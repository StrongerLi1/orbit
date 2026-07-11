import asyncio
from pathlib import Path
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urlparse

import websockets
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from .auth import (
    clear_auth_cookies,
    create_user,
    delete_user_account,
    ensure_user_active,
    get_user_by_username,
    issue_playcaptcha_token,
    list_permissions,
    list_roles,
    list_users,
    public_user,
    require_permission,
    refresh_user,
    require_user,
    require_playcaptcha_token,
    revoke_refresh_token,
    set_user_banned,
    set_auth_cookies,
    set_user_roles,
    touch_login,
    validate_credentials_input,
    verify_password,
)
from .config import PUBLIC_DIR, settings
from .database import COLLECTIONS, initialize_database
from .hermes_stream_pool import HermesStreamLease, HermesStreamPool
from .repository import (
    create_item,
    delete_item,
    folder_exists,
    folder_has_bookmarks,
    add_hermes_message,
    create_hermes_conversation,
    get_hermes_conversation,
    get_item,
    list_admin_hermes_conversations,
    list_hermes_conversations,
    list_hermes_messages,
    list_items,
    hermes_chat_user_lock,
    soft_delete_hermes_conversation,
    update_hermes_conversation_after_message,
    update_item,
)


app = FastAPI(title=settings.app_name)
logger = logging.getLogger(__name__)
_hermes_stream_pool: HermesStreamPool | None = None
_hermes_active_streams: dict[str, Any] = {}
_hermes_stop_requests: set[str] = set()
_hermes_background_tasks: set[asyncio.Task] = set()


@app.on_event("startup")
async def startup() -> None:
    initialize_database()
    await _warm_hermes_stream_pool()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _hermes_stream_pool
    for task in list(_hermes_background_tasks):
        task.cancel()
    if _hermes_background_tasks:
        await asyncio.gather(*_hermes_background_tasks, return_exceptions=True)
    if _hermes_stream_pool is not None:
        await _hermes_stream_pool.close()
        _hermes_stream_pool = None


def validate(collection: str, input_data: dict[str, Any]) -> dict[str, Any]:
    item = dict(input_data or {})
    item.pop("id", None)
    item.pop("createdAt", None)

    if collection == "folders":
        name = str(item.get("name") or "").strip()[:30]
        if not name:
            raise HTTPException(status_code=422, detail="收藏夹名称不能为空")
        result = {"name": name}
        if "sortOrder" in item:
            result["sortOrder"] = max(0, min(100_000, round(_number(item.get("sortOrder"), 0))))
        return result

    if collection == "excerpts":
        content = str(item.get("content") or "").strip()[:3000]
        if not content:
            raise HTTPException(status_code=422, detail="摘录内容不能为空")
        excerpt_date = str(item.get("excerptDate") or "")
        if excerpt_date and not _is_date(excerpt_date):
            raise HTTPException(status_code=422, detail="请输入有效日期")
        return {
            "content": content,
            "source": str(item.get("source") or "").strip()[:200],
            "author": str(item.get("author") or "").strip()[:100],
            "excerptDate": excerpt_date,
            "note": str(item.get("note") or "").strip()[:500],
        }

    title = str(item.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="标题不能为空")
    item["title"] = title

    if collection == "bookmarks":
        url = str(item.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=422, detail="请输入有效的网址")
        return {
            "title": title,
            "url": url,
            "category": str(item.get("category") or "未分类").strip(),
            "note": str(item.get("note") or "").strip(),
            "favorite": bool(item.get("favorite")),
        }

    if collection == "todos":
        priority = item.get("priority") if item.get("priority") in {"low", "medium", "high"} else "medium"
        return {
            "title": title,
            "priority": priority,
            "dueDate": str(item.get("dueDate") or ""),
            "completed": bool(item.get("completed")),
        }

    if collection == "plans":
        frequency = item.get("frequencyType") if item.get("frequencyType") in {"daily", "weekly", "monthly"} else "daily"
        target_count = max(1, min(99, round(_number(item.get("targetCount"), 1))))
        start_date = str(item.get("startDate") or item.get("date") or "")
        end_date = str(item.get("endDate") or "")
        if not _is_date(start_date):
            raise HTTPException(status_code=422, detail="请选择开始日期")
        if end_date and not _is_date(end_date):
            raise HTTPException(status_code=422, detail="请输入有效结束日期")
        if end_date and end_date < start_date:
            raise HTTPException(status_code=422, detail="结束日期不能早于开始日期")
        time = str(item.get("time") or "")
        if len(time) != 5 or time[2] != ":" or not time.replace(":", "").isdigit() or not ("00:00" <= time <= "23:59"):
            raise HTTPException(status_code=422, detail="请输入有效时间")
        duration = max(5, min(480, int(_number(item.get("duration"), 30))))
        color = item.get("color") if item.get("color") in {"violet", "orange", "green", "blue"} else "violet"
        completions = item.get("completions") if isinstance(item.get("completions"), dict) else {}
        clean_completions = {
            str(day): max(0, min(99, round(_number(count, 0))))
            for day, count in completions.items()
            if _is_date(str(day))
        }
        clean_completions = {day: count for day, count in clean_completions.items() if count > 0}
        return {
            "title": title,
            "frequencyType": frequency,
            "targetCount": target_count,
            "startDate": start_date,
            "endDate": end_date,
            "completions": clean_completions,
            "time": time,
            "duration": duration,
            "color": color,
        }

    raise HTTPException(status_code=404, detail="Not found")


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _is_date(value: str) -> bool:
    if len(value) != 10:
        return False
    year, month, day = value.split("-") if value.count("-") == 2 else ("", "", "")
    return len(year) == 4 and len(month) == 2 and len(day) == 2 and year.isdigit() and month.isdigit() and day.isdigit()


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def _normalize_search_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = []
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("merged_by_type"), dict):
            for pan_type, entries in data["merged_by_type"].items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if isinstance(entry, dict):
                        raw_items.append({**entry, "pan_type": pan_type})
        if not raw_items:
            for key in ("data", "results", "items", "list"):
                if isinstance(payload.get(key), list):
                    raw_items = payload[key]
                    break
    else:
        raw_items = []

    results = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or item.get("filename") or item.get("file_name") or item.get("note") or "未命名资源"
        url = item.get("url") or item.get("link") or item.get("share_url") or item.get("shareUrl") or item.get("href") or ""
        if not url:
            continue
        results.append({
            "title": str(title),
            "url": str(url),
            "source": str(item.get("pan_type") or item.get("source") or item.get("site") or item.get("channel") or item.get("engine") or ""),
            "description": str(item.get("description") or item.get("desc") or item.get("summary") or item.get("content") or item.get("note") or ""),
            "size": str(item.get("size") or item.get("file_size") or ""),
            "time": str(item.get("time") or item.get("date") or item.get("datetime") or item.get("created_at") or item.get("updated_at") or ""),
            "raw": item,
        })
    return results


def _command_parts(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Hermes 命令配置无效，请检查 HERMES_DASHBOARD_COMMAND") from error


def _command_available(parts: list[str]) -> bool:
    if not parts:
        return False
    executable = Path(parts[0]).expanduser() if "/" in parts[0] else None
    return bool(executable and executable.exists()) or shutil.which(parts[0]) is not None


def _hermes_stream_command_parts() -> list[str]:
    try:
        return shlex.split(settings.hermes_stream_command)
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Hermes 流式命令配置无效，请检查 HERMES_STREAM_COMMAND") from error


def _hermes_chat_title(content: str) -> str:
    title = " ".join(content.strip().split())
    return (title[:30] + "…") if len(title) > 30 else title or "新的对话"


async def _get_hermes_stream_pool() -> HermesStreamPool:
    global _hermes_stream_pool
    parts = _hermes_stream_command_parts()
    if not parts:
        raise HTTPException(status_code=503, detail="Hermes 流式聊天尚未配置，请设置 HERMES_STREAM_COMMAND")
    if not _command_available(parts):
        raise HTTPException(status_code=503, detail="Hermes 流式命令不可用，请检查 HERMES_STREAM_COMMAND")
    if _hermes_stream_pool is None:
        _hermes_stream_pool = HermesStreamPool(parts, settings.hermes_stream_pool_size)
    try:
        await _hermes_stream_pool.start()
    except (OSError, ValueError, json.JSONDecodeError, asyncio.TimeoutError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=f"Hermes worker 池启动失败：{error}") from error
    return _hermes_stream_pool


async def _warm_hermes_stream_pool() -> None:
    if not settings.hermes_stream_command:
        return
    try:
        await _get_hermes_stream_pool()
    except Exception as error:
        logger.warning("Hermes worker pool warm-up skipped: %s", error)


async def _start_hermes_stream(message: str, hermes_session_id: str = "", conversation_key: str = ""):
    status = _hermes_status()
    if not status.get("running"):
        raise HTTPException(status_code=503, detail="Hermes dashboard 尚未运行，请联系管理员启动")

    try:
        pool = await _get_hermes_stream_pool()
        lease = await pool.acquire(
            conversation_key or hermes_session_id or "new",
            timeout=settings.hermes_stream_pool_wait_timeout,
        )
    except asyncio.TimeoutError as error:
        raise HTTPException(status_code=503, detail="Hermes worker 池正忙，请稍后再试") from error

    try:
        await lease.send({
            "content": message,
            "hermesSessionId": hermes_session_id,
            "conversationKey": conversation_key,
        })
    except (BrokenPipeError, ConnectionResetError) as error:
        await lease.release(reusable=False)
        raise HTTPException(status_code=502, detail="Hermes 流式桥接启动失败") from error
    return lease


async def _stop_hermes_stream(process, reusable: bool = False) -> None:
    if isinstance(process, HermesStreamLease):
        await process.release(reusable=reusable)
        return
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, 15)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, 9)
        except ProcessLookupError:
            pass
        await process.wait()


def _parse_hermes_stream_record(raw: bytes) -> dict[str, str]:
    if not raw or len(raw) > 1_000_000:
        raise ValueError("invalid Hermes stream record size")
    record = json.loads(raw.decode("utf-8"))
    if not isinstance(record, dict) or record.get("type") not in {"started", "delta", "completed", "error"}:
        raise ValueError("invalid Hermes stream record")
    kind = record["type"]
    result = {"type": kind}
    if kind in {"delta", "completed"}:
        if not isinstance(record.get("content"), str):
            raise ValueError("invalid Hermes stream content")
        result["content"] = record["content"]
    if kind in {"started", "completed"}:
        result["hermesSessionId"] = str(record.get("hermesSessionId") or "")[:120]
    if kind == "error":
        result["error"] = str(record.get("error") or "Hermes 运行失败")[:500]
    return result


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _hermes_status(message: str = "") -> dict[str, Any]:
    start_parts = _command_parts(settings.hermes_dashboard_command)
    installed = _command_available(start_parts)
    configured = bool(settings.hermes_dashboard_url and start_parts)
    running = False
    details = ""
    if configured:
        try:
            status_url = f"{settings.hermes_dashboard_url}/api/status"
            request = urllib.request.Request(status_url, headers={"accept": "application/json"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=settings.hermes_dashboard_timeout) as response:
                running = 200 <= response.status < 500
        except urllib.error.HTTPError as error:
            running = error.code in {401, 403}
            details = f"HTTP {error.code}"
        except TimeoutError:
            details = "Hermes dashboard status probe timed out"
        except urllib.error.URLError as error:
            details = str(error.reason)
        except Exception as error:
            details = str(error)
    if not message:
        if not configured:
            message = "Hermes dashboard is not configured"
        elif not installed:
            message = "Hermes CLI is not installed or not on PATH"
        elif running:
            message = "Hermes dashboard is running"
        else:
            message = "Hermes dashboard is not reachable"
    return {
        "configured": configured,
        "installed": installed,
        "running": running,
        "dashboardUrl": settings.hermes_dashboard_url,
        "dashboardPublicUrl": settings.hermes_dashboard_public_path + "/",
        "message": message,
        "details": details,
    }


def _proxy_headers(headers: Any) -> dict[str, str]:
    blocked = {
        "accept-encoding",
        "connection",
        "content-length",
        "cookie",
        "host",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
    return {key: value for key, value in headers.items() if key.lower() not in blocked}


def _response_headers(headers: Any) -> dict[str, str]:
    blocked = {
        "connection",
        "content-encoding",
        "content-length",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
    return {key: value for key, value in headers.items() if key.lower() not in blocked}


def _hermes_ws_target(query: str) -> str:
    base = settings.hermes_dashboard_url.rstrip("/")
    if base.startswith("https://"):
        target = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        target = "ws://" + base[len("http://"):]
    else:
        target = base
    target += "/ws"
    if query:
        target += "?" + query
    return target


def _hermes_ws_target_for_path(path: str, query: str) -> str:
    base = settings.hermes_dashboard_url.rstrip("/")
    if base.startswith("https://"):
        target = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        target = "ws://" + base[len("http://"):]
    else:
        target = base
    target += path if path.startswith("/") else f"/{path}"
    if query:
        target += "?" + query
    return target


def _rewrite_hermes_html(raw: bytes) -> bytes:
    public_path = settings.hermes_dashboard_public_path
    script = f"<script>window.__HERMES_BASE_PATH__ = {json.dumps(public_path)};</script>"
    html = raw.decode("utf-8", errors="replace")
    html = html.replace('href="/', f'href="{public_path}/')
    html = html.replace('src="/', f'src="{public_path}/')
    html = html.replace('window.__HERMES_BASE_PATH__="";', f"window.__HERMES_BASE_PATH__={json.dumps(public_path)};")
    html = html.replace('window.__HERMES_BASE_PATH__ = "";', f"window.__HERMES_BASE_PATH__ = {json.dumps(public_path)};")
    if "__HERMES_BASE_PATH__" not in html:
        html = html.replace("<head>", f"<head>{script}", 1)
    asset_pattern = rf'((?:src|href)=")({re.escape(public_path)}/assets/[^"]+\.(?:js|css))(")'
    html = re.sub(asset_pattern, rf"\1\2?v=orbit-hermes-proxy-20260707\3", html)
    return html.encode("utf-8")


def _rewrite_hermes_javascript(raw: bytes) -> bytes:
    public_path = settings.hermes_dashboard_public_path
    script = raw.decode("utf-8", errors="replace")
    script = script.replace("window.__HERMES_BASE_PATH__??``", json.dumps(public_path))
    return script.encode("utf-8")


def _rewrite_hermes_css(raw: bytes) -> bytes:
    public_path = settings.hermes_dashboard_public_path
    css = raw.decode("utf-8", errors="replace")
    css = css.replace("url(/", f"url({public_path}/")
    return css.encode("utf-8")


@app.get("/api/auth/me")
def auth_me(request: Request):
    return public_user(require_user(request))


@app.post("/api/auth/playcaptcha")
def auth_playcaptcha():
    return {"token": issue_playcaptcha_token()}


@app.post("/api/auth/register", status_code=201)
async def auth_register(request: Request, response: Response):
    data = await request.json()
    require_playcaptcha_token(str(data.get("playcaptchaToken") or ""))
    user = create_user(data.get("username", ""), data.get("password", ""))
    set_auth_cookies(response, user)
    return public_user(user)


@app.post("/api/auth/login")
async def auth_login(request: Request, response: Response):
    data = await request.json()
    require_playcaptcha_token(str(data.get("playcaptchaToken") or ""))
    username, password = validate_credentials_input(data.get("username", ""), data.get("password", ""))
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码不正确")
    ensure_user_active(user)
    touch_login(user["id"])
    user["last_login_at"] = user.get("last_login_at") or ""
    set_auth_cookies(response, user)
    return public_user(user)


@app.post("/api/auth/refresh")
def auth_refresh(request: Request, response: Response):
    return public_user(refresh_user(request, response))


@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response):
    revoke_refresh_token(request.cookies.get("orbit_refresh", ""))
    clear_auth_cookies(response)
    return {"ok": True}


@app.get("/api/netdisk/search")
def netdisk_search(request: Request, kw: str = "", page: int = 1):
    require_permission(request, "netdisk:search")
    keyword = kw.strip()
    if not keyword:
        raise HTTPException(status_code=422, detail="请输入搜索关键词")
    if len(keyword) > 80:
        raise HTTPException(status_code=422, detail="关键词太长了，先缩短一点再搜")

    query = urllib.parse.urlencode({"kw": keyword, "page": max(1, int(page or 1))})
    target = f"{settings.pansou_base_url}/api/search?{query}"
    search_request = urllib.request.Request(target, headers={
        "accept": "application/json",
        "user-agent": "OrbitPersonalHub/1.0",
    })
    try:
        with urllib.request.urlopen(search_request, timeout=settings.pansou_timeout) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read(2_000_000)
    except urllib.error.HTTPError as error:
        if error.code in {403, 429, 503}:
            raise HTTPException(status_code=502, detail="PanSou 搜索服务暂时不可用，请检查 PANSOU_BASE_URL") from error
        raise HTTPException(status_code=502, detail=f"搜索服务返回异常：HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise HTTPException(status_code=502, detail=f"暂时连接不上搜索服务：{error.reason}") from error
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="搜索服务响应超时") from error

    text = raw.decode("utf-8", errors="replace")
    if "application/json" not in content_type and text.lstrip().startswith("<"):
        raise HTTPException(status_code=502, detail="搜索服务返回了网页挑战页，请检查 PANSOU_BASE_URL")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail="搜索服务返回的数据格式不是 JSON") from error

    return {
        "keyword": keyword,
        "source": settings.pansou_base_url,
        "results": _normalize_search_results(payload),
        "raw": payload,
    }


@app.get("/api/agents/hermes/status")
def hermes_agent_status(request: Request):
    require_permission(request, "agents:manage")
    return _hermes_status()


@app.post("/api/agents/hermes/start")
def hermes_agent_start(request: Request):
    require_permission(request, "agents:manage")
    parts = _command_parts(settings.hermes_dashboard_command)
    if not _command_available(parts):
        raise HTTPException(status_code=503, detail="Hermes CLI 未安装或不在 PATH 中")
    try:
        subprocess.Popen(parts, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        raise HTTPException(status_code=503, detail=f"Hermes dashboard 启动失败：{error}") from error
    time.sleep(min(2.0, max(0.2, settings.hermes_dashboard_timeout / 3)))
    return _hermes_status("Hermes dashboard start command has been sent")


@app.post("/api/agents/hermes/stop")
def hermes_agent_stop(request: Request):
    require_permission(request, "agents:manage")
    parts = _command_parts(settings.hermes_dashboard_stop_command)
    if not _command_available(parts):
        raise HTTPException(status_code=503, detail="Hermes CLI 未安装或不在 PATH 中")
    try:
        subprocess.run(parts, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=settings.hermes_dashboard_timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise HTTPException(status_code=504, detail="Hermes dashboard 停止命令超时") from error
    time.sleep(0.5)
    return _hermes_status("Hermes dashboard stop command has been sent")


@app.api_route("/hermes-dashboard", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@app.api_route("/hermes-dashboard/{proxy_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def hermes_dashboard_proxy(request: Request, proxy_path: str = ""):
    require_permission(request, "agents:manage")
    if not _hermes_status().get("running"):
        raise HTTPException(status_code=503, detail="Hermes dashboard 尚未运行，请先在管理员页面启动")

    suffix = "/" + proxy_path if proxy_path else "/"
    target = f"{settings.hermes_dashboard_url}{suffix}"
    if request.url.query:
        target = f"{target}?{request.url.query}"

    data = None if request.method in {"GET", "HEAD"} else await request.body()
    upstream_request = urllib.request.Request(target, data=data, headers=_proxy_headers(request.headers), method=request.method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(upstream_request, timeout=settings.hermes_dashboard_timeout) as upstream:
            raw = upstream.read()
            status = upstream.status
            headers = _response_headers(upstream.headers)
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
        headers = _response_headers(error.headers)
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="Hermes dashboard 响应超时") from error
    except urllib.error.URLError as error:
        raise HTTPException(status_code=502, detail=f"暂时连接不上 Hermes dashboard：{error.reason}") from error

    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    if "text/html" in content_type:
        raw = _rewrite_hermes_html(raw)
        headers.pop("Content-Length", None)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store"
    elif "javascript" in content_type:
        raw = _rewrite_hermes_javascript(raw)
        headers.pop("Content-Length", None)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store"
    elif "text/css" in content_type:
        raw = _rewrite_hermes_css(raw)
        headers.pop("Content-Length", None)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store"
    return Response(content=raw, status_code=status, headers=headers)


@app.websocket("/hermes-dashboard/ws")
async def hermes_dashboard_ws_proxy(websocket: WebSocket):
    try:
        require_permission(websocket, "agents:manage")  # type: ignore[arg-type]
    except HTTPException:
        await websocket.close(code=1008)
        return

    if not _hermes_status().get("running"):
        await websocket.close(code=1013)
        return

    await websocket.accept()
    target = _hermes_ws_target(websocket.url.query)
    upstream_headers = []
    if "user-agent" in websocket.headers:
        upstream_headers.append(("user-agent", websocket.headers["user-agent"]))

    try:
        async with websockets.connect(
            target,
            additional_headers=upstream_headers,
            open_timeout=settings.hermes_dashboard_timeout,
            ping_interval=None,
            max_size=None,
        ) as upstream:
            async def client_to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    msg_type = message.get("type")
                    if msg_type == "websocket.disconnect":
                        break
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])

            async def upstream_to_client() -> None:
                while True:
                    message = await upstream.recv()
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=1011)


async def _proxy_hermes_websocket(websocket: WebSocket, upstream_path: str) -> None:
    try:
        require_permission(websocket, "agents:manage")  # type: ignore[arg-type]
    except HTTPException:
        await websocket.close(code=1008)
        return

    if not _hermes_status().get("running"):
        await websocket.close(code=1013)
        return

    await websocket.accept()
    target = _hermes_ws_target_for_path(upstream_path, websocket.url.query)
    upstream_headers = []
    if "user-agent" in websocket.headers:
        upstream_headers.append(("user-agent", websocket.headers["user-agent"]))

    try:
        async with websockets.connect(
            target,
            additional_headers=upstream_headers,
            open_timeout=settings.hermes_dashboard_timeout,
            ping_interval=None,
            max_size=None,
        ) as upstream:
            async def client_to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    msg_type = message.get("type")
                    if msg_type == "websocket.disconnect":
                        break
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])

            async def upstream_to_client() -> None:
                while True:
                    message = await upstream.recv()
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=1011)


@app.websocket("/hermes-dashboard/api/ws")
async def hermes_dashboard_api_ws_proxy(websocket: WebSocket):
    await _proxy_hermes_websocket(websocket, "/api/ws")


@app.websocket("/hermes-dashboard/api/pty")
async def hermes_dashboard_api_pty_proxy(websocket: WebSocket):
    await _proxy_hermes_websocket(websocket, "/api/pty")


@app.websocket("/hermes-dashboard/api/events")
async def hermes_dashboard_api_events_proxy(websocket: WebSocket):
    await _proxy_hermes_websocket(websocket, "/api/events")


async def _hermes_stream_records(process):
    assert process.stdout is not None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.hermes_chat_timeout if settings.hermes_chat_timeout > 0 else None
    while True:
        remaining = deadline - loop.time() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise asyncio.TimeoutError
        try:
            raw = await asyncio.wait_for(process.stdout.readline(), timeout=min(15, remaining) if remaining is not None else 15)
        except asyncio.TimeoutError:
            if deadline is not None and loop.time() >= deadline:
                raise
            yield None
            continue
        if not raw:
            raise EOFError("Hermes stream ended")
        record = _parse_hermes_stream_record(raw)
        yield record
        if record["type"] in {"completed", "error"}:
            return


def _persist_interrupted_hermes_message(
    conversation_id: str,
    user_id: str,
    title: str,
    hermes_session_id: str,
    chunks: list[str],
) -> None:
    content = "".join(chunks)
    if not content:
        return
    add_hermes_message(conversation_id, user_id, "assistant", content, status="interrupted")
    update_hermes_conversation_after_message(conversation_id, title, hermes_session_id)


def _finish_hermes_generation(conversation_id: str, process, lock_context) -> None:
    if _hermes_active_streams.get(conversation_id) is process:
        _hermes_active_streams.pop(conversation_id, None)
    _hermes_stop_requests.discard(conversation_id)
    lock_context.__exit__(None, None, None)


def _track_hermes_background_task(coro) -> None:
    task = asyncio.create_task(coro)
    _hermes_background_tasks.add(task)

    def done(completed: asyncio.Task) -> None:
        _hermes_background_tasks.discard(completed)
        if not completed.cancelled() and completed.exception() is not None:
            logger.error("Hermes background generation failed: %s", completed.exception())

    task.add_done_callback(done)


async def _finish_hermes_stream_in_background(
    process,
    lock_context,
    conversation_id: str,
    user_id: str,
    title: str,
    hermes_session_id: str,
    chunks: list[str],
) -> None:
    terminal = False
    timed_out = False
    try:
        async for record in _hermes_stream_records(process):
            if record is None:
                continue
            kind = record["type"]
            if kind == "started":
                hermes_session_id = record["hermesSessionId"] or hermes_session_id
                update_hermes_conversation_after_message(conversation_id, title, hermes_session_id)
            elif kind == "delta":
                chunks.append(record["content"])
            elif kind == "completed":
                hermes_session_id = record["hermesSessionId"] or hermes_session_id
                content = "".join(chunks) or record["content"]
                if content.strip():
                    add_hermes_message(conversation_id, user_id, "assistant", content)
                    update_hermes_conversation_after_message(conversation_id, title, hermes_session_id)
                terminal = True
            else:
                terminal = True
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        timed_out = True
    except (EOFError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        pass
    finally:
        stopped = conversation_id in _hermes_stop_requests
        await asyncio.shield(_stop_hermes_stream(process, reusable=terminal and not stopped))
        if (stopped or (not terminal and not timed_out)) and chunks:
            _persist_interrupted_hermes_message(conversation_id, user_id, title, hermes_session_id, chunks)
        _finish_hermes_generation(conversation_id, process, lock_context)


async def _hermes_chat_stream_events(
    process,
    lock_context,
    conversation_id: str,
    user_id: str,
    title: str,
    hermes_session_id: str,
    user_message: dict[str, Any],
    conversation: dict[str, Any],
):
    chunks: list[str] = []
    terminal = False
    settled = False
    detached = False
    try:
        yield _sse_event("started", {"conversation": conversation, "userMessage": user_message})
        async for record in _hermes_stream_records(process):
            if record is None:
                yield ": keep-alive\n\n"
                continue
            kind = record["type"]
            if kind == "started":
                hermes_session_id = record["hermesSessionId"] or hermes_session_id
                update_hermes_conversation_after_message(conversation_id, title, hermes_session_id)
            elif kind == "delta":
                chunks.append(record["content"])
                yield _sse_event("delta", {"content": record["content"]})
            elif kind == "completed":
                hermes_session_id = record["hermesSessionId"] or hermes_session_id
                content = "".join(chunks) or record["content"]
                if not content.strip():
                    settled = True
                    terminal = True
                    yield _sse_event("error", {"status": 502, "detail": "Hermes 没有返回可显示的回复"})
                    continue
                assistant_message = add_hermes_message(
                    conversation_id,
                    user_id,
                    "assistant",
                    content,
                )
                updated = update_hermes_conversation_after_message(
                    conversation_id,
                    title,
                    hermes_session_id,
                )
                settled = True
                terminal = True
                if not chunks:
                    yield _sse_event("delta", {"content": content})
                yield _sse_event("completed", {"conversation": updated, "message": assistant_message})
            else:
                settled = True
                terminal = True
                yield _sse_event("error", {"status": 502, "detail": record["error"]})
    except (asyncio.CancelledError, GeneratorExit):
        detached = not settled and conversation_id not in _hermes_stop_requests
        raise
    except asyncio.TimeoutError:
        settled = True
        yield _sse_event("error", {"status": 504, "detail": "Hermes 聊天响应超时"})
    except EOFError:
        settled = True
        yield _sse_event("error", {"status": 502, "detail": "Hermes 流式连接意外结束"})
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        settled = True
        yield _sse_event("error", {"status": 502, "detail": "Hermes 流式响应格式无效"})
    finally:
        if detached:
            _track_hermes_background_task(
                _finish_hermes_stream_in_background(
                    process,
                    lock_context,
                    conversation_id,
                    user_id,
                    title,
                    hermes_session_id,
                    chunks,
                )
            )
        else:
            stopped = conversation_id in _hermes_stop_requests
            await asyncio.shield(_stop_hermes_stream(process, reusable=terminal and not stopped))
            if stopped and chunks:
                _persist_interrupted_hermes_message(conversation_id, user_id, title, hermes_session_id, chunks)
            _finish_hermes_generation(conversation_id, process, lock_context)


@app.get("/api/hermes-chat/conversations")
def hermes_chat_conversations(request: Request):
    user = require_permission(request, "hermes:chat")
    return list_hermes_conversations(user["id"])


@app.post("/api/hermes-chat/conversations", status_code=201)
async def hermes_chat_create_conversation(request: Request):
    user = require_permission(request, "hermes:chat")
    data = await request.json()
    return create_hermes_conversation(user["id"], str(data.get("title") or ""))


@app.get("/api/hermes-chat/conversations/{conversation_id}")
def hermes_chat_conversation(conversation_id: str, request: Request):
    user = require_permission(request, "hermes:chat")
    conversation = get_hermes_conversation(conversation_id, user["id"])
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {
        **conversation,
        "messages": list_hermes_messages(conversation_id),
        "generating": conversation_id in _hermes_active_streams,
    }


@app.post("/api/hermes-chat/conversations/{conversation_id}/messages/stream")
async def hermes_chat_stream_message(conversation_id: str, request: Request):
    user = require_permission(request, "hermes:chat")
    conversation = get_hermes_conversation(conversation_id, user["id"])
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    data = await request.json()
    content = str(data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息不能为空")
    if len(content) > 8000:
        raise HTTPException(status_code=422, detail="消息太长了，请缩短后再发送")

    lock_context = hermes_chat_user_lock(user["id"])
    if not lock_context.__enter__():
        lock_context.__exit__(None, None, None)
        raise HTTPException(status_code=409, detail="已有 Hermes 回答正在生成，请先等待或停止")

    process = None
    try:
        hermes_session_id = conversation.get("hermesSessionId") or ""
        process = await _start_hermes_stream(content, hermes_session_id, conversation_id)
        user_message = add_hermes_message(conversation_id, user["id"], "user", content)
        title = _hermes_chat_title(content) if conversation.get("title") == "新的对话" else conversation["title"]
        updated = update_hermes_conversation_after_message(conversation_id, title, hermes_session_id)
        _hermes_active_streams[conversation_id] = process
    except Exception:
        if process is not None:
            await _stop_hermes_stream(process)
        lock_context.__exit__(None, None, None)
        raise

    return StreamingResponse(
        _hermes_chat_stream_events(
            process,
            lock_context,
            conversation_id,
            user["id"],
            title,
            hermes_session_id,
            user_message,
            updated,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/hermes-chat/conversations/{conversation_id}/messages/stop")
async def hermes_chat_stop_message(conversation_id: str, request: Request):
    user = require_permission(request, "hermes:chat")
    if not get_hermes_conversation(conversation_id, user["id"]):
        raise HTTPException(status_code=404, detail="对话不存在")
    process = _hermes_active_streams.get(conversation_id)
    if process is None:
        raise HTTPException(status_code=409, detail="这条对话当前没有正在生成的回答")
    _hermes_stop_requests.add(conversation_id)
    await _stop_hermes_stream(process, reusable=False)
    return {"ok": True}


@app.delete("/api/hermes-chat/conversations/{conversation_id}")
def hermes_chat_delete_conversation(conversation_id: str, request: Request):
    user = require_permission(request, "hermes:chat")
    result = soft_delete_hermes_conversation(conversation_id, user["id"])
    if not result["ok"]:
        raise HTTPException(status_code=404, detail="对话不存在")
    return result


@app.get("/api/admin/hermes-chat/conversations")
def admin_hermes_chat_conversations(request: Request):
    require_permission(request, "users:manage")
    return list_admin_hermes_conversations()


@app.get("/api/admin/hermes-chat/conversations/{conversation_id}")
def admin_hermes_chat_conversation(conversation_id: str, request: Request):
    require_permission(request, "users:manage")
    conversation = get_hermes_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {**conversation, "messages": list_hermes_messages(conversation_id)}


@app.delete("/api/admin/hermes-chat/conversations/{conversation_id}")
def admin_hermes_chat_delete_conversation(conversation_id: str, request: Request):
    require_permission(request, "users:manage")
    result = soft_delete_hermes_conversation(conversation_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail="对话不存在")
    return result


@app.get("/api/admin/users")
def admin_users(request: Request):
    require_permission(request, "users:manage")
    return list_users()


@app.patch("/api/admin/users/{user_id}/roles")
async def admin_update_user_roles(user_id: str, request: Request):
    require_permission(request, "users:manage")
    data = await request.json()
    roles = data.get("roles") if isinstance(data.get("roles"), list) else []
    return set_user_roles(user_id, roles)


@app.patch("/api/admin/users/{user_id}/ban")
async def admin_update_user_ban(user_id: str, request: Request):
    require_permission(request, "users:manage")
    data = await request.json()
    return set_user_banned(user_id, bool(data.get("banned")))


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str, request: Request):
    require_permission(request, "users:manage")
    return delete_user_account(user_id)


@app.get("/api/admin/roles")
def admin_roles(request: Request):
    require_permission(request, "roles:manage")
    return list_roles()


@app.get("/api/admin/permissions")
def admin_permissions(request: Request):
    require_permission(request, "roles:manage")
    return list_permissions()


@app.get("/api/{collection}")
def api_list(collection: str, request: Request):
    require_permission(request, "content:read")
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
    return list_items(collection)


@app.post("/api/{collection}", status_code=201)
async def api_create(collection: str, request: Request):
    require_permission(request, "content:write")
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
    valid = validate(collection, await request.json())
    if collection == "folders" and folder_exists(valid["name"]):
        raise HTTPException(status_code=409, detail="这个收藏夹已经存在")
    return create_item(collection, valid)


@app.patch("/api/{collection}/{item_id}")
async def api_update(collection: str, item_id: str, request: Request):
    require_permission(request, "content:write")
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
    existing = get_item(collection, item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="记录不存在")
    data = await request.json()
    if collection == "folders" and "sortOrder" in data:
        require_permission(request, "folders:manage")
    valid = validate(collection, {**existing, **data})
    return update_item(collection, item_id, valid)


@app.delete("/api/{collection}/{item_id}")
def api_delete(collection: str, item_id: str, request: Request):
    require_permission(request, "content:write")
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
    if collection == "folders":
        require_permission(request, "folders:manage")
    existing = get_item(collection, item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="记录不存在")
    if collection == "folders" and folder_has_bookmarks(existing["name"]):
        raise HTTPException(status_code=409, detail="请先移动收藏夹内的网站")
    return delete_item(collection, item_id)


app.mount("/assets", StaticFiles(directory=PUBLIC_DIR), name="assets")


@app.get("/")
def index():
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/{path_name:path}")
def static_file(path_name: str):
    target = (PUBLIC_DIR / path_name).resolve()
    public_root = PUBLIC_DIR.resolve()
    if not str(target).startswith(str(public_root)) or not target.is_file():
        target = PUBLIC_DIR / "index.html"
    return FileResponse(target)
