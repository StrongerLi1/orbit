# 实施计划：摘录归属与个人写权限

## 执行顺序

1. 在 `backend/database.py` 增加摘录归属列、启动时幂等迁移和历史 `admin` 归属回填；同步 JSON 导入字段。
2. 在 `backend/repository.py` 扩展摘录 mapper、列表/单条查询上下文、创建归属写入和 owner 查询辅助。
3. 在 `backend/main.py` 从认证用户写入新摘录，并为摘录 PATCH/DELETE 增加管理员或 owner 校验；补充后端自检覆盖验证和权限边界。
4. 在 `public/app.js` 增加摘录人展示、编辑按钮、编辑回填与 PATCH 提交。
5. 在 Android `Models.kt`、`OrbitState.kt`、`Screens.kt` 增加字段解码、编辑 API 和编辑 UI，保持客户端只消费服务端 `canManage`。
6. 更新 README / 认证或 RBAC 文档中的摘录数据语义，删除“所有业务数据共享写入”的过时表述，明确摘录例外规则。
7. 运行质量检查；若发现 PRD 或跨层契约缺口，先回到规划阶段修正再继续。

## 验证命令

- `npm test`
- `node --check public/app.js`
- `python3 -m compileall backend run.py tests`
- `cd android && ./gradlew testDebugUnitTest lintDebug assembleDebug`
- 若本地 MySQL/Redis 可用：启动 API，使用 admin、普通用户 A、普通用户 B 验证摘录创建、列表、编辑、删除和跨用户 `403`。

## 必测场景

- 新摘录忽略客户端传入的 `createdByName` / owner 字段，记录当前认证用户。
- 旧表无归属列时启动自动添加；旧行显示 `admin`，管理员可编辑删除，普通用户不可操作。
- 普通用户编辑/删除自己的摘录成功。
- 普通用户编辑/删除他人的摘录返回 `403`，摘录内容保持不变。
- 管理员编辑/删除任意用户摘录成功。
- GET 列表对普通用户仍返回所有摘录，且只有可操作项带 `canManage=true`。
- 浏览器与 Android 编辑表单完整回填并保存内容、作者、出处、日期、备注。

## 风险文件与回滚点

- 高风险：`backend/database.py` 的启动迁移顺序、`backend/repository.py` 的通用 collection 查询、`backend/main.py` 的通用路由。
- 中风险：浏览器通用 modal 提交流程、Android 摘录对话框状态回填。
- 回滚点：先保留数据库新增列和兼容默认值，再回滚客户端；不要执行删除列或清空历史归属数据。

## 开始执行前检查

- [ ] PRD 已确认管理员全量管理、普通用户 owner-only、所有用户可读。
- [ ] 设计已确认 API 字段为 `createdByName` / `canManage`，不暴露内部 user ID。
- [ ] 已读取 backend database/shared-library 与 frontend component/android 指南。
- [ ] `task.py start` 后再修改业务代码。
