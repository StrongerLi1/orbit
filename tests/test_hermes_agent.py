import asyncio
import io
import json
import sys
from collections import OrderedDict
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException

from backend.config import settings
import backend.hermes_stream_bridge as bridge_module
import backend.main as main_module
from backend.hermes_stream_pool import HermesStreamPool
from backend.main import (
    _hermes_chat_stream_events,
    _hermes_chat_title,
    _hermes_status,
    _hermes_stream_command_parts,
    _parse_hermes_stream_record,
    _rewrite_hermes_css,
    _rewrite_hermes_html,
    _rewrite_hermes_javascript,
    _sse_event,
)


class FakeStdout:
    def __init__(self, records):
        self.records = iter(records)

    async def readline(self):
        return next(self.records, b"")


class FakeProcess:
    def __init__(self, records):
        self.stdout = FakeStdout(records)
        self.returncode = 0

    async def wait(self):
        return self.returncode


class FakeLock:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.exited = False

    def __enter__(self):
        return self.acquired

    def __exit__(self, *_args):
        self.exited = True


class FakeRequest:
    async def json(self):
        return {"content": "hello"}


def main() -> None:
    original_command = settings.hermes_dashboard_command
    original_url = settings.hermes_dashboard_url
    original_timeout = settings.hermes_dashboard_timeout
    try:
        settings.hermes_dashboard_command = "orbit-hermes-missing-binary dashboard --no-open"
        settings.hermes_dashboard_url = "http://127.0.0.1:9"
        settings.hermes_dashboard_timeout = 0.1
        status = _hermes_status()
        assert status["configured"] is True
        assert status["installed"] is False
        assert status["running"] is False
        assert status["dashboardPublicUrl"] == "/hermes-dashboard/"
        assert "not installed" in status["message"]
        html = _rewrite_hermes_html(b'<head><script src="/assets/app.js"></script><link href="/favicon.ico">')
        assert b'window.__HERMES_BASE_PATH__ = "/hermes-dashboard"' in html
        assert b'src="/hermes-dashboard/assets/app.js?v=orbit-hermes-proxy-20260707"' in html
        assert b'href="/hermes-dashboard/favicon.ico"' in html
        original_html = _rewrite_hermes_html(b'<head><script>window.__HERMES_BASE_PATH__="";</script>')
        assert b'window.__HERMES_BASE_PATH__="/hermes-dashboard"' in original_html
        script = _rewrite_hermes_javascript(b"let base=window.__HERMES_BASE_PATH__??``;")
        assert script == b'let base="/hermes-dashboard";'
        css = _rewrite_hermes_css(b"@font-face{src:url(/assets/font.woff2)}")
        assert css == b"@font-face{src:url(/hermes-dashboard/assets/font.woff2)}"
        assert _hermes_chat_title("  hello   Hermes  ") == "hello Hermes"
        assert _hermes_chat_title("a" * 31) == ("a" * 30) + "…"
        original_stream_command = settings.hermes_stream_command
        try:
            settings.hermes_stream_command = 'python3 -m backend.hermes_stream_bridge'
            assert _hermes_stream_command_parts() == ["python3", "-m", "backend.hermes_stream_bridge"]
        finally:
            settings.hermes_stream_command = original_stream_command

        assert _parse_hermes_stream_record(b'{"type":"delta","content":"hello"}\n') == {"type": "delta", "content": "hello"}
        assert _parse_hermes_stream_record(b'{"type":"completed","content":"hello","hermesSessionId":"next"}\n') == {
            "type": "completed",
            "content": "hello",
            "hermesSessionId": "next",
        }
        try:
            _parse_hermes_stream_record(b'{"type":"tool","content":"secret"}\n')
            raise AssertionError("unknown bridge records must be rejected")
        except ValueError:
            pass
        assert _sse_event("delta", {"content": "你好"}) == 'event: delta\ndata: {"content": "你好"}\n\n'

        class SlowStdout:
            async def readline(self):
                await asyncio.sleep(0.05)
                return b""

        async def configured_turn_timeout_is_enforced():
            process = FakeProcess([])
            process.stdout = SlowStdout()
            original_chat_timeout = settings.hermes_chat_timeout
            settings.hermes_chat_timeout = 0.01
            try:
                try:
                    async for _record in main_module._hermes_stream_records(process):
                        pass
                    raise AssertionError("configured Hermes turn timeout must be enforced")
                except asyncio.TimeoutError:
                    pass
            finally:
                settings.hermes_chat_timeout = original_chat_timeout

        asyncio.run(configured_turn_timeout_is_enforced())

        protocol = io.StringIO()
        hermes_noise = io.StringIO()
        original_transport_stdout = bridge_module._transport_stdout
        try:
            bridge_module._transport_stdout = protocol
            with redirect_stdout(hermes_noise):
                print("Hermes diagnostic")
                bridge_module._emit("delta", content="流")
        finally:
            bridge_module._transport_stdout = original_transport_stdout
        assert json.loads(protocol.getvalue()) == {"type": "delta", "content": "流"}
        assert hermes_noise.getvalue() == "Hermes diagnostic\n"

        class FakeAgent:
            def __init__(self):
                self.session_id = "native-1"
                self.run_calls = 0
                self.histories = []

            def run_conversation(self, user_message, conversation_history, stream_callback):
                self.run_calls += 1
                self.histories.append(list(conversation_history))
                stream_callback(f"reply-{self.run_calls}")
                return {
                    "final_response": f"reply-{self.run_calls}",
                    "messages": [*conversation_history, {"role": "user", "content": user_message}, {"role": "assistant", "content": f"reply-{self.run_calls}"}],
                }

            def close(self):
                pass

        class FakeHermesCLI:
            creations = 0

            def __init__(self, resume=None, compact=False):
                type(self).creations += 1
                self.session_id = resume or "native-1"
                self.conversation_history = []
                self.agent = None

            def _ensure_runtime_credentials(self):
                return True

            def _resolve_turn_agent_config(self, _prompt):
                return {"model": "fake", "runtime": {}, "request_overrides": None}

            def _init_agent(self, **_kwargs):
                self.agent = FakeAgent()
                return True

        sessions = OrderedDict()
        protocol = io.StringIO()
        original_transport_stdout = bridge_module._transport_stdout
        try:
            bridge_module._transport_stdout = protocol
            bridge_module._run_turn({"conversationKey": "c1", "content": "one", "hermesSessionId": ""}, sessions, FakeHermesCLI)
            bridge_module._run_turn({"conversationKey": "c1", "content": "two", "hermesSessionId": "native-1"}, sessions, FakeHermesCLI)
        finally:
            bridge_module._transport_stdout = original_transport_stdout
        assert FakeHermesCLI.creations == 1
        assert sessions["c1"].agent.run_calls == 2
        assert len(sessions["c1"].agent.histories[1]) == 2
        assert [json.loads(line)["type"] for line in protocol.getvalue().splitlines()] == [
            "started", "delta", "completed", "started", "delta", "completed",
        ]

        async def pool_reuses_and_replaces_workers():
            worker_code = (
                "import json,os,sys; print(json.dumps({'type':'ready'}),flush=True); "
                "exec(\"for line in sys.stdin:\\n p=json.loads(line); sid=p.get('hermesSessionId') or 'native'; "
                "print(json.dumps({'type':'started','hermesSessionId':sid}),flush=True); "
                "print(json.dumps({'type':'delta','content':str(os.getpid())}),flush=True); "
                "print(json.dumps({'type':'completed','content':str(os.getpid()),'hermesSessionId':sid}),flush=True)\")"
            )
            pool = HermesStreamPool([sys.executable, "-u", "-c", worker_code], 1)

            async def turn():
                lease = await pool.acquire("c1", timeout=2)
                await lease.send({"content": "hello", "hermesSessionId": "native"})
                records = [json.loads(await lease.stdout.readline()) for _ in range(3)]
                await lease.release(reusable=True)
                return lease.pid, records

            first_pid, first_records = await turn()
            second_pid, second_records = await turn()
            assert first_pid == second_pid
            assert [item["type"] for item in first_records] == ["started", "delta", "completed"]
            assert [item["type"] for item in second_records] == ["started", "delta", "completed"]
            discarded = await pool.acquire("c1", timeout=2)
            await discarded.release(reusable=False)
            replacement, _ = await turn()
            assert replacement != first_pid
            await pool.close()

        asyncio.run(pool_reuses_and_replaces_workers())

        original_add = main_module.add_hermes_message
        original_update = main_module.update_hermes_conversation_after_message
        original_require = main_module.require_permission
        original_get = main_module.get_hermes_conversation
        original_list_messages = main_module.list_hermes_messages
        original_lock = main_module.hermes_chat_user_lock
        original_start = main_module._start_hermes_stream
        saved = []
        try:
            main_module.add_hermes_message = lambda conversation_id, user_id, role, content, status="completed": saved.append({
                "id": str(len(saved) + 1), "conversationId": conversation_id, "userId": user_id,
                "role": role, "content": content, "status": status,
            }) or saved[-1]
            main_module.update_hermes_conversation_after_message = lambda conversation_id, title, session_id: {
                "id": conversation_id, "title": title, "hermesSessionId": session_id,
            }

            async def complete_stream():
                lock = FakeLock()
                process = FakeProcess([
                    b'{"type":"started","hermesSessionId":"next"}\n',
                    b'{"type":"delta","content":"hello "}\n',
                    b'{"type":"delta","content":"back"}\n',
                    b'{"type":"completed","content":"hello back","hermesSessionId":"next"}\n',
                ])
                events = [event async for event in _hermes_chat_stream_events(
                    process, lock, "c1", "u1", "title", "old", {"id": "m1"}, {"id": "c1"},
                )]
                assert lock.exited is True
                assert any(event.startswith("event: delta") for event in events)
                payload = json.loads([event for event in events if event.startswith("event: completed")][0].split("data: ", 1)[1])
                assert payload["message"]["content"] == "hello back"

            async def disconnected_stream_finishes_in_background():
                lock = FakeLock()
                process = FakeProcess([
                    b'{"type":"delta","content":"background"}\n',
                    b'{"type":"completed","content":"background","hermesSessionId":"next"}\n',
                ])
                stream = _hermes_chat_stream_events(
                    process, lock, "c2", "u1", "title", "old", {"id": "m2"}, {"id": "c2"},
                )
                await stream.__anext__()
                assert "background" in await stream.__anext__()
                await stream.aclose()
                await asyncio.gather(*list(main_module._hermes_background_tasks))
                assert lock.exited is True

            async def explicitly_stopped_stream_is_interrupted():
                lock = FakeLock()
                process = FakeProcess([b'{"type":"delta","content":"partial"}\n'])
                stream = _hermes_chat_stream_events(
                    process, lock, "c-stop", "u1", "title", "old", {"id": "m3"}, {"id": "c-stop"},
                )
                await stream.__anext__()
                assert "partial" in await stream.__anext__()
                main_module._hermes_stop_requests.add("c-stop")
                await stream.aclose()
                assert lock.exited is True

            async def disconnect_after_completion_does_not_detach():
                lock = FakeLock()
                process = FakeProcess([
                    b'{"type":"completed","content":"done","hermesSessionId":"next"}\n',
                ])
                stream = _hermes_chat_stream_events(
                    process, lock, "c-done", "u1", "title", "old", {"id": "m4"}, {"id": "c-done"},
                )
                await stream.__anext__()
                assert "done" in await stream.__anext__()
                await stream.aclose()
                assert lock.exited is True
                assert not main_module._hermes_background_tasks

            asyncio.run(complete_stream())
            asyncio.run(disconnected_stream_finishes_in_background())
            asyncio.run(explicitly_stopped_stream_is_interrupted())
            asyncio.run(disconnect_after_completion_does_not_detach())
            assert saved[0]["status"] == "completed"
            assert saved[1]["content"] == "background"
            assert saved[1]["status"] == "completed"
            assert saved[2]["content"] == "partial"
            assert saved[2]["status"] == "interrupted"
            assert saved[3]["content"] == "done"
            assert saved[3]["status"] == "completed"

            async def fake_start(_content, _session_id, _conversation_id):
                return FakeProcess([
                    b'{"type":"delta","content":"live"}\n',
                    b'{"type":"completed","content":"live","hermesSessionId":"next"}\n',
                ])

            main_module.require_permission = lambda _request, _permission: {"id": "u1"}
            main_module.get_hermes_conversation = lambda conversation_id, user_id=None: {
                "id": conversation_id, "userId": user_id or "u1", "title": "新的对话", "hermesSessionId": "",
            }
            main_module.list_hermes_messages = lambda _conversation_id: []
            main_module.hermes_chat_user_lock = lambda _user_id: FakeLock()
            main_module._start_hermes_stream = fake_start

            async def stop_endpoint_marks_generation():
                process = FakeProcess([])
                main_module._hermes_active_streams["c-stop-api"] = process
                result = await main_module.hermes_chat_stop_message("c-stop-api", FakeRequest())
                assert result == {"ok": True}
                assert "c-stop-api" in main_module._hermes_stop_requests
                main_module._hermes_active_streams.pop("c-stop-api", None)
                main_module._hermes_stop_requests.discard("c-stop-api")

            asyncio.run(stop_endpoint_marks_generation())

            async def endpoint_stream():
                response = await main_module.hermes_chat_stream_message("c3", FakeRequest())
                assert main_module.hermes_chat_conversation("c3", FakeRequest())["generating"] is True
                events = [event async for event in response.body_iterator]
                assert response.media_type == "text/event-stream"
                assert response.headers["x-accel-buffering"] == "no"
                assert any(event.startswith("event: completed") for event in events)
                assert main_module.hermes_chat_conversation("c3", FakeRequest())["generating"] is False

            asyncio.run(endpoint_stream())

            main_module.hermes_chat_user_lock = lambda _user_id: FakeLock(False)
            try:
                asyncio.run(main_module.hermes_chat_stream_message("c3", FakeRequest()))
                raise AssertionError("a second active generation must be rejected")
            except HTTPException as error:
                assert error.status_code == 409

            started = False

            async def should_not_start(_content, _session_id, _conversation_id):
                nonlocal started
                started = True

            main_module.get_hermes_conversation = lambda *_args, **_kwargs: None
            main_module._start_hermes_stream = should_not_start
            try:
                asyncio.run(main_module.hermes_chat_stream_message("another-user", FakeRequest()))
                raise AssertionError("cross-user conversations must be rejected")
            except HTTPException as error:
                assert error.status_code == 404
                assert started is False
        finally:
            main_module.add_hermes_message = original_add
            main_module.update_hermes_conversation_after_message = original_update
            main_module.require_permission = original_require
            main_module.get_hermes_conversation = original_get
            main_module.list_hermes_messages = original_list_messages
            main_module.hermes_chat_user_lock = original_lock
            main_module._start_hermes_stream = original_start
    finally:
        settings.hermes_dashboard_command = original_command
        settings.hermes_dashboard_url = original_url
        settings.hermes_dashboard_timeout = original_timeout


if __name__ == "__main__":
    main()
