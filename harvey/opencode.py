"""OpenCode adapter — one-shot ``opencode run --format json`` calls.

The thin counterpart to the Claude path in brain.py: every Harvey call is an
independent subprocess (no sessions, no server attach). OpenCode's auth is
whatever ``opencode providers`` already holds; Harvey never manages it.
Failure kinds (setup/auth/usage_limit/transient) let the brain pause or retry
without parsing CLI text itself.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger("harvey.opencode")

OPENCODE_CLI = "opencode"
# Same Windows argv-limit trick as brain.py: longer prompts travel on stdin.
_MAX_ARGV_PROMPT_CHARS = 8000
DEFAULT_TIMEOUT_SECONDS = 300

# stderr fragments that mean retrying is pointless until the operator acts.
# "opencode auth" is the CLI's own login hint; a bare "auth" substring would
# also match "author" and similar noise, so it is deliberately absent.
_AUTH_PATTERNS = (
    "not logged in",
    "log in",
    "login",
    "unauthorized",
    "401",
    "api key",
    "credential",
    "opencode auth",
)
_USAGE_LIMIT_PATTERNS = (
    "rate limit",
    "usage limit",
    "quota",
    "429",
    "exceeded",
)


class OpenCodeError(Exception):
    """A failed OpenCode call, classified for the caller.

    kind: "setup" | "auth" | "usage_limit" | "transient"
    retryable: whether an immediate backoff-retry could succeed
    """

    def __init__(self, message: str, kind: str = "transient", retryable: bool | None = None):
        super().__init__(message)
        self.kind = kind
        self.retryable = kind == "transient" if retryable is None else retryable


def _cli_missing() -> OpenCodeError:
    return OpenCodeError(
        "OpenCode CLI not found. Install it: https://opencode.ai",
        kind="setup",
        retryable=False,
    )


@dataclass
class OpenCodeResult:
    """What Harvey needs back from one successful run."""

    text: str
    model: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = field(default=None)


def classify_error(error_text: str) -> tuple[str, bool]:
    """Map CLI error text to (kind, retryable). Unknown text is transient."""
    text = (error_text or "").lower()
    if any(p in text for p in _USAGE_LIMIT_PATTERNS):
        return "usage_limit", True
    if any(p in text for p in _AUTH_PATTERNS):
        return "auth", False
    return "transient", True


def parse_run_output(raw: str, model: str = "", duration_ms: int = 0) -> OpenCodeResult:
    """Parse ``opencode run --format json`` NDJSON stdout.

    Live shape (v1.19.4): one JSON object per line. Assistant text arrives as
    ``{"type":"text","part":{"text":...}}`` events (concatenated in order);
    token totals and cost ride the final ``step_finish`` event. Unknown event
    types are ignored so a newer CLI doesn't break the parser.
    """
    texts: list[str] = []
    input_tokens = output_tokens = total_tokens = 0
    cost_usd: float | None = None
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        part = event.get("part") or {}
        if event.get("type") == "text" and isinstance(part, dict):
            piece = part.get("text")
            if isinstance(piece, str):
                texts.append(piece)
        if event.get("type") == "step_finish" and isinstance(part, dict):
            tokens = part.get("tokens") or {}
            if isinstance(tokens, dict):
                input_tokens = int(tokens.get("input") or 0)
                output_tokens = int(tokens.get("output") or 0)
                total_tokens = int(tokens.get("total") or 0)
            cost = part.get("cost")
            if isinstance(cost, (int, float)):
                cost_usd = float(cost)

    text = "".join(texts).strip()
    if not text:
        raise OpenCodeError(
            "OpenCode run produced no assistant text", kind="transient", retryable=True
        )
    return OpenCodeResult(
        text=text,
        model=model,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )


def build_run_command(model: str, prompt: str, prompt_via_stdin: bool) -> list[str]:
    cmd = [OPENCODE_CLI, "run", "--format", "json"]
    if model:
        cmd += ["-m", model]
    if not prompt_via_stdin:
        cmd.append(prompt)
    return cmd


async def run(prompt: str, model: str = "", timeout: float = DEFAULT_TIMEOUT_SECONDS) -> OpenCodeResult:
    """One-shot run; raises OpenCodeError classified for pause/retry decisions.

    Empty ``model`` uses OpenCode's own default (validated empty in config).
    """
    prompt_via_stdin = len(prompt) > _MAX_ARGV_PROMPT_CHARS
    cmd = build_run_command(model, prompt, prompt_via_stdin)
    started = time.monotonic()
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=(asyncio.subprocess.PIPE if prompt_via_stdin else asyncio.subprocess.DEVNULL),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise _cli_missing() from e

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(prompt.encode("utf-8") if prompt_via_stdin else None),
            timeout=timeout,
        )
    except asyncio.TimeoutError as e:
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            pass
        logger.error(f"OpenCode call timed out after {timeout:.0f}s. Killing process.")
        raise OpenCodeError(
            f"OpenCode call timed out after {timeout:.0f}s", kind="transient", retryable=True
        ) from e
    except asyncio.CancelledError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        raise

    duration_ms = int((time.monotonic() - started) * 1000)
    if process.returncode != 0:
        error = stderr.decode(errors="replace").strip()
        kind, retryable = classify_error(error)
        logger.error(f"OpenCode exited with code {process.returncode}: {error[:300]}")
        raise OpenCodeError(
            f"OpenCode exited with code {process.returncode}: {error[:300]}",
            kind=kind,
            retryable=retryable,
        )

    raw = stdout.decode(errors="replace")
    return parse_run_output(raw, model=model, duration_ms=duration_ms)


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


async def preflight() -> str:
    """Cheap health check for ``harvey status --check``: CLI present, logged in.

    Returns the CLI version string, or raises OpenCodeError (setup/auth).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            OPENCODE_CLI, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    except FileNotFoundError as e:
        raise _cli_missing() from e
    except asyncio.TimeoutError as e:
        raise OpenCodeError("opencode --version timed out", kind="transient") from e

    if proc.returncode != 0:
        raise OpenCodeError(
            f"opencode --version failed (code {proc.returncode})",
            kind="setup",
            retryable=False,
        )
    version = _strip_ansi(stdout.decode(errors="replace")).strip()

    try:
        proc = await asyncio.create_subprocess_exec(
            OPENCODE_CLI, "providers", "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError as e:
        raise OpenCodeError("opencode providers list timed out", kind="transient") from e

    # Observed shape (v1.19.4): a credentials table with one ●-marked row per
    # logged-in provider. Heuristic: a logged-in listing contains that bullet
    # (or the word "credential"); anything else is treated as not logged in.
    listing = _strip_ansi(stdout.decode(errors="replace"))
    if proc.returncode != 0:
        err = _strip_ansi(stderr.decode(errors="replace")).strip()
        kind, retryable = classify_error(err)
        if kind == "transient":
            kind, retryable = "auth", False
        raise OpenCodeError(
            f"OpenCode credentials check failed: {err[:300] or proc.returncode}",
            kind=kind,
            retryable=retryable,
        )
    if "●" not in listing and "credential" not in listing.lower():
        raise OpenCodeError(
            "No OpenCode credentials configured. Run: opencode providers login",
            kind="auth",
            retryable=False,
        )
    return version
