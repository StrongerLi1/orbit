# 技术设计：待办和计划按用户隔离

## 架构边界

用户归属是一个跨层契约：MySQL `todos` / `plans` -> `backend.database` 启动升级与历史回填 -> `backend.repository` 查询和写入约束 -> FastAPI 通用 collection 路由 -> 浏览器和 Android 现有内容加载/变更流程。

本次隔离只作用于 `todos` 和 `plans`。书签、文件夹、摘录、书库和 Hermes 对话保持现有语义。`server.js` 是无认证的旧本地 JSON 服务，当前 `npm start` 和部署入口使用 `run.py` / FastAPI，因此不把它当作认证数据源或本次隔离的实现入口。

## 数据模型与迁移

- 在 `todos`、`plans` 增加 `owner_user_id VARCHAR(64) NULL DEFAULT NULL`，并为 `(owner_user_id, created_at)` 增加查询索引。
- 新表定义直接包含归属列；已有表通过 `information_schema.COLUMNS` 检测后幂等 `ALTER TABLE`。
- 数据库表先完成创建/升级，再执行 JSON 导入和用户/RBAC seed；管理员 seed 完成后执行统一的历史回填，将两个表中空归属或空字符串归属绑定到配置的管理员账号，找不到时回退到首个管理员账号。
- JSON 导入阶段允许暂时写入空归属，随后由同一回填步骤绑定管理员；不会读取客户端 JSON 中可能存在的归属字段。
- 回填只更新空归属行，不覆盖已经绑定的记录，重复启动不会改变已归属数据。

## Repository 与 API 契约

- 定义用户隔离 collection 集合，例如 `USER_SCOPED_COLLECTIONS = {"todos", "plans"}`，让列表、单条读取、更新和删除共享同一判断，避免两个 collection 分支漂移。
- `list_items` / `get_item` 对用户隔离 collection 使用 `owner_user_id = current_user_id`；跨用户已知 ID 按不存在处理并返回 404，避免泄露记录存在性。
- `create_item` 对用户隔离 collection 强制要求认证用户上下文，并从 `current_user["id"]` 写入归属；验证器只返回允许的业务字段，忽略客户端传入的 owner 字段。
- `update_item` / `delete_item` 接收当前用户上下文或已过滤的记录，并在真实 SQL 条件中保留归属约束，避免只依赖前置 GET 检查的竞态窗口。
- `/api/todos` 和 `/api/plans` 继续使用现有路径和响应字段；通用路由将当前用户传入 repository。权限仍由 `content:read` / `content:write` 控制，不新增 RBAC 权限。
- 其他 collection 的现有共享查询和摘录专属权限逻辑不变。

## 客户端行为

- 浏览器和 Android 无需新增用户筛选参数；登录后请求现有 `/api/todos`、`/api/plans` 即得到当前用户集合，现有仪表盘、统计、完成/打卡和删除状态自然基于隔离后的响应工作。
- 保持客户端不发送 owner 字段、不缓存跨账号数据；登出和账号切换继续通过现有会话重置/重新加载流程清空并替换内容状态。
- 若后端对跨用户 ID 返回 404，现有 mutation 错误流程显示服务器错误并重新加载，不在客户端复制归属判断。

## 兼容性、风险与回滚

- 新增 nullable 列和索引对旧客户端透明；API 不增加必需响应字段。
- 发布顺序先部署可幂等升级数据库的后端，再启用归属过滤；旧数据在同一次启动中回填管理员。
- 若客户端回滚，旧客户端仍可使用现有 API，但只能看到当前用户集合；若后端代码回滚，保留新增列不会破坏旧 SQL，但会暂时恢复共享读取，因此回滚后应尽快重新部署隔离版本。
- 不删除历史数据、不删除列、不覆盖已有非空归属；出现问题可回滚应用代码并保留数据库结构。
