import asyncio
import io
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, UploadFile
from pypdf import PdfWriter

import backend.main as main_module
import backend.repository as repository_module
from backend.config import settings
from backend.library_files import (
    book_path,
    clean_download_name,
    cover_path,
    detect_book_format,
    detect_cover,
    ensure_library_storage,
    extract_book_metadata,
    metadata_from_filename,
    save_upload,
)


class FakeRequest:
    def __init__(self, payload=None):
        self.payload = payload or {}

    async def json(self):
        return self.payload


def assert_http(status: int, action) -> None:
    try:
        action()
        raise AssertionError(f"expected HTTP {status}")
    except HTTPException as error:
        assert error.status_code == status


def epub_bytes(title: str = "内嵌书名", author: str = "内嵌作者") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        archive.writestr(
            "OPS/content.opf",
            f'''<?xml version="1.0"?>
            <package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">
              <metadata><dc:title>{title}</dc:title><dc:creator>{author}</dc:creator></metadata>
              <manifest><item id="cover" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/></manifest>
            </package>''',
        )
        archive.writestr("OPS/images/cover.jpg", b"\xff\xd8\xff\xe0embedded-cover")
    return buffer.getvalue()


def pdf_bytes(title: str = "PDF 内嵌书名", author: str = "PDF 内嵌作者") -> bytes:
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": title, "/Author": author})
    writer.write(buffer)
    return buffer.getvalue()


def test_file_validation(root: Path) -> None:
    pdf = root / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7\nexample")
    assert detect_book_format(pdf, "book.pdf") == "pdf"

    epub = root / "book.epub"
    epub.write_bytes(epub_bytes())
    assert detect_book_format(epub, "book.epub") == "epub"

    mobi = root / "book.mobi"
    mobi.write_bytes(b"\0" * 60 + b"BOOKMOBI" + b"body")
    assert detect_book_format(mobi, "book.mobi") == "mobi"
    assert detect_book_format(mobi, "book.azw3") == "azw3"

    text = root / "book.txt"
    text.write_text("一本书", encoding="utf-8")
    assert detect_book_format(text, "book.txt") == "txt"

    invalid_text = root / "invalid.txt"
    invalid_text.write_bytes(b"a" * 70000 + b"\xff")
    assert_http(415, lambda: detect_book_format(invalid_text, "invalid.txt"))

    bad = root / "fake.pdf"
    bad.write_text("not a pdf", encoding="utf-8")
    assert_http(415, lambda: detect_book_format(bad, "fake.pdf"))

    jpeg = root / "cover.bin"
    jpeg.write_bytes(b"\xff\xd8\xff\xe0cover")
    assert detect_cover(jpeg) == ("jpg", "image/jpeg")
    png = root / "cover.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\ncontent")
    assert detect_cover(png) == ("png", "image/png")
    webp = root / "cover.webp"
    webp.write_bytes(b"RIFF\x00\x00\x00\x00WEBPcontent")
    assert detect_cover(webp) == ("webp", "image/webp")


def test_metadata_extraction(root: Path) -> None:
    assert metadata_from_filename("《活着》 余华.epub") == {"title": "活着", "author": "余华"}
    assert metadata_from_filename("百年孤独 - 加西亚·马尔克斯.pdf") == {
        "title": "百年孤独",
        "author": "加西亚·马尔克斯",
    }
    assert metadata_from_filename("只有书名.txt") == {"title": "只有书名", "author": ""}

    epub = root / "filename - fallback.epub"
    epub.write_bytes(epub_bytes())
    metadata = extract_book_metadata(epub, epub.name, "epub", 1024)
    assert metadata["title"] == "内嵌书名"
    assert metadata["author"] == "内嵌作者"
    assert metadata["coverBytes"] == b"\xff\xd8\xff\xe0embedded-cover"
    assert metadata["coverContentType"] == "image/jpeg"
    assert "coverBytes" not in extract_book_metadata(epub, epub.name, "epub", 4)

    malformed = root / "malformed.epub"
    with zipfile.ZipFile(malformed, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<not-closed")
    assert extract_book_metadata(malformed, "回退书名 - 回退作者.epub", "epub", 1024) == {
        "title": "回退书名",
        "author": "回退作者",
    }

    pdf = root / "文件名 - 文件作者.pdf"
    pdf.write_bytes(pdf_bytes())
    metadata = extract_book_metadata(pdf, pdf.name, "pdf", 1024)
    assert metadata["title"] == "PDF 内嵌书名"
    assert metadata["author"] == "PDF 内嵌作者"


def test_storage_and_upload(root: Path) -> None:
    original_storage = settings.library_storage_dir
    settings.library_storage_dir = root / "library"
    try:
        ensure_library_storage()
        assert book_path("safe.pdf").parent == (root / "library" / "books").resolve()
        assert cover_path("safe.png").parent == (root / "library" / "covers").resolve()
        assert_http(404, lambda: book_path("../escape.pdf"))
        assert clean_download_name("../../name.pdf", "书名", "pdf") == "name.pdf"
        assert clean_download_name("bad.exe", "书名", "epub").endswith(".epub")

        target = root / "upload.part"
        upload = UploadFile(filename="book.txt", file=io.BytesIO("内容".encode()))
        assert asyncio.run(save_upload(upload, target, 100, "电子书")) == len("内容".encode())
        assert target.read_text(encoding="utf-8") == "内容"

        too_large = root / "large.part"
        upload = UploadFile(filename="large.txt", file=io.BytesIO(b"12345"))
        try:
            asyncio.run(save_upload(upload, too_large, 4, "电子书"))
            raise AssertionError("oversized upload must fail")
        except HTTPException as error:
            assert error.status_code == 413
        assert not too_large.exists()
    finally:
        settings.library_storage_dir = original_storage


def test_upload_route_cleanup(root: Path) -> None:
    original_storage = settings.library_storage_dir
    original_require = main_module.require_permission
    original_create = main_module.create_book
    created = {}

    def require_upload(_request, permission):
        assert permission == "library:upload"
        return {"id": "u1", "username": "alice"}

    def capture_book(book, user_id):
        assert user_id == "u1"
        created.update(book)
        return book

    async def upload() -> dict:
        return await main_module.library_upload_book(
            FakeRequest(),
            title="  测试书  ",
            author="作者",
            book_file=UploadFile(filename="source.pdf", file=io.BytesIO(pdf_bytes())),
            cover_file=UploadFile(filename="cover.jpg", file=io.BytesIO(b"\xff\xd8\xff\xe0cover")),
        )

    async def auto_upload() -> dict:
        return await main_module.library_upload_book(
            FakeRequest(),
            title="",
            author="",
            book_file=UploadFile(filename="错误文件名 - 错误作者.epub", file=io.BytesIO(epub_bytes())),
            cover_file=None,
        )

    try:
        settings.library_storage_dir = root / "success"
        main_module.require_permission = require_upload
        main_module.create_book = capture_book
        result = asyncio.run(upload())
        assert result["title"] == "测试书"
        assert book_path(created["storedFilename"]).read_bytes() == pdf_bytes()
        assert cover_path(created["coverFilename"]).read_bytes() == b"\xff\xd8\xff\xe0cover"
        assert not any((settings.library_storage_dir / "tmp").iterdir())

        settings.library_storage_dir = root / "auto"
        created.clear()
        result = asyncio.run(auto_upload())
        assert result["title"] == "内嵌书名"
        assert result["author"] == "内嵌作者"
        assert cover_path(created["coverFilename"]).read_bytes() == b"\xff\xd8\xff\xe0embedded-cover"
        assert not any((settings.library_storage_dir / "tmp").iterdir())

        settings.library_storage_dir = root / "failure"

        def fail_create(_book, _user_id):
            raise RuntimeError("database failure")

        main_module.create_book = fail_create
        try:
            asyncio.run(upload())
            raise AssertionError("database failure must propagate")
        except RuntimeError as error:
            assert str(error) == "database failure"
        assert not any((settings.library_storage_dir / "books").iterdir())
        assert not any((settings.library_storage_dir / "covers").iterdir())
        assert not any((settings.library_storage_dir / "tmp").iterdir())
    finally:
        settings.library_storage_dir = original_storage
        main_module.require_permission = original_require
        main_module.create_book = original_create


def test_read_grouping() -> None:
    rows = [
        {"id": "r2", "user_id": "u1", "username": "alice", "read_date": "2026-07-02", "created_at": "2", "updated_at": "2"},
        {"id": "r1", "user_id": "u1", "username": "alice", "read_date": "2026-07-01", "created_at": "1", "updated_at": "1"},
        {"id": "r3", "user_id": "u2", "username": "bob", "read_date": "2026-07-03", "created_at": "3", "updated_at": "3"},
    ]

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def execute(self, *_args): pass
        def fetchall(self): return rows

    class Connection:
        def cursor(self): return Cursor()

    @contextmanager
    def fake_connection():
        yield Connection()

    original = repository_module.connection
    repository_module.connection = fake_connection
    try:
        result = repository_module.list_book_reads("b1", "u1")
    finally:
        repository_module.connection = original
    assert result["readerCount"] == 2
    assert result["readCount"] == 3
    assert result["readers"][0]["isCurrentUser"] is True
    assert [item["readDate"] for item in result["readers"][0]["reads"]] == ["2026-07-02", "2026-07-01"]


def test_read_routes() -> None:
    original_require = main_module.require_permission
    original_book = main_module._library_book_or_404
    original_create = main_module.create_book_read
    original_update = main_module.update_book_read
    original_delete = main_module.delete_book_read
    calls = []
    try:
        main_module.require_permission = lambda _request, permission: calls.append(permission) or {"id": "u1"}
        main_module._library_book_or_404 = lambda book_id, user_id: {"id": book_id, "user": user_id}
        main_module.create_book_read = lambda book_id, user_id, read_date: {"id": "r1", "book": book_id, "user": user_id, "readDate": read_date}
        created = asyncio.run(main_module.library_create_read("b1", FakeRequest({"readDate": "2026-07-14"})))
        assert created["readDate"] == "2026-07-14"
        assert calls == ["library:read"]

        try:
            asyncio.run(main_module.library_create_read("b1", FakeRequest({"readDate": "2026-02-30"})))
            raise AssertionError("invalid calendar date must fail")
        except HTTPException as error:
            assert error.status_code == 422

        main_module.update_book_read = lambda *_args: None
        try:
            asyncio.run(main_module.library_update_read("b1", "other-user-record", FakeRequest({"readDate": "2026-07-14"})))
            raise AssertionError("cross-user update must be hidden")
        except HTTPException as error:
            assert error.status_code == 404

        main_module.delete_book_read = lambda *_args: False
        assert_http(404, lambda: main_module.library_delete_read("b1", "other-user-record", FakeRequest()))
    finally:
        main_module.require_permission = original_require
        main_module._library_book_or_404 = original_book
        main_module.create_book_read = original_create
        main_module.update_book_read = original_update
        main_module.delete_book_read = original_delete


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        test_file_validation(root)
        test_metadata_extraction(root)
        test_storage_and_upload(root)
        test_upload_route_cleanup(root)
    test_read_grouping()
    test_read_routes()


if __name__ == "__main__":
    main()
