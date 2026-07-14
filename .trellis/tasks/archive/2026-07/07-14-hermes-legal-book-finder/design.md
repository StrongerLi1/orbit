# Orbit 共享图书馆技术设计

## Architecture and boundaries

共享图书馆沿用现有单体结构，不新增服务：

- `public/index.html` 增加图书馆页面、上传表单和读者详情界面。
- `public/app.js` 管理目录状态、文件上传、阅读记录和管理员操作。
- `public/styles.css` 增加封面网格、状态标签、读者历史和响应式样式。
- `backend/main.py` 暴露经过登录态与权限校验的图书馆 API，并流式处理上传与下载。
- `backend/repository.py` 负责共享书籍和阅读记录的查询与写入。
- `backend/database.py` 创建 `books` 与 `book_reads` 表。
- 私有存储目录保存电子书与封面，不能挂载为公开静态目录；所有访问经过 API。

原 Hermes 流式桥接、对话模型和外部找书 skill 不参与本功能。

## Data model

### `books`

| Column | Shape | Purpose |
| --- | --- | --- |
| `id` | `VARCHAR(64)` PK | UUID |
| `title` | `VARCHAR(300)` | 手动填写书名 |
| `author` | `VARCHAR(200)` | 手动填写作者 |
| `file_format` | `VARCHAR(20)` | `epub/pdf/mobi/azw3/txt` |
| `original_filename` | `VARCHAR(300)` | 下载时的可读文件名 |
| `stored_filename` | `VARCHAR(120)` | 随机内部文件名，不含用户路径 |
| `file_size` | `BIGINT` | 文件大小 |
| `cover_filename` | `VARCHAR(120)` | 可空的随机封面文件名 |
| `cover_content_type` | `VARCHAR(80)` | 可空；仅 JPEG/PNG/WebP |
| `uploaded_by` | `VARCHAR(64)` | 上传用户 ID，用于审计 |
| `uploaded_by_name` | `VARCHAR(64)` | 用户名快照，删除账号后仍可追溯 |
| `created_at` | `VARCHAR(40)` | 与现有表一致的 ISO 时间 |
| `updated_at` | `VARCHAR(40)` | 最近管理员修改时间 |

按 `created_at DESC` 建索引。首版不使用数据库外键，延续项目现有模式；删除流程在 repository 中显式清理关联记录。

### `book_reads`

| Column | Shape | Purpose |
| --- | --- | --- |
| `id` | `VARCHAR(64)` PK | 单次阅读 UUID |
| `book_id` | `VARCHAR(64)` | 共享书籍 |
| `user_id` | `VARCHAR(64)` | 阅读用户 |
| `read_date` | `VARCHAR(20)` | `YYYY-MM-DD` |
| `created_at` | `VARCHAR(40)` | 创建时间 |
| `updated_at` | `VARCHAR(40)` | 日期修正时间 |

建立 `(book_id, user_id, read_date)` 与 `(user_id, book_id)` 索引，不设置唯一约束：同一用户可以在相同或不同日期重复阅读同一本书。

当前用户的状态由记录推导：`COUNT(book_reads WHERE book_id=? AND user_id=?) > 0` 即已读。唯一读者数使用 `COUNT(DISTINCT user_id)`，总阅读次数使用 `COUNT(*)`。

## File storage

- 新增 `LIBRARY_STORAGE_DIR`，默认位于应用数据目录下的 `library/`，包含 `books/`、`covers/` 与 `tmp/`。
- 新增 `LIBRARY_MAX_FILE_MB=100`；封面固定限制为 5 MB。
- 上传使用 `multipart/form-data` 与 FastAPI `UploadFile`，新增标准依赖 `python-multipart`；服务端按块写入临时文件，不能一次把 100 MB 读入内存。
- 电子书只接受 EPUB、PDF、MOBI、AZW3、TXT。除扩展名和声明类型外，使用标准库检查基本内容签名：PDF 头、EPUB ZIP mimetype、MOBI/AZW3 `BOOKMOBI` 标记、TXT 可解码文本。
- 封面只接受 JPEG、PNG、WebP，使用文件签名而非仅信任扩展名或 `Content-Type`。
- 最终文件名由书籍 UUID和规范扩展名生成；原始文件名只用于下载响应并做控制字符清理。
- 上传过程先写临时文件并完成验证，再移动到最终路径并写数据库；任一步失败都执行补偿清理。
- 删除书籍先确认管理员权限和记录，再删除数据库数据与文件；文件删除失败要记录错误并返回失败，避免静默留下不可追踪文件。
- 所有路径都由已知存储根目录与数据库中的内部文件名组合，拒绝包含分隔符或解析后逃逸存储根目录的值。

## Permissions

在现有 RBAC 中增加：

- `library:read`：查看目录、封面、读者历史并下载。
- `library:upload`：上传共享书籍。
- `library:manage`：编辑书目信息、替换/删除封面、删除整本书。

默认 `user` 角色获得 `library:read` 与 `library:upload`；`admin` 通过现有全权限规则获得三项权限。阅读记录的创建、修改和删除还必须校验 `user_id == current_user.id`，不能仅依赖角色。

删除普通用户账号时清理该用户的 `book_reads`，但保留其上传的共享书籍及上传者用户名快照。

## API contracts

All endpoints require authentication.

### Books

- `GET /api/library/books`
  - 返回共享书籍摘要。
  - 每项包含 `readerCount`、`readCount`、`currentUserReadCount` 与 `currentUserRead`。
- `POST /api/library/books` (`library:upload`, multipart)
  - Fields: `title`, `author`, `bookFile`, optional `coverFile`.
  - 返回新书摘要，状态 `201`。
- `PATCH /api/library/books/{book_id}` (`library:manage`, multipart)
  - 可修改 `title`、`author`，可选替换或移除封面；首版不替换电子书正文。
- `DELETE /api/library/books/{book_id}` (`library:manage`)
  - 删除元数据、全部阅读记录、电子书与封面。
- `GET /api/library/books/{book_id}/download` (`library:read`)
  - `Content-Disposition: attachment`，保留规范化原文件名。
- `GET /api/library/books/{book_id}/cover` (`library:read`)
  - 有封面时返回图片；无封面时返回 `404`，前端使用 CSS 占位封面。

### Reading history

- `GET /api/library/books/{book_id}/reads` (`library:read`)
  - 返回 `readerCount`、`readCount` 与按用户名分组的阅读记录。
  - 单条记录包含 `id`、`readDate`、`isCurrentUser`；不暴露用户 ID。
- `POST /api/library/books/{book_id}/reads` (`library:read`)
  - JSON `{ "readDate": "YYYY-MM-DD" }`；每次都新增记录，返回 `201`。
- `PATCH /api/library/books/{book_id}/reads/{read_id}` (`library:read`)
  - JSON `{ "readDate": "YYYY-MM-DD" }`；仅记录所有者可修改。
- `DELETE /api/library/books/{book_id}/reads/{read_id}` (`library:read`)
  - 仅记录所有者可删除；删除最后一条后当前用户状态自动变为未读。

对不存在和无权访问的阅读记录统一返回 `404`，不泄露其他用户记录细节。日期必须是有效 ISO 日历日期。

## Frontend flow

1. 进入“共享图书馆”时加载书籍摘要并呈现封面网格。
2. 上传按钮打开专用 multipart 表单；成功后把返回书籍插入目录并关闭表单。
3. 卡片显示当前用户状态，以及“X 人读过 · 共阅读 Y 次”。
4. “记录阅读”打开日期输入，默认当天；提交后新增记录并刷新该书统计。
5. “查看读者”打开详情，按用户名分组列出日期；当前用户自己的记录提供修改和删除操作。
6. 管理员额外看到编辑与删除书籍操作；普通用户不渲染这些按钮，后端仍强制校验。
7. 无封面卡片用书名首字与稳定色值生成占位封面，无需生成图片文件。

## Failure handling

- 上游不存在；所有失败来自输入、存储、数据库或权限。
- 413 表示电子书或封面过大，415 表示文件类型不支持，422 表示字段或日期无效，404 隐藏不存在/越权资源，409 用于存储或状态冲突，500 仅返回通用错误。
- 前端上传期间禁用重复提交并显示进度状态；失败后保留用户填写的元数据，便于重试。
- 文件下载使用流式响应，不将文件读入内存。

## Compatibility, rollout, and rollback

- 新表通过 `CREATE TABLE IF NOT EXISTS` 增量创建，不修改现有业务表。
- 新权限由现有 RBAC seed 逻辑补齐并自动分配给默认角色；需要覆盖升级后已有角色映射。
- 新导航与页面对无权限用户隐藏；旧页面和 API 不变。
- 部署前创建并授权存储目录，同时设置 Nginx `client_max_body_size` 大于 100 MB。
- 回滚代码不会破坏旧功能；`books`、`book_reads` 与存储目录可保留，重新部署后继续使用。只有显式数据清理才删除文件。

## Trade-offs

- 采用磁盘文件 + MySQL 元数据，而非对象存储：最符合当前单机部署；多实例或云存储需求出现时再抽象存储后端。
- 增加 `python-multipart` 而不设计自定义分段协议：依赖很小，显著简化浏览器上传和错误处理。
- 文件名解析只处理明确的“书名 - 作者”和“《书名》 作者”模式；不明确时整个文件名作为书名，避免猜错作者。
- EPUB 使用标准库读取 OPF 元数据与 JPEG/PNG/WebP 封面；PDF 使用 `pypdf` 读取文档信息。MOBI/AZW3/TXT 首版仅使用文件名兜底，避免引入体积更大的电子书解析栈。
- 元数据优先级固定为“用户手动填写 > 文件内元数据 > 文件名”，用户上传封面优先于 EPUB 内嵌封面。
- 读者详情按需加载：目录只带统计，避免书籍多、阅读记录多时扩大首屏响应。
