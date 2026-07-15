# 实施计划：待办和计划按用户隔离

## 执行顺序

1. 在 `backend/database.py` 为 `todos`、`plans` 增加归属列和索引，补充幂等升级，并在管理员 seed 后统一回填历史空归属记录；同步 JSON 导入写入路径。
2. 在 `backend/repository.py` 增加用户隔离 collection 约束，扩展列表/单条查询、创建、更新、删除的用户上下文和 SQL 条件。
3. 在 `backend/main.py` 的通用 collection 路由中将认证用户传入待办/计划 repository 操作，确保跨用户 ID 不可读写，同时保持摘录权限逻辑不变。
4. 增加后端自检，覆盖隔离 collection、客户端归属字段忽略、历史回填 SQL/迁移约定和验证器兼容行为；必要时补充 repository mock 测试。
5. 检查 `public/app.js` 和 Android 客户端：确认现有请求无需用户参数，验证账号切换后的内容状态只由服务端集合驱动；若发现错误处理或类型契约缺口，只做最小客户端修正。
6. 更新必要的项目文档/客户端检查项，明确待办和计划是用户私有数据，避免留下“业务数据全部共享”的过时描述。
7. 运行完整质量检查；若发现 PRD 或跨层契约缺口，先回到规划阶段修正再继续。

## 验证命令

- `npm test`
- `node --check public/app.js`
- `python3 -m compileall backend run.py tests`
- `cd android && ./gradlew testDebugUnitTest lintDebug assembleDebug`
- 若本地 MySQL/Redis 可用：使用管理员、普通用户 A、普通用户 B 验证创建、列表、已知 ID 访问、更新、删除和账号切换。

## 必测场景

- 新待办/计划始终记录当前认证用户 ID，客户端传入的 owner 字段不会生效。
- 用户 A 的列表和仪表盘不出现用户 B 的数据，管理员也只出现自己的数据。
- 用户 B 使用用户 A 的记录 ID 进行 GET/PATCH/DELETE 时返回 404，数据不变。
- 用户 A 可以完成/重开待办、清空自己的已完成待办、增加/撤销自己的计划打卡。
- 旧表缺少归属列时启动成功；旧待办/计划空归属只回填管理员，已有非空归属不被覆盖；重复启动幂等。
- 浏览器和 Android 登录、登出、重新登录不同账号后不会残留前一账号的待办/计划。

## 风险文件与回滚点

- 高风险：`backend/database.py` 的启动迁移/回填顺序、`backend/repository.py` 的通用 collection 查询、`backend/main.py` 的通用路由。
- 中风险：JSON 导入的字段兼容和通用 mutation 重新加载流程。
- 回滚点：先保留新增列、索引和历史归属，再回滚应用逻辑；不要执行删除列、清空数据或覆盖非空 owner。

## 开始执行前检查

- [x] 已确认管理员也只看自己的待办和计划。
- [x] 已确认全部历史无归属数据绑定到管理员账号。
- [x] PRD、技术设计和实施计划已完成，等待用户审核。
- [x] `task.py start` 后再修改业务代码。
