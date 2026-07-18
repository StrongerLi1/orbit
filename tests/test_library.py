import asyncio
import io
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, UploadFile
from PIL import Image
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


def pdf_bytes(
    title: str = "PDF 内嵌书名",
    author: str = "PDF 内嵌作者",
    pages: tuple[tuple[float, float], ...] = ((100, 100),),
    password: str = "",
) -> bytes:
    buffer = io.BytesIO()
    writer = PdfWriter()
    for width, height in pages:
        writer.add_blank_page(width=width, height=height)
    writer.add_metadata({"/Title": title, "/Author": author})
    if password:
        writer.encrypt(password)
    writer.write(buffer)
    return buffer.getvalue()


def azw3_bytes(
    updated_title: str | None = "AZW3 更新书名",
    full_name: str = "AZW3 原始书名",
    authors: tuple[str, ...] = ("作者甲", "作者乙"),
    cover: bytes | None = b"\xff\xd8\xff\xe0azw3-cover",
) -> bytes:
    def exth_record(record_type: int, value: bytes) -> bytes:
        return record_type.to_bytes(4, "big") + (len(value) + 8).to_bytes(4, "big") + value

    exth_records = [exth_record(100, author.encode()) for author in authors]
    if cover is not None:
        exth_records.append(exth_record(201, (2).to_bytes(4, "big")))
    if updated_title is not None:
        exth_records.append(exth_record(503, updated_title.encode()))
    exth_body = b"".join(exth_records)
    exth = b"EXTH" + (len(exth_body) + 12).to_bytes(4, "big") + len(exth_records).to_bytes(4, "big") + exth_body

    header_length = 232
    full_name_bytes = full_name.encode()
    full_name_offset = 16 + header_length + len(exth)
    record0 = bytearray(full_name_offset + len(full_name_bytes))
    record0[16:20] = b"MOBI"
    record0[20:24] = header_length.to_bytes(4, "big")
    record0[28:32] = (65001).to_bytes(4, "big")
    record0[36:40] = (8).to_bytes(4, "big")
    record0[84:88] = full_name_offset.to_bytes(4, "big")
    record0[88:92] = len(full_name_bytes).to_bytes(4, "big")
    record0[108:112] = (3 if cover is not None else 0xFFFFFFFF).to_bytes(4, "big")
    record0[124:128] = (1).to_bytes(4, "big")
    record0[16 + header_length:full_name_offset] = exth
    record0[full_name_offset:] = full_name_bytes

    records = [bytes(record0)]
    if cover is not None:
        records.extend((
            b"compressed-text-1",
            b"compressed-text-2",
            b"\xff\xd8\xffother-image",
            b"image-gap",
            cover,
        ))
    palm_header = bytearray(78)
    palm_header[60:68] = b"BOOKMOBI"
    palm_header[76:78] = len(records).to_bytes(2, "big")
    first_record_offset = 78 + len(records) * 8 + 2
    record_offsets = []
    cursor = first_record_offset
    for record in records:
        record_offsets.append(cursor)
        cursor += len(record)
    table = b"".join(offset.to_bytes(4, "big") + b"\0\0\0\0" for offset in record_offsets)
    return bytes(palm_header) + table + b"\0\0" + b"".join(records)


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
    metadata = extract_book_metadata(pdf, pdf.name, "pdf", 1024 * 1024)
    assert metadata["title"] == "PDF 内嵌书名"
    assert metadata["author"] == "PDF 内嵌作者"
    assert metadata["coverBytes"].startswith(b"\xff\xd8\xff")
    assert metadata["coverContentType"] == "image/jpeg"
    with Image.open(io.BytesIO(metadata["coverBytes"])) as cover:
        assert cover.format == "JPEG"
        assert cover.size == (200, 200)
        assert cover.getpixel((0, 0)) == (255, 255, 255)
    assert "coverBytes" not in extract_book_metadata(pdf, pdf.name, "pdf", 4)

    multipage = root / "多页.pdf"
    multipage.write_bytes(pdf_bytes(pages=((400, 800), (1000, 100))))
    metadata = extract_book_metadata(multipage, multipage.name, "pdf", 1024 * 1024)
    with Image.open(io.BytesIO(metadata["coverBytes"])) as cover:
        assert cover.size == (800, 1600)

    oversized_page = root / "超大页面.pdf"
    oversized_page.write_bytes(pdf_bytes(pages=((10000, 5000),)))
    metadata = extract_book_metadata(oversized_page, oversized_page.name, "pdf", 1024 * 1024)
    with Image.open(io.BytesIO(metadata["coverBytes"])) as cover:
        assert cover.size == (1600, 800)

    encrypted_pdf = root / "加密文件 - 文件作者.pdf"
    encrypted_pdf.write_bytes(pdf_bytes(password="secret"))
    assert extract_book_metadata(encrypted_pdf, encrypted_pdf.name, "pdf", 1024 * 1024) == {
        "title": "加密文件",
        "author": "文件作者",
    }

    malformed_pdf = root / "损坏文件 - 文件作者.pdf"
    malformed_pdf.write_bytes(b"%PDF-1.7\nmalformed")
    assert extract_book_metadata(malformed_pdf, malformed_pdf.name, "pdf", 1024 * 1024) == {
        "title": "损坏文件",
        "author": "文件作者",
    }

    empty_pdf = root / "空白文件 - 文件作者.pdf"
    empty_pdf.write_bytes(pdf_bytes(pages=()))
    metadata = extract_book_metadata(empty_pdf, empty_pdf.name, "pdf", 1024 * 1024)
    assert metadata["title"] == "PDF 内嵌书名"
    assert metadata["author"] == "PDF 内嵌作者"
    assert "coverBytes" not in metadata

    azw3 = root / "文件书名 - 文件作者.azw3"
    azw3.write_bytes(azw3_bytes())
    assert detect_book_format(azw3, azw3.name) == "azw3"
    metadata = extract_book_metadata(azw3, azw3.name, "azw3", 1024)
    assert metadata["title"] == "AZW3 更新书名"
    assert metadata["author"] == "作者甲 / 作者乙"
    assert metadata["coverBytes"] == b"\xff\xd8\xff\xe0azw3-cover"
    assert metadata["coverContentType"] == "image/jpeg"

    full_name = root / "文件书名 - 文件作者-full-name.azw3"
    full_name.write_bytes(azw3_bytes(updated_title=None, full_name="MOBI Full Name", authors=()))
    metadata = extract_book_metadata(full_name, "文件书名 - 文件作者.azw3", "azw3", 1024)
    assert metadata["title"] == "MOBI Full Name"
    assert metadata["author"] == "文件作者"

    covers = (
        (b"\xff\xd8\xffjpeg", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\npng", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPwebp", "image/webp"),
    )
    for index, (cover, content_type) in enumerate(covers):
        path = root / f"cover-{index}.azw3"
        path.write_bytes(azw3_bytes(cover=cover))
        assert extract_book_metadata(path, path.name, "azw3", 1024)["coverContentType"] == content_type

    unsupported_cover = root / "unsupported-cover.azw3"
    unsupported_cover.write_bytes(azw3_bytes(cover=b"GIF89a-cover"))
    assert "coverBytes" not in extract_book_metadata(unsupported_cover, unsupported_cover.name, "azw3", 1024)
    assert "coverBytes" not in extract_book_metadata(azw3, azw3.name, "azw3", 4)

    malformed_table = bytearray(azw3_bytes())
    malformed_table[78:82] = (len(malformed_table) + 1).to_bytes(4, "big")
    malformed = root / "回退书名 - 回退作者.azw3"
    malformed.write_bytes(malformed_table)
    assert extract_book_metadata(malformed, malformed.name, "azw3", 1024) == {
        "title": "回退书名",
        "author": "回退作者",
    }

    malformed_exth = bytearray(azw3_bytes())
    record0_offset = int.from_bytes(malformed_exth[78:82], "big")
    exth_length_offset = record0_offset + 16 + 232 + 4
    malformed_exth[exth_length_offset:exth_length_offset + 4] = len(malformed_exth).to_bytes(4, "big")
    malformed.write_bytes(malformed_exth)
    assert extract_book_metadata(malformed, malformed.name, "azw3", 1024) == {
        "title": "回退书名",
        "author": "回退作者",
    }

    assert extract_book_metadata(azw3, "文件书名 - 文件作者.mobi", "mobi", 1024) == {
        "title": "文件书名",
        "author": "文件作者",
    }


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

    async def pdf_auto_upload() -> dict:
        return await main_module.library_upload_book(
            FakeRequest(),
            title="",
            author="",
            book_file=UploadFile(filename="错误文件名 - 错误作者.pdf", file=io.BytesIO(pdf_bytes())),
            cover_file=None,
        )

    async def azw3_manual_upload() -> dict:
        return await main_module.library_upload_book(
            FakeRequest(),
            title="手写书名",
            author="手写作者",
            book_file=UploadFile(filename="source.azw3", file=io.BytesIO(azw3_bytes())),
            cover_file=UploadFile(filename="manual.png", file=io.BytesIO(b"\x89PNG\r\n\x1a\nmanual-cover")),
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

        settings.library_storage_dir = root / "pdf-auto"
        created.clear()
        result = asyncio.run(pdf_auto_upload())
        assert result["title"] == "PDF 内嵌书名"
        assert result["author"] == "PDF 内嵌作者"
        assert cover_path(created["coverFilename"]).read_bytes().startswith(b"\xff\xd8\xff")
        assert not any((settings.library_storage_dir / "tmp").iterdir())

        settings.library_storage_dir = root / "azw3-manual"
        created.clear()
        result = asyncio.run(azw3_manual_upload())
        assert result["title"] == "手写书名"
        assert result["author"] == "手写作者"
        assert cover_path(created["coverFilename"]).read_bytes() == b"\x89PNG\r\n\x1a\nmanual-cover"
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


def test_review_mapping_and_permissions() -> None:
    rows = [
        {"id": "v1", "book_id": "b1", "user_id": "u1", "reviewer_name": "alice", "is_anonymous": 1, "content": "我的评论", "created_at": "2026-07-15T00:00:00Z"},
        {"id": "v2", "book_id": "b1", "user_id": "u2", "reviewer_name": "bob", "content": "另一条评论", "created_at": "2026-07-14T00:00:00Z"},
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
        result = repository_module.list_book_reviews("b1", "u1")
        assert result[0]["canDelete"] is True
        assert result[0]["canToggleAnonymous"] is True
        assert result[0]["username"] == "alice"
        assert result[1]["canDelete"] is False
        assert result[1]["username"] == "bob"
        other_result = repository_module.list_book_reviews("b1", "u2")
        assert other_result[0]["username"] == "匿名用户"
        admin_result = repository_module.list_book_reviews("b1", "admin", True)
        assert all(review["canDelete"] for review in admin_result)
        assert admin_result[0]["username"] == "alice"
    finally:
        repository_module.connection = original


def test_book_search() -> None:
    rows = [{
        "id": "b1", "title": "百年孤独", "author": "加西亚·马尔克斯",
        "file_format": "epub", "original_filename": "book.epub", "file_size": 1,
        "cover_filename": "", "uploaded_by_name": "alice", "created_at": "1",
        "updated_at": "1", "reader_count": 0, "read_count": 0,
        "current_user_read_count": 0,
    }]
    calls = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def execute(self, query, params): calls.append((query, params))
        def fetchall(self): return rows

    class Connection:
        def cursor(self): return Cursor()

    @contextmanager
    def fake_connection():
        yield Connection()

    original = repository_module.connection
    repository_module.connection = fake_connection
    try:
        result = repository_module.list_books("u1", "  百年   马尔克斯  ")
        repository_module.list_books("u1")
    finally:
        repository_module.connection = original

    assert result[0]["title"] == "百年孤独"
    assert calls[0][0].count("(b.title LIKE %s OR b.author LIKE %s)") == 2
    assert calls[0][1] == ["u1", "%百年%", "%百年%", "%马尔克斯%", "%马尔克斯%"]
    assert "WHERE (b.title LIKE %s OR b.author LIKE %s)" not in calls[1][0]
    assert calls[1][1] == ["u1"]


def test_book_search_route() -> None:
    original_require = main_module.require_permission
    original_list = main_module.list_books
    calls = []
    try:
        main_module.require_permission = lambda _request, permission: calls.append(("permission", permission)) or {"id": "u1"}
        main_module.list_books = lambda user_id, query: calls.append(("search", user_id, query)) or []
        assert main_module.library_books(FakeRequest(), "百年 马尔克斯") == []
    finally:
        main_module.require_permission = original_require
        main_module.list_books = original_list

    assert calls == [("permission", "library:read"), ("search", "u1", "百年 马尔克斯")]


def test_read_routes() -> None:
    original_require = main_module.require_permission
    original_book = main_module._library_book_or_404
    original_create = main_module.create_book_read
    original_update = main_module.update_book_read
    original_delete = main_module.delete_book_read
    original_create_review = main_module.create_book_review
    original_delete_review = main_module.delete_book_review
    original_update_review = main_module.update_book_review_anonymity
    original_list_reviews = main_module.list_book_reviews
    calls = []
    try:
        main_module.require_permission = lambda _request, permission: calls.append(permission) or {"id": "u1", "username": "alice", "permissions": []}
        main_module._library_book_or_404 = lambda book_id, user_id: {"id": book_id, "user": user_id}
        main_module.create_book_read = lambda book_id, user_id, read_date, review_content="", reviewer_name="", review_anonymous=False: {"id": "r1", "book": book_id, "user": user_id, "readDate": read_date, "review": review_content, "reviewAnonymous": review_anonymous}
        created = asyncio.run(main_module.library_create_read("b1", FakeRequest({"readDate": "2026-07-14"})))
        assert created["readDate"] == "2026-07-14"
        assert calls == ["library:read"]
        created_with_review = asyncio.run(main_module.library_create_read("b1", FakeRequest({"readDate": "2026-07-15", "review": "  很好看  ", "reviewAnonymous": True})))
        assert created_with_review["review"] == "很好看"
        assert created_with_review["reviewAnonymous"] is True

        try:
            asyncio.run(main_module.library_create_read("b1", FakeRequest({"readDate": "2026-02-30"})))
            raise AssertionError("invalid calendar date must fail")
        except HTTPException as error:
            assert error.status_code == 422
        assert_http(422, lambda: asyncio.run(main_module.library_create_read("b1", FakeRequest({"readDate": "2026-07-14", "review": "x" * 3001}))))

        main_module.update_book_read = lambda *_args: None
        try:
            asyncio.run(main_module.library_update_read("b1", "other-user-record", FakeRequest({"readDate": "2026-07-14"})))
            raise AssertionError("cross-user update must be hidden")
        except HTTPException as error:
            assert error.status_code == 404

        main_module.delete_book_read = lambda *_args: False
        assert_http(404, lambda: main_module.library_delete_read("b1", "other-user-record", FakeRequest()))

        main_module.create_book_review = lambda book_id, user_id, reviewer_name, content, is_anonymous=False: {"id": "v1", "book": book_id, "user": user_id, "username": reviewer_name, "content": content, "isAnonymous": is_anonymous}
        main_module.list_book_reviews = lambda book_id, user_id, is_admin: [{"id": "v1", "canDelete": is_admin or user_id == "u1"}]
        listed_reviews = main_module.library_book_reviews("b1", FakeRequest())
        assert listed_reviews == [{"id": "v1", "canDelete": True}]
        created_review = asyncio.run(main_module.library_create_review("b1", FakeRequest({"content": "  很值得重读  ", "anonymous": True})))
        assert created_review["content"] == "很值得重读"
        assert created_review["isAnonymous"] is True
        assert calls[-1] == "library:read"
        assert_http(422, lambda: asyncio.run(main_module.library_create_review("b1", FakeRequest({"content": "   "}))))
        assert_http(422, lambda: asyncio.run(main_module.library_create_review("b1", FakeRequest({"content": "x" * 3001}))))

        main_module.delete_book_review = lambda *_args: False
        assert_http(404, lambda: main_module.library_delete_review("b1", "other-user-review", FakeRequest()))
        main_module.update_book_review_anonymity = lambda *_args: False
        assert_http(404, lambda: asyncio.run(main_module.library_update_review("b1", "other-user-review", FakeRequest({"anonymous": True}))))
        main_module.update_book_review_anonymity = lambda *_args: True
        assert main_module.library_update_review is not None
        assert asyncio.run(main_module.library_update_review("b1", "v1", FakeRequest({"anonymous": False}))) == {"ok": True}
        main_module.delete_book_review = lambda *_args: True
        assert main_module.library_delete_review("b1", "v1", FakeRequest()) == {"ok": True}
        admin_calls = []
        main_module.require_permission = lambda _request, permission: admin_calls.append(permission) or {"id": "admin", "username": "admin", "permissions": ["users:manage"]}
        assert main_module.library_delete_review("b1", "v1", FakeRequest()) == {"ok": True}
        assert admin_calls[-1] == "library:read"
    finally:
        main_module.require_permission = original_require
        main_module._library_book_or_404 = original_book
        main_module.create_book_read = original_create
        main_module.update_book_read = original_update
        main_module.delete_book_read = original_delete
        main_module.create_book_review = original_create_review
        main_module.delete_book_review = original_delete_review
        main_module.update_book_review_anonymity = original_update_review
        main_module.list_book_reviews = original_list_reviews


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        test_file_validation(root)
        test_metadata_extraction(root)
        test_storage_and_upload(root)
        test_upload_route_cleanup(root)
    test_read_grouping()
    test_book_search()
    test_book_search_route()
    test_read_routes()


if __name__ == "__main__":
    main()
