# 技术设计：摘录归属与个人写权限

## 架构边界

摘录归属是一个跨层契约：MySQL `excerpts` -> `backend.database` 启动升级 -> `backend.repository` 数据映射与写入 -> FastAPI 通用摘录路由 -> 浏览器 `public/app.js` 与 Android Compose 客户端。

## 数据模型与迁移

- 在 `excerpts` 增加 `owner_user_id VARCHAR(64)`，新建记录写认证上下文中的当前用户 UID（`user["id"]`）。
- 增加 `owner_name VARCHAR(64)` 作为创建时的用户名快照，API 展示使用它；这样用户账号被删除后摘录仍保留可读的摘录人文本。
- 新表定义给 `owner_user_id` 空值、`owner_name` 默认 `admin`，兼容旧数据；现有表通过 `information_schema.COLUMNS` 检测后幂等添加列。
- 启动完成用户和 RBAC seed 后，将 `owner_user_id` 为空的历史摘录绑定到现有管理员账号（优先配置的 `ADMIN_USERNAME`，再使用 `is_admin = 1` 的账号）。没有可绑定账号时保留空 ID，但仍以 `admin` 名称展示，管理员可管理这些历史记录。
- JSON 导入的历史摘录同样使用 `admin` 默认归属；新建摘录不从客户端 payload 读取归属字段。

## API 契约

摘录响应继续返回现有字段，并增加：

```json
{
  "createdByName": "alice",
  "canManage": true
}
```

- `createdByName` 是摘录人用户名快照；不返回 `owner_user_id`。
- `canManage` 由服务端按“当前用户是管理员或归属 ID 等于当前用户 ID”计算，编辑和删除入口共用该能力标记。
- `GET /api/excerpts` 仍返回全部摘录。
- `POST /api/excerpts` 从认证上下文写入当前用户 ID 和用户名。
- `PATCH/DELETE /api/excerpts/{id}` 先验证摘录存在，再验证管理员或归属用户；非管理员操作他人摘录返回 `403`，不执行写操作。
- 其他 collection 继续沿用现有共享写权限逻辑，避免本次需求扩大影响面。

## 后端实现

- `require_permission(request, "content:write")` 仍负责登录和基础业务写权限。
- 在摘录更新/删除路由增加集中式归属判断；不要依赖前端隐藏按钮实现安全控制。
- repository 的摘录 mapper 使用 `owner_name`，`list_items` / `get_item` 接收当前用户上下文计算 `canManage`；创建函数显式接收当前用户。
- 添加一个小型 owner 查询/检查辅助，避免将内部用户 ID返回给客户端，同时让更新和删除在数据库真实归属上校验。

## 浏览器客户端

- 摘录卡片显示 `createdByName`，并在 `canManage` 时显示编辑和删除按钮。
- 复用现有 item modal：打开编辑时回填摘录字段，提交使用 `PATCH`；新增仍使用 `POST`。
- 编辑和删除都通过现有 `mutate` / `request` 流程，服务端拒绝时显示已有 toast 错误。

## Android 客户端

- `Excerpt` 增加 `createdByName` 和 `canManage`，由 JSON 解码器提供默认值以兼容服务端短暂缺字段的情况。
- 摘录卡片显示摘录人；`canManage` 为真时展示编辑、删除操作。
- 扩展现有 `ExcerptDialog` 支持新增和编辑两种模式，编辑时回填五个可编辑字段；`OrbitState` 新增更新摘录方法，仍复用现有 `mutate`。
- Android 只调用现有 `/api/excerpts` 路由，不复制服务端权限判断。

## 失败与回滚

- 数据库列添加和回填均为幂等启动步骤；发布异常时旧客户端仍可读取新增字段之外的原有字段。
- 如果客户端部署回滚，后端响应新增字段不会影响现有字段解析；如果后端回滚到无新列版本，需要同时回滚数据库代码并保留列，不能删除列。
- 权限判断失败不改动数据；更新/删除后客户端重新加载摘录列表，避免本地状态与服务器分叉。

## 关键取舍

- 采用用户 UID 做授权、用户名快照做展示，避免用户名文本可变、客户端伪造或账号删除影响权限判定和历史可读性。
- 管理员绕过 owner 检查是已确认的产品规则；普通用户仍严格按 owner ID 比较。
- 本次只给摘录增加归属，不抽象所有 collection 的 ownership 框架，保持改动范围最小。
