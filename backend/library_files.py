import codecs
import os
import posixpath
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from .config import settings


BOOK_CONTENT_TYPES = {
    "epub": "application/epub+zip",
    "pdf": "application/pdf",
    "mobi": "application/x-mobipocket-ebook",
    "azw3": "application/vnd.amazon.ebook",
    "txt": "text/plain; charset=utf-8",
}
COVER_CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
_CHUNK_SIZE = 1024 * 1024
_EPUB_XML_LIMIT = 1024 * 1024


def ensure_library_storage() -> None:
    for directory in (books_dir(), covers_dir(), temp_dir()):
        directory.mkdir(parents=True, exist_ok=True)


def books_dir() -> Path:
    return settings.library_storage_dir / "books"


def covers_dir() -> Path:
    return settings.library_storage_dir / "covers"


def temp_dir() -> Path:
    return settings.library_storage_dir / "tmp"


def _safe_child(root: Path, filename: str) -> Path:
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="文件不存在")
    root = root.resolve()
    target = (root / filename).resolve()
    if target.parent != root:
        raise HTTPException(status_code=404, detail="文件不存在")
    return target


def book_path(filename: str) -> Path:
    return _safe_child(books_dir(), filename)


def cover_path(filename: str) -> Path:
    return _safe_child(covers_dir(), filename)


def temporary_path() -> Path:
    ensure_library_storage()
    return _safe_child(temp_dir(), f"{uuid.uuid4()}.part")


async def save_upload(upload: UploadFile, target: Path, max_bytes: int, label: str) -> int:
    size = 0
    try:
        with target.open("xb") as output:
            while chunk := await upload.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail=f"{label}大小超过限制")
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail=f"{label}不能为空")
        return size
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def detect_book_format(path: Path, original_filename: str) -> str:
    extension = Path(original_filename or "").suffix.lower().lstrip(".")
    if extension not in BOOK_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="仅支持 EPUB、PDF、MOBI、AZW3 和 TXT")

    with path.open("rb") as source:
        head = source.read(65536)
    valid = False
    if extension == "pdf":
        valid = head.startswith(b"%PDF-")
    elif extension == "epub":
        try:
            with zipfile.ZipFile(path) as archive:
                info = archive.getinfo("mimetype")
                valid = info.file_size <= 100 and archive.read(info) == b"application/epub+zip"
        except (KeyError, OSError, zipfile.BadZipFile):
            valid = False
    elif extension in {"mobi", "azw3"}:
        valid = len(head) >= 68 and head[60:68] == b"BOOKMOBI"
    elif extension == "txt":
        try:
            decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
            has_text = False
            with path.open("rb") as source:
                while chunk := source.read(_CHUNK_SIZE):
                    if b"\x00" in chunk:
                        raise UnicodeDecodeError("utf-8", chunk, 0, 1, "NUL byte")
                    has_text = has_text or bool(decoder.decode(chunk).strip())
                has_text = has_text or bool(decoder.decode(b"", final=True).strip())
            valid = has_text
        except UnicodeDecodeError:
            valid = False
    if not valid:
        raise HTTPException(status_code=415, detail="文件内容与电子书格式不匹配")
    return extension


def detect_cover_bytes(head: bytes) -> tuple[str, str]:
    if head.startswith(b"\xff\xd8\xff"):
        extension = "jpg"
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = "png"
    elif len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        extension = "webp"
    else:
        raise HTTPException(status_code=415, detail="封面仅支持 JPEG、PNG 和 WebP")
    return extension, COVER_CONTENT_TYPES[extension]


def detect_cover(path: Path) -> tuple[str, str]:
    with path.open("rb") as source:
        return detect_cover_bytes(source.read(16))


def metadata_from_filename(original_filename: str) -> dict[str, str]:
    stem = re.sub(r"\s+", " ", Path(original_filename or "").stem).strip()
    if not stem:
        return {"title": "", "author": ""}
    quoted = re.fullmatch(r"《(.+?)》(?:\s*[-—–]\s*|\s+)(.+)", stem)
    if quoted:
        return {"title": quoted.group(1).strip(), "author": quoted.group(2).strip()}
    separated = re.fullmatch(r"(.+?)\s+[-—–]\s+(.+)", stem)
    if separated:
        return {"title": separated.group(1).strip(), "author": separated.group(2).strip()}
    return {"title": stem, "author": ""}


def _xml_text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def _local_name(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _zip_read_limited(archive: zipfile.ZipFile, member: str, limit: int) -> bytes:
    try:
        info = archive.getinfo(member)
    except KeyError:
        return b""
    if info.file_size > limit:
        return b""
    with archive.open(info) as source:
        data = source.read(limit + 1)
    return data if len(data) <= limit else b""


def _epub_member(package_name: str, href: str) -> str:
    decoded = unquote(str(href or "").split("#", 1)[0])
    if not decoded or "\\" in decoded:
        return ""
    member = posixpath.normpath(posixpath.join(posixpath.dirname(package_name), decoded))
    if member.startswith("../") or member in {"..", "."} or member.startswith("/"):
        return ""
    return member


def _epub_metadata(path: Path, max_cover_bytes: int) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            container_data = _zip_read_limited(archive, "META-INF/container.xml", _EPUB_XML_LIMIT)
            if not container_data:
                return {}
            container = ElementTree.fromstring(container_data)
            rootfile = next((item for item in container.iter() if _local_name(item) == "rootfile"), None)
            package_name = rootfile.get("full-path", "") if rootfile is not None else ""
            package_data = _zip_read_limited(archive, package_name, _EPUB_XML_LIMIT)
            if not package_data:
                return {}
            package = ElementTree.fromstring(package_data)
            titles = [_xml_text(item) for item in package.iter() if _local_name(item) == "title"]
            creators = [_xml_text(item) for item in package.iter() if _local_name(item) == "creator"]
            manifest = [item for item in package.iter() if _local_name(item) == "item"]

            cover_id = ""
            cover_href = ""
            for item in package.iter():
                if _local_name(item) == "meta" and item.get("name", "").lower() == "cover":
                    cover_id = item.get("content", "")
                if _local_name(item) == "reference" and item.get("type", "").lower() == "cover":
                    cover_href = item.get("href", "")
            cover_item = next(
                (item for item in manifest if "cover-image" in item.get("properties", "").split()),
                None,
            )
            if cover_item is None and cover_id:
                cover_item = next((item for item in manifest if item.get("id") == cover_id), None)
            if cover_item is None and cover_href:
                cover_item = next((item for item in manifest if item.get("href") == cover_href), None)
            if cover_item is None:
                cover_item = next(
                    (
                        item for item in manifest
                        if item.get("media-type", "").startswith("image/")
                        and "cover" in f'{item.get("id", "")} {item.get("href", "")}'.lower()
                    ),
                    None,
                )

            result: dict[str, Any] = {
                "title": next((value for value in titles if value), ""),
                "author": " / ".join(value for value in creators if value),
            }
            if cover_item is not None:
                member = _epub_member(package_name, cover_item.get("href", ""))
                cover = _zip_read_limited(archive, member, max_cover_bytes) if member else b""
                if cover:
                    try:
                        extension, content_type = detect_cover_bytes(cover[:16])
                        result.update({
                            "coverBytes": cover,
                            "coverExtension": extension,
                            "coverContentType": content_type,
                        })
                    except HTTPException:
                        pass
            return result
    except (ElementTree.ParseError, KeyError, OSError, RuntimeError, ValueError, zipfile.BadZipFile):
        return {}


def _pdf_metadata(path: Path) -> dict[str, str]:
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted or reader.metadata is None:
            return {}
        return {
            "title": re.sub(r"\s+", " ", str(reader.metadata.title or "")).strip(),
            "author": re.sub(r"\s+", " ", str(reader.metadata.author or "")).strip(),
        }
    except Exception:
        return {}


def extract_book_metadata(
    path: Path,
    original_filename: str,
    file_format: str,
    max_cover_bytes: int,
) -> dict[str, Any]:
    result: dict[str, Any] = metadata_from_filename(original_filename)
    embedded: dict[str, Any] = {}
    if file_format == "epub":
        embedded = _epub_metadata(path, max_cover_bytes)
    elif file_format == "pdf":
        embedded = _pdf_metadata(path)
    for key in ("title", "author"):
        if embedded.get(key):
            result[key] = embedded[key]
    for key in ("coverBytes", "coverExtension", "coverContentType"):
        if embedded.get(key):
            result[key] = embedded[key]
    return result


def move_into_place(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)


def remove_file(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def clean_download_name(original_filename: str, title: str, file_format: str) -> str:
    name = Path(original_filename or "").name
    name = re.sub(r"[\x00-\x1f\x7f]+", "", name).strip().replace('"', "")
    wanted_suffix = f".{file_format}"
    if not name or Path(name).suffix.lower() != wanted_suffix:
        base = re.sub(r"[^\w\- .()\u4e00-\u9fff]+", "_", title, flags=re.UNICODE).strip(" ._") or "book"
        name = f"{base}{wanted_suffix}"
    if len(name) > 220:
        name = f"{Path(name).stem[:200]}{wanted_suffix}"
    return name
