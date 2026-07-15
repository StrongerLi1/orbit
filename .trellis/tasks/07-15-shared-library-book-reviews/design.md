# 技术设计：共享图书馆独立书评

## 架构边界

书评是共享图书馆的一种独立用户内容：MySQL `book_reviews` -> `backend.database` 启动建表与用户清理 -> `backend.repository` 查询、创建、删除与阅读记录联动 -> FastAPI 书评/阅读记录路由 -> 浏览器图书卡片、书评弹窗和阅读记录表单。

本任务只覆盖浏览器端。Android 当前没有共享图书馆页面，后续 Android 图书馆任务再复用本 API 契约。

## 数据模型与迁移

新增表：

```sql
book_reviews(
  id VARCHAR(64) PRIMARY KEY,
  book_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  reviewer_name VARCHAR(64) NOT NULL,
  content TEXT NOT NULL,
  created_at VARCHAR(40) NOT NULL,
  INDEX idx_book_reviews_book_created (book_id, created_at),
  INDEX idx_book_reviews_user (user_id)
)
```

- `reviewer_name` 保存用户名快照，列表不需要向客户端暴露内部用户 ID。
- `initialize_database()` 使用 `CREATE TABLE IF NOT EXISTS`，已有数据库启动时幂等升级；不修改已有 `books` 或 `book_reads` 数据。
- 删除书籍时同时删除该书的书评；删除用户账号时同时删除该用户的书评，和现有阅读记录清理保持一致。
- 书评不绑定 `book_reads`，删除或修改阅读记录不会改变书评；同一用户可以对同一本书发布多条书评。

## API 契约

新增接口：

```text
GET    /api/library/books/{book_id}/reviews
POST   /api/library/books/{book_id}/reviews
DELETE /api/library/books/{book_id}/reviews/{review_id}
```

响应列表元素：

```json
{
  "id": "...",
  "username": "alice",
  "content": "...",
  "createdAt": "2026-07-15T...Z",
  "canDelete": true
}
```

- 三个接口均要求 `library:read`；已有普通用户和管理员都具备该权限，因此未读用户也可以评论。
- POST 只接受 `content`，服务端 trim 后要求非空，最多保留 3000 个字符；不接受客户端传入的用户 ID 或用户名。
- 服务端从认证上下文写入 `user_id` 和 `reviewer_name`。
- `canDelete` 由服务端按“管理员或当前用户是作者”计算；不返回 `user_id`。
- 非管理员删除他人书评返回 `404`，与阅读记录的 owner-only 删除契约一致，避免暴露评论归属；管理员可删除任意书评。
- 书籍不存在返回 `404`；空内容或超长内容返回 `422`。

阅读记录 POST 扩展：

```json
{
  "readDate": "2026-07-15",
  "review": "可选书评"
}
```

- `review` 可缺省或为空；创建阅读记录时有内容则在同一数据库事务中额外创建独立书评。
- PATCH 阅读记录只处理 `readDate`，不修改或删除已有书评。
- 现有阅读记录响应字段保持兼容；创建响应可附带本次创建的书评，但客户端不依赖该字段。

## 后端实现

- 在 `backend.database.initialize_database()` 创建 `book_reviews` 表。
- 在 `backend.repository` 增加书评 mapper、列表、创建和 owner/admin 删除函数；扩展删除书籍和用户的清理路径。
- 扩展 `create_book_read()` 接受可选书评内容，在同一连接事务内写入 `book_reads` 和 `book_reviews`，避免记录成功而书评失败造成半完成状态。
- 在 `backend.main` 增加书评内容校验、三个书评路由，并在阅读记录 POST 中复用同一校验。
- 管理员判断沿用现有 RBAC 权限集合（`users:manage`），不新增角色或权限。

## 浏览器实现

- 每本书卡片新增“书评”按钮，打开独立书评弹窗；弹窗展示全部评论、用户名、时间和当前用户可执行的删除按钮。
- 书评弹窗底部提供文本框和发布按钮，所有能看到图书馆的用户都能使用，不根据 `currentUserRead` 隐藏。
- 阅读记录弹窗新增可选“书评”文本域；新建时发送 `review`，编辑记录时隐藏或禁用该字段，明确不会修改历史书评。
- 删除书评前使用现有 `confirm`，成功后重新加载该书评列表；新增阅读记录后同时刷新图书统计和书评列表。
- 所有用户可见文本通过现有 `escapeHtml` 渲染，按钮权限以 API 返回的 `canDelete` 为准，服务端仍是最终授权边界。
- 复用现有 vanilla JS 状态、`request()`、toast 和弹窗样式，不引入新依赖。

## 兼容性、失败与回滚

- 旧客户端忽略新增 API 和阅读记录响应字段即可继续工作；旧阅读记录没有书评也能正常展示。
- 新表只增加数据，不改变旧表结构；回滚应用代码时保留 `book_reviews` 表和数据，不执行破坏性删除。
- 书籍删除、用户删除和阅读记录+书评创建采用数据库操作顺序/事务，失败时回滚数据库写入。
- 书评接口错误通过现有前端 toast 展示，列表加载失败显示弹窗内错误状态，不影响书籍目录加载。
