# AZW3 书目信息与封面解析设计

## Architecture and boundaries

继续复用 `backend/library_files.py` 的单一元数据入口，不新增服务或运行时依赖：

- `extract_book_metadata()` 在 `file_format == "azw3"` 时调用内部 AZW3/MOBI 容器解析器。
- 解析器只读取 PalmDB 记录表、record 0 的 PalmDOC/MOBI/EXTH 头，以及被 EXTH 201 指向的单个封面记录。
- 上传路由、数据库结构、前端表单和响应结构不变。
- 解析异常返回空字典，由现有文件名和手写字段逻辑兜底。

## Binary data flow

1. 从文件头读取 PalmDB `record_count` 与每条 8 字节记录索引。
2. 校验记录偏移严格递增且位于文件范围内。
3. 有界读取 record 0，校验偏移 16 处的 `MOBI` 标识。
4. 从 MOBI 头读取编码、full-name 偏移/长度、首资源记录和头长度。
5. 从 MOBI 头末尾解析有界 EXTH 区域：
   - 100：作者，可重复。
   - 201：封面相对资源偏移。
   - 503：更新书名，优先于 full-name。
6. 以 `first_resource + cover_offset` 定位记录，只在记录长度不超过封面限制时读取，并复用 `detect_cover_bytes()` 接受 JPEG/PNG/WebP。

## Validation and limits

- PalmDB 记录数量来自 16 位字段，索引表读取量天然有界；仍需验证表长不超过文件大小。
- record 0 最多读取 1 MB，书名和单个 EXTH 字符串限制为现有字段上限附近的保守值。
- EXTH 总长度、记录数量、每条记录长度均必须落在 record 0 内。
- 封面读取前用相邻记录偏移计算长度；超过 `LIBRARY_MAX_COVER_MB` 时跳过。
- 文本编码 65001 使用 UTF-8，1252 使用 CP1252；未知编码使用有替换策略的 UTF-8，解析错误不得中断上传。

## Compatibility

- 不改变 `detect_book_format()` 对 AZW3/MOBI 的现有签名校验。
- 不改变手写优先级、封面存储格式、API 或数据库。
- `.mobi` 继续使用文件名回退，避免无需求扩张。

## Trade-offs

- 选择标准库小解析器而不是 Calibre/KindleUnpack/libmobi 运行时，因为需求只涉及三个 EXTH 字段和一个资源记录。
- 不支持混合 KF7/KF8 的第二套 record 0；常规 AZW3 使用当前 KF8 record 0，混合文件仍可通过手写或文件名上传。
- 不转换 GIF/BMP；需要时由管理员上传支持格式封面。

## Rollback

回滚仅需移除 AZW3 分支和相关测试。文件格式校验、数据库和已上传书籍均无需迁移。

## PDF First-Page Cover Extension

- `_pdf_metadata(path, max_cover_bytes)` 继续读取 pypdf 元数据，并使用 pypdfium2 只打开、测量和渲染第一页。
- 页面按完整比例缩放到固定最长边上限，白色背景转 RGB 后由 Pillow 编码；生成结果超过现有封面限制则跳过。
- 上传路由、手动封面覆盖逻辑、数据库和 API 不变。
- pypdfium2 使用官方预编译 wheel，不依赖生产机上的 Poppler、Ghostscript 或子进程。
- 渲染异常为软失败；回滚只需移除依赖和 PDF 封面分支，不影响已存储封面。
