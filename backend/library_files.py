import codecs
import io
import math
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
import pypdfium2 as pdfium

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
_MOBI_RECORD0_LIMIT = 1024 * 1024
_MOBI_TEXT_LIMIT = 64 * 1024
_MOBI_EXTH_RECORD_LIMIT = 4096
_PDF_COVER_MAX_EDGE = 1600
_PDF_COVER_MAX_SCALE = 2.0
_PDF_COVER_QUALITY = 85


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


def _pdf_metadata(path: Path, max_cover_bytes: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        reader = PdfReader(path, strict=False)
        if not reader.is_encrypted and reader.metadata is not None:
            result.update({
                "title": re.sub(r"\s+", " ", str(reader.metadata.title or "")).strip(),
                "author": re.sub(r"\s+", " ", str(reader.metadata.author or "")).strip(),
            })
    except Exception:
        pass

    document = None
    page = None
    bitmap = None
    image = None
    try:
        document = pdfium.PdfDocument(path)
        if len(document) == 0:
            return result
        page = document[0]
        width, height = page.get_size()
        largest_edge = max(width, height)
        if not math.isfinite(largest_edge) or largest_edge <= 0:
            return result
        scale = min(_PDF_COVER_MAX_SCALE, _PDF_COVER_MAX_EDGE / largest_edge)
        bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 255))
        image = bitmap.to_pil().convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=_PDF_COVER_QUALITY, optimize=True)
        cover = output.getvalue()
        if 0 < len(cover) <= max_cover_bytes:
            result.update({
                "coverBytes": cover,
                "coverExtension": "jpg",
                "coverContentType": "image/jpeg",
            })
    except Exception:
        pass
    finally:
        if image is not None:
            image.close()
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        if document is not None:
            document.close()
    return result


def _big_endian(data: bytes, offset: int, size: int) -> int:
    end = offset + size
    if offset < 0 or size <= 0 or end > len(data):
        raise ValueError("binary field is out of bounds")
    return int.from_bytes(data[offset:end], "big")


def _pdb_record_offsets(path: Path) -> list[int]:
    file_size = path.stat().st_size
    with path.open("rb") as source:
        header = source.read(78)
        if len(header) != 78:
            raise ValueError("PalmDB header is incomplete")
        record_count = _big_endian(header, 76, 2)
        if record_count == 0:
            raise ValueError("PalmDB has no records")
        table_size = record_count * 8
        table = source.read(table_size)
    if len(table) != table_size or 78 + table_size > file_size:
        raise ValueError("PalmDB record table is incomplete")

    offsets = [_big_endian(table, index * 8, 4) for index in range(record_count)]
    table_end = 78 + table_size
    if offsets[0] < table_end or offsets[-1] >= file_size:
        raise ValueError("PalmDB record offset is out of bounds")
    if any(current >= following for current, following in zip(offsets, offsets[1:])):
        raise ValueError("PalmDB record offsets are not increasing")
    return [*offsets, file_size]


def _read_pdb_record(path: Path, offsets: list[int], index: int, limit: int) -> bytes:
    if index < 0 or index + 1 >= len(offsets):
        return b""
    size = offsets[index + 1] - offsets[index]
    if size <= 0 or size > limit:
        return b""
    with path.open("rb") as source:
        source.seek(offsets[index])
        data = source.read(size)
    return data if len(data) == size else b""


def _decode_mobi_text(data: bytes, encoding: int) -> str:
    if not data or len(data) > _MOBI_TEXT_LIMIT:
        return ""
    codec = "utf-8" if encoding == 65001 else "cp1252" if encoding == 1252 else "utf-8"
    return re.sub(r"\s+", " ", data.decode(codec, errors="replace").strip("\0")).strip()


def _azw3_metadata(path: Path, max_cover_bytes: int) -> dict[str, Any]:
    try:
        offsets = _pdb_record_offsets(path)
        record0 = _read_pdb_record(path, offsets, 0, _MOBI_RECORD0_LIMIT)
        if len(record0) < 128 or record0[16:20] != b"MOBI":
            return {}

        header_length = _big_endian(record0, 20, 4)
        if header_length < 112 or 16 + header_length > len(record0):
            return {}
        encoding = _big_endian(record0, 28, 4)
        # MOBI field offsets are relative to its header at record 0 byte 16.
        full_name_offset = _big_endian(record0, 16 + 68, 4)
        full_name_length = _big_endian(record0, 16 + 72, 4)
        first_image = _big_endian(record0, 16 + 92, 4)

        full_name = ""
        if full_name_length <= _MOBI_TEXT_LIMIT:
            full_name_end = full_name_offset + full_name_length
            if full_name_offset >= 0 and full_name_end <= len(record0):
                full_name = _decode_mobi_text(record0[full_name_offset:full_name_end], encoding)

        authors: list[str] = []
        updated_title = ""
        cover_offset: int | None = None
        exth_offset = 16 + header_length
        if record0[exth_offset:exth_offset + 4] == b"EXTH":
            exth_length = _big_endian(record0, exth_offset + 4, 4)
            exth_count = _big_endian(record0, exth_offset + 8, 4)
            exth_end = exth_offset + exth_length
            if exth_length < 12 or exth_end > len(record0) or exth_count > _MOBI_EXTH_RECORD_LIMIT:
                raise ValueError("EXTH header is invalid")
            cursor = exth_offset + 12
            for _ in range(exth_count):
                record_type = _big_endian(record0, cursor, 4)
                record_length = _big_endian(record0, cursor + 4, 4)
                record_end = cursor + record_length
                if record_length < 8 or record_end > exth_end:
                    raise ValueError("EXTH record is invalid")
                value = record0[cursor + 8:record_end]
                if record_type == 100:
                    author = _decode_mobi_text(value, encoding)
                    if author:
                        authors.append(author)
                elif record_type == 201 and len(value) >= 4:
                    cover_offset = int.from_bytes(value[:4], "big")
                elif record_type == 503 and not updated_title:
                    updated_title = _decode_mobi_text(value, encoding)
                cursor = record_end

        result: dict[str, Any] = {
            "title": updated_title or full_name,
            "author": " / ".join(authors),
        }
        if first_image != 0xFFFFFFFF and cover_offset is not None:
            cover = _read_pdb_record(path, offsets, first_image + cover_offset, max_cover_bytes)
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
    except (OSError, ValueError):
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
        embedded = _pdf_metadata(path, max_cover_bytes)
    elif file_format == "azw3":
        embedded = _azw3_metadata(path, max_cover_bytes)
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
