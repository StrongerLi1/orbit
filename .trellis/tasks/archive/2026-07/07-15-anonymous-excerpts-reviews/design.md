# 技术设计：Web 摘录与书评匿名展示

## 架构边界

匿名状态是数据库到浏览器的跨层契约：MySQL `excerpts.is_anonymous` / `book_reviews.is_anonymous` -> `backend.database` 启动升级与导入 -> `backend.repository` 按当前用户计算可见名称与能力 -> FastAPI 通用摘录路由和书评路由 -> `public/app.js` 表单、卡片、弹窗。

本次不修改 Android 客户端，也不改变摘录/书评原有的共享读取范围和真实 UID 授权逻辑。

## 数据模型与迁移

- `excerpts` 增加 `is_anonymous TINYINT(1) NOT NULL DEFAULT 0`。
- `book_reviews` 增加 `is_anonymous TINYINT(1) NOT NULL DEFAULT 0`。
- `initialize_database()` 对两张已存在的表通过 `information_schema.COLUMNS` 检测后幂等 `ALTER TABLE`；新表定义同时包含默认值。
- JSON 导入的历史摘录显式写入 `is_anonymous = 0`；书评没有现有 JSON 导入路径，旧行由数据库默认值兼容。
- 不删除或重写 `owner_user_id` / `user_id` 和用户名快照。匿名只影响展示，不影响数据归属、清理和权限。

## API 契约

### 摘录

- `POST /api/excerpts` 和 `PATCH /api/excerpts/{id}` 接受可选布尔字段 `anonymous`；服务端将其规范化为 `is_anonymous`，不读取客户端的作者字段。
- 摘录响应保留 `createdByName` 和 `canManage`，新增 `isAnonymous` 与仅作者为真的 `canToggleAnonymous`。
- `createdByName` 是服务端按当前读取者计算的展示值：匿名记录对记录作者本人和管理员返回用户名快照，对其他普通读取者返回 `匿名用户`；非匿名记录始终返回用户名快照。
- `isAnonymous` 只表示该记录的公开状态，不暴露内部 UID；作者看到真实用户名和该字段对应的“匿名”标识。

### 书评

- 保持现有 `GET/POST/DELETE /api/library/books/{book_id}/reviews`；POST 接受可选布尔字段 `anonymous`。
- 新增 `PATCH /api/library/books/{book_id}/reviews/{review_id}`，只处理 `anonymous` 字段，不接受或修改 `content`、`user_id`、`reviewer_name`。
- 书评响应保留 `username`、`content`、`createdAt`、`canDelete`，新增 `isAnonymous` 和 `canToggleAnonymous`。
- `username` 使用与摘录相同的按读取者计算规则；`canToggleAnonymous` 仅在当前用户是书评作者时为真，管理员仍可按现有规则删除，但不新增管理员代作者切换书评匿名的 UI。
- 书评匿名 PATCH 由服务端严格要求 `library:read`、书籍存在和当前用户为该书评作者；他人请求返回 `404`，不改变数据。

## 后端实现

- 扩展 `_excerpt_row()` 和 `_book_review_row()`，集中计算 `isAnonymous`、可见用户名和切换能力，避免在路由或前端复制隐私判断。
- `create_item()` / `update_item()` 的摘录 SQL 增加 `is_anonymous`；通用 `validate("excerpts", ...)` 只接受布尔匿名字段，默认从合并后的已有记录保留原值。
- `_insert_book_review()`、`create_book_review()` 和阅读记录附带书评的事务写入增加匿名参数，并保持默认 false；阅读记录表单通过 `reviewAnonymous` 传递该选项。
- 新增 `update_book_review_anonymity()` repository 方法，按 `book_id + review_id + user_id` 更新，返回是否命中。
- `library_create_review()` 从认证用户传入用户名和匿名状态；`library_update_review()` 只调用匿名更新方法并拒绝非作者。
- 书籍删除和用户删除路径无需额外处理，新增列随行删除；数据库升级必须可重复执行。

## 浏览器实现

- 摘录新增/编辑表单增加“匿名发布” checkbox，编辑时回填 `isAnonymous`；提交时将布尔值放入已有 POST/PATCH payload。
- 摘录卡片使用 API 已计算的 `createdByName`，匿名时在作者可见视角追加“匿名”标识；其他用户只看到“匿名用户”。编辑/删除按钮仍由 `canManage` 控制。
- 书评发布表单和阅读记录中的可选书评均增加“匿名发布” checkbox；书评卡片按 `username` 和 `isAnonymous` 展示匿名标识。
- 当 `canToggleAnonymous` 为真时显示“设为匿名”或“取消匿名”按钮，调用新 PATCH 路由后重新加载当前书评列表；删除按钮逻辑不变。
- 所有新增文本继续通过 `escapeHtml` 渲染，复用现有 `request()`、toast、弹窗和刷新流程，不引入依赖。

## 兼容性、失败与回滚

- 旧客户端忽略新增字段即可继续读取；旧数据库首次启动会补列并把旧记录视为非匿名。
- 旧客户端创建摘录/书评不带匿名字段时，服务端按 false 处理。
- 匿名 PATCH 失败时不更新前端本地状态，弹窗保留并显示现有错误 toast；成功后以服务端列表为准刷新。
- 回滚应用代码时保留新增列和数据，不执行破坏性删除；后端回滚到旧版本时新增列不会影响旧 SQL。

## 测试策略

- 后端单元测试覆盖摘录/书评 mapper 的作者、管理员、其他用户三种可见性，以及匿名字段默认值和往返更新权限。
- API/路由测试覆盖匿名字段的创建、摘录更新、书评匿名 PATCH、他人拒绝、管理员既有删除权限和伪造作者字段不生效。
- 数据库升级/导入测试覆盖新增列幂等和历史记录默认非匿名。
- 浏览器侧至少运行 `node --check public/app.js`，并通过项目现有测试命令验证完整回归。
