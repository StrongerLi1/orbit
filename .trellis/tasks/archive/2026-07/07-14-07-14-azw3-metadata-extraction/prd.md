# AZW3 书目信息与封面解析

## Goal

为共享图书馆上传流程增加 AZW3 书名、作者和内嵌封面解析，并保留手写覆盖和文件名回退。

## Background

- 当前 `backend/library_files.py` 已校验 AZW3/MOBI 的 `BOOKMOBI` 签名，但只对 EPUB/PDF 提取元数据。
- 当前上传优先级是用户手写值、内嵌元数据、文件名回退；手动封面优先于内嵌封面。
- AZW3 使用 PalmDB/MOBI/KF8 容器。libmobi 的公开实现将作者映射到 EXTH 100、更新书名映射到 EXTH 503，并以首资源记录加 EXTH 201 封面偏移定位封面。
- 项目当前只存储 JPEG、PNG、WebP 封面，单张封面默认上限 5 MB。

## Requirements

- 上传 `.azw3` 时读取 PalmDB 记录表、MOBI 头和 EXTH 元数据，提取书名与一个或多个作者。
- 书名优先使用 EXTH 更新书名，其次使用 MOBI full-name，再回退文件名。
- 封面使用 MOBI 首资源记录与 EXTH cover-offset 定位，并继续执行现有图片签名和大小校验。
- 解析失败必须是软失败：合法 AZW3 仍可通过手写字段或文件名上传。
- 解析器必须使用有界读取、校验记录偏移，不执行外部命令，不解压或重写原文件。
- 保持现有优先级：手写字段/封面 > AZW3 内嵌数据 > 文件名。
- 不加入 Calibre、KindleUnpack 或原生 C 运行时依赖；标准库足以覆盖所需字段。
- 只接受现有 JPEG、PNG、WebP 图片签名；GIF/BMP 不转换，按无内嵌封面处理。

## Acceptance Criteria

- [x] 带 UTF-8 书名、作者和 JPEG/PNG/WebP 封面的 AZW3 可自动生成书目信息和封面。
- [x] EXTH 503 缺失时使用 MOBI full-name；内嵌作者缺失时使用文件名作者或提示手写。
- [x] 多个 EXTH 100 作者按稳定顺序合并。
- [x] 手写书名、作者和上传封面仍覆盖 AZW3 内嵌值。
- [x] 畸形记录表、越界 EXTH、超限封面或不支持的封面图片不会崩溃、越界读取或留下临时文件。
- [x] 现有 EPUB、PDF、MOBI、TXT 上传和阅读记录测试保持通过。

## Out of Scope

- DRM 解密、正文解析、格式转换、GIF/BMP 转码。
- 将同一解析能力扩展到 `.mobi`；本补丁只改变用户明确要求的 `.azw3` 路径。

## PDF First-Page Cover Extension

### Goal

PDF 没有手动上传封面时，将第一页完整渲染为共享图书馆封面。

### Requirements

- 保持优先级：手动封面 > PDF 第一页自动封面。
- 只渲染第一页，不提取正文图片，不调用系统命令。
- 使用有预编译 wheel、宽松许可证的 PDFium Python 绑定；继续使用已安装的 Pillow 编码封面。
- 限制输出像素尺寸并继续服从 `LIBRARY_MAX_COVER_MB`，避免超大页面导致内存失控。
- 加密、无页面、畸形或渲染失败的 PDF 软降级为无自动封面，不拒绝合法上传。

### Acceptance Criteria

- [x] 普通单页和多页 PDF 均只把第一页生成为支持的封面图片。
- [x] 自动封面保持第一页完整比例和白色背景，最长边有固定上限。
- [x] 手动上传封面继续覆盖 PDF 自动封面。
- [x] 加密、零页、畸形、超大页面或超限输出不会崩溃或留下临时文件。
- [x] EPUB、AZW3、MOBI、TXT 及现有阅读记录测试保持通过。

### Rendering Contract

- 用户确认自动封面使用完整第一页、白底 JPEG、最长边 1600 像素、质量 85；超过现有封面大小限制时软降级。
