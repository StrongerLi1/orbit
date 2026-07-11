"""Private NDJSON bridge from Orbit to Hermes Agent's streaming callback."""

import json
import signal
import sys
from collections import OrderedDict
from contextlib import redirect_stdout


_active_agent = None
_transport_stdout = sys.stdout
_SESSION_CACHE_LIMIT = 16


def _emit(kind: str, **payload) -> None:
    _transport_stdout.write(json.dumps({"type": kind, **payload}, ensure_ascii=False) + "\n")
    _transport_stdout.flush()


def _interrupt(_signum, _frame) -> None:
    if _active_agent is not None:
        try:
            _active_agent.interrupt("Orbit stopped generation")
        except Exception:
            pass
    raise KeyboardInterrupt


def _install_signal_handlers() -> None:
    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _interrupt)


def _close_cli(cli) -> None:
    try:
        with redirect_stdout(sys.stderr):
            if cli.agent is not None:
                cli.agent.close()
    except Exception:
        pass


def _run_turn(payload: dict, sessions=None, hermes_cli_class=None) -> int:
    global _active_agent
    conversation_key = str(payload.get("conversationKey") or payload.get("hermesSessionId") or "").strip()[:120]
    try:
        prompt = str(payload.get("content") or "").strip()
        session_id = str(payload.get("hermesSessionId") or "").strip()
        if not prompt:
            raise ValueError("empty prompt")

        if hermes_cli_class is None:
            with redirect_stdout(sys.stderr):
                from cli import HermesCLI as hermes_cli_class

        cli = sessions.get(conversation_key) if sessions is not None and conversation_key else None
        if cli is not None:
            current_session_id = str(cli.agent.session_id or cli.session_id or "")
            if not session_id or (current_session_id and current_session_id != session_id):
                sessions.pop(conversation_key, None)
                _close_cli(cli)
                cli = None

        if cli is None:
            cli = hermes_cli_class(resume=session_id or None, compact=True)
            cli.tool_progress_mode = "off"
            cli.streaming_enabled = False
            with redirect_stdout(sys.stderr):
                if not cli._ensure_runtime_credentials():
                    raise RuntimeError("Hermes provider is not configured")
                route = cli._resolve_turn_agent_config(prompt)
                if not cli._init_agent(
                    model_override=route["model"],
                    runtime_override=route["runtime"],
                    request_overrides=route.get("request_overrides"),
                ):
                    raise RuntimeError("Hermes agent initialization failed")
            if sessions is not None and conversation_key:
                sessions[conversation_key] = cli
                sessions.move_to_end(conversation_key)
                while len(sessions) > _SESSION_CACHE_LIMIT:
                    _, evicted = sessions.popitem(last=False)
                    _close_cli(evicted)
        elif sessions is not None:
            sessions.move_to_end(conversation_key)

        _active_agent = cli.agent
        _active_agent.quiet_mode = True
        _active_agent.suppress_status_output = True
        _active_agent.stream_delta_callback = None
        _active_agent.tool_gen_callback = None
        _emit("started", hermesSessionId=_active_agent.session_id or cli.session_id)

        streamed: list[str] = []

        def on_delta(text) -> None:
            if isinstance(text, str) and text:
                streamed.append(text)
                _emit("delta", content=text)

        with redirect_stdout(sys.stderr):
            result = _active_agent.run_conversation(
                user_message=prompt,
                conversation_history=cli.conversation_history,
                stream_callback=on_delta,
            )

        final = result.get("final_response", "") if isinstance(result, dict) else str(result or "")
        if isinstance(result, dict) and isinstance(result.get("messages"), list):
            cli.conversation_history = result["messages"]
        if not streamed and final:
            streamed.append(final)
            _emit("delta", content=final)
        latest_session_id = _active_agent.session_id or cli.session_id
        cli.session_id = latest_session_id
        _emit("completed", content="".join(streamed) or final, hermesSessionId=latest_session_id)
        _active_agent = None
        return 0
    except Exception as error:
        if sessions is not None and conversation_key:
            failed = sessions.pop(conversation_key, None)
            if failed is not None:
                _close_cli(failed)
        _active_agent = None
        print(f"Hermes stream bridge failed: {error}", file=sys.stderr)
        _emit("error", error="Hermes 运行失败，请检查服务配置")
        return 1


def _worker_main() -> int:
    sessions = OrderedDict()
    try:
        with redirect_stdout(sys.stderr):
            from cli import HermesCLI
        _emit("ready")
        for line in sys.stdin:
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("invalid payload")
                _run_turn(payload, sessions=sessions, hermes_cli_class=HermesCLI)
            except (json.JSONDecodeError, ValueError):
                _emit("error", error="Hermes 运行失败，请检查服务配置")
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        for cli in sessions.values():
            _close_cli(cli)


def main() -> int:
    _install_signal_handlers()
    if "--worker" in sys.argv[1:]:
        return _worker_main()
    try:
        payload = json.loads(sys.stdin.readline())
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
        return _run_turn(payload)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"Hermes stream bridge failed: {error}", file=sys.stderr)
        _emit("error", error="Hermes 运行失败，请检查服务配置")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
