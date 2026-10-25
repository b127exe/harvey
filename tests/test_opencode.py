"""OpenCode adapter: one-shot `opencode run --format json` calls, typed
failures, and a cheap preflight — verified with fakes, never a real CLI."""

import asyncio

import pytest

import harvey.opencode as oc
from harvey.opencode import OpenCodeError, OpenCodeResult, parse_run_output


# ── event parsing (shape confirmed by a live capture) ──

_LIVE_SHAPE = "\n".join([
    '{"type":"step_start","timestamp":1,"sessionID":"s","part":{"id":"a","type":"step-start"}}',
    '{"type":"text","timestamp":2,"sessionID":"s","part":{"id":"b","type":"text","text":"OK","time":{"start":1,"end":5}}}',
    '{"type":"step_finish","timestamp":3,"sessionID":"s","part":{"id":"c","type":"step-finish","reason":"stop",'
    '"tokens":{"total":100,"input":90,"output":7,"reasoning":3,"cache":{"write":0,"read":0}},"cost":0.01}}',
])


def test_parse_run_output_happy_path():
    result = parse_run_output(_LIVE_SHAPE, model="opencode-go/mimo-v2.5", duration_ms=1500)
    assert isinstance(result, OpenCodeResult)
    assert result.text == "OK"
    assert result.model == "opencode-go/mimo-v2.5"
    assert result.duration_ms == 1500
    assert result.input_tokens == 90
    assert result.output_tokens == 7
    assert result.total_tokens == 100
    assert result.cost_usd == pytest.approx(0.01)


def test_parse_run_output_concatenates_multiple_text_events():
    raw = "\n".join([
        '{"type":"text","part":{"type":"text","text":"Hello "}}',
        '{"type":"text","part":{"type":"text","text":"world"}}',
        '{"type":"step_finish","part":{"type":"step-finish","tokens":{"total":5,"input":4,"output":1}}}',
    ])
    result = parse_run_output(raw, model="", duration_ms=10)
    assert result.text == "Hello world"


def test_parse_run_output_ignores_unknown_event_types():
    raw = '\n'.join([
        '{"type":"something_new","part":{"x":1}}',
        '{"type":"text","part":{"type":"text","text":"ok"}}',
    ])
    assert parse_run_output(raw, model="", duration_ms=1).text == "ok"


def test_parse_run_output_missing_text_is_a_typed_error():
    with pytest.raises(OpenCodeError) as exc:
        parse_run_output('{"type":"step_finish","part":{"tokens":{}}}', model="", duration_ms=1)
    assert exc.value.kind == "transient"
    assert exc.value.retryable is True


def test_parse_run_output_blank_output_is_a_typed_error():
    with pytest.raises(OpenCodeError):
        parse_run_output("   ", model="", duration_ms=1)


# ── error classification ──


@pytest.mark.parametrize("fragment,kind,retryable", [
    ("Please run opencode auth to log in", "auth", False),
    ("401 Unauthorized", "auth", False),
    ("no credentials configured", "auth", False),
    ("rate limit exceeded", "usage_limit", True),
    ("quota exhausted for this model", "usage_limit", True),
    ("connection reset by peer", "transient", True),
])
def test_classify_error(fragment, kind, retryable):
    got_kind, got_retryable = oc.classify_error(fragment)
    assert (got_kind, got_retryable) == (kind, retryable)


# ── subprocess seam (monkeypatched create_subprocess_exec) ──


class _FakeProcess:
    def __init__(self, returncode=0, stdout=b"", stderr=b"", hang=False):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._hang = hang
        self.killed = False
        self.stdin_data = None

    def kill(self):
        self.killed = True

    async def wait(self):
        return self.returncode

    async def communicate(self, data=None):
        self.stdin_data = data
        if self._hang:
            await asyncio.sleep(3600)
        return self._stdout, self._stderr


def _capture_exec(monkeypatch, process_factory):
    captured = {"calls": 0}

    async def fake_exec(*cmd, **kwargs):
        captured["calls"] += 1
        captured["cmd"] = list(cmd)
        captured["kwargs"] = kwargs
        captured["proc"] = process_factory(captured["calls"])
        return captured["proc"]

    monkeypatch.setattr(oc.asyncio, "create_subprocess_exec", fake_exec)
    return captured


def _ok_process(_n):
    return _FakeProcess(stdout=_LIVE_SHAPE.encode("utf-8"))


@pytest.mark.asyncio
async def test_run_builds_one_shot_json_command(monkeypatch):
    captured = _capture_exec(monkeypatch, _ok_process)
    result = await oc.run("hi", model="opencode-go/mimo-v2.5")
    cmd = captured["cmd"]
    assert cmd[0] == "opencode"
    assert cmd[1:4] == ["run", "--format", "json"]
    assert cmd[cmd.index("-m") + 1] == "opencode-go/mimo-v2.5"
    assert "hi" in cmd
    assert captured["kwargs"]["stdin"] == asyncio.subprocess.DEVNULL
    assert result.text == "OK"


@pytest.mark.asyncio
async def test_run_omits_model_flag_when_model_empty(monkeypatch):
    captured = _capture_exec(monkeypatch, _ok_process)
    await oc.run("hi", model="")
    assert "-m" not in captured["cmd"]


@pytest.mark.asyncio
async def test_long_prompts_go_via_stdin(monkeypatch):
    captured = _capture_exec(monkeypatch, _ok_process)
    long_prompt = "x" * (oc._MAX_ARGV_PROMPT_CHARS + 1)
    await oc.run(long_prompt, model="opencode-go/mimo-v2.5")
    assert long_prompt not in captured["cmd"]
    assert captured["kwargs"]["stdin"] == asyncio.subprocess.PIPE
    assert captured["proc"].stdin_data == long_prompt.encode("utf-8")


@pytest.mark.asyncio
async def test_auth_failure_is_non_retryable_typed_error(monkeypatch):
    def factory(_n):
        return _FakeProcess(returncode=1, stderr=b"Error: please log in with opencode auth")
    _capture_exec(monkeypatch, factory)
    with pytest.raises(OpenCodeError) as exc:
        await oc.run("hi", model="m/x")
    assert exc.value.kind == "auth"
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_transient_failure_is_retryable_typed_error(monkeypatch):
    def factory(_n):
        return _FakeProcess(returncode=1, stderr=b"connection reset by peer")
    _capture_exec(monkeypatch, factory)
    with pytest.raises(OpenCodeError) as exc:
        await oc.run("hi", model="m/x")
    assert exc.value.kind == "transient"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_missing_cli_is_setup_error(monkeypatch):
    async def fake_exec(*_a, **_k):
        raise FileNotFoundError("opencode")
    monkeypatch.setattr(oc.asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(OpenCodeError) as exc:
        await oc.run("hi", model="m/x")
    assert exc.value.kind == "setup"
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_timeout_kills_process_and_raises_transient(monkeypatch):
    def factory(_n):
        return _FakeProcess(hang=True)
    captured = _capture_exec(monkeypatch, factory)
    with pytest.raises(OpenCodeError) as exc:
        await oc.run("hi", model="m/x", timeout=0.05)
    assert captured["proc"].killed is True
    assert exc.value.kind == "transient"
    assert exc.value.retryable is True


# ── preflight ──


@pytest.mark.asyncio
async def test_preflight_ok_returns_version(monkeypatch):
    def factory(call):
        if call == 1:
            return _FakeProcess(stdout=b"1.19.4\n")
        return _FakeProcess(stdout="Credentials\n● OpenCode Go\n".encode("utf-8"))
    _capture_exec(monkeypatch, factory)
    version = await oc.preflight()
    assert version == "1.19.4"


@pytest.mark.asyncio
async def test_preflight_missing_cli_is_setup_error(monkeypatch):
    async def fake_exec(*_a, **_k):
        raise FileNotFoundError("opencode")
    monkeypatch.setattr(oc.asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(OpenCodeError) as exc:
        await oc.preflight()
    assert exc.value.kind == "setup"


@pytest.mark.asyncio
async def test_preflight_no_credentials_is_auth_error(monkeypatch):
    def factory(call):
        if call == 1:
            return _FakeProcess(stdout=b"1.19.4\n")
        return _FakeProcess(stdout=b"no providers logged in\n")
    _capture_exec(monkeypatch, factory)
    with pytest.raises(OpenCodeError) as exc:
        await oc.preflight()
    assert exc.value.kind == "auth"
