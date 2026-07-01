from pathlib import Path
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import PUBLIC_DIR, settings
from .database import COLLECTIONS, initialize_database
from .repository import (
    create_item,
    delete_item,
    folder_exists,
    folder_has_bookmarks,
    get_item,
    list_items,
    update_item,
)


app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def validate(collection: str, input_data: dict[str, Any]) -> dict[str, Any]:
    item = dict(input_data or {})
    item.pop("id", None)
    item.pop("createdAt", None)

    if collection == "folders":
        name = str(item.get("name") or "").strip()[:30]
        if not name:
            raise HTTPException(status_code=422, detail="收藏夹名称不能为空")
        return {"name": name}

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


@app.get("/api/netdisk/search")
def netdisk_search(kw: str = "", page: int = 1):
    keyword = kw.strip()
    if not keyword:
        raise HTTPException(status_code=422, detail="请输入搜索关键词")
    if len(keyword) > 80:
        raise HTTPException(status_code=422, detail="关键词太长了，先缩短一点再搜")

    query = urllib.parse.urlencode({"kw": keyword, "page": max(1, int(page or 1))})
    target = f"{settings.pansou_base_url}/api/search?{query}"
    request = urllib.request.Request(target, headers={
        "accept": "application/json",
        "user-agent": "OrbitPersonalHub/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=settings.pansou_timeout) as response:
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


@app.get("/api/{collection}")
def api_list(collection: str):
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
    return list_items(collection)


@app.post("/api/{collection}", status_code=201)
async def api_create(collection: str, request: Request):
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
    valid = validate(collection, await request.json())
    if collection == "folders" and folder_exists(valid["name"]):
        raise HTTPException(status_code=409, detail="这个收藏夹已经存在")
    return create_item(collection, valid)


@app.patch("/api/{collection}/{item_id}")
async def api_update(collection: str, item_id: str, request: Request):
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
    existing = get_item(collection, item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="记录不存在")
    valid = validate(collection, {**existing, **await request.json()})
    return update_item(collection, item_id, valid)


@app.delete("/api/{collection}/{item_id}")
def api_delete(collection: str, item_id: str):
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not found")
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
