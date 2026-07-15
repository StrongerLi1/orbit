# 实施计划：共享图书馆独立书评

## 顺序清单

1. [x] 在数据库初始化中增加 `book_reviews` 幂等建表；将书评纳入删除书籍和删除用户的清理路径。
2. [x] 在 repository 增加书评数据映射、列表、创建、owner/admin 删除；扩展阅读记录创建事务以支持可选书评。
3. [x] 在 FastAPI 增加书评 GET/POST/DELETE 路由，复用 `library:read` 和现有书籍存在性校验；扩展阅读记录 POST 的 `review` 校验。
4. [x] 增加后端测试：建模/SQL 参数契约、书评列表映射、普通用户 owner-only 删除、管理员删除他人评论、空/超长内容、阅读记录带书评和旧阅读记录兼容。
5. [x] 在浏览器 HTML/CSS/JS 增加书评按钮、书评弹窗、评论列表与删除操作；在新建阅读记录表单增加可选书评，编辑记录时不修改书评。
6. [x] 增加浏览器静态检查和必要的 DOM/请求行为测试；检查桌面与移动布局没有横向溢出。
7. [x] 运行完整质量检查，逐项对照 PRD 验收标准；如实现与 PRD 有偏差，先回到规划阶段修订文档。

## 验证命令

- `python3 -m compileall backend run.py tests`
- `node --check public/app.js`
- `python3 tests/test_library.py`
- `npm test`

## 风险文件与回滚点

- 高风险文件：`backend/database.py`、`backend/repository.py`、`backend/main.py`、`public/index.html`、`public/app.js`、`public/styles.css`、`tests/test_library.py`。
- 数据库回滚点：新表和索引保持不删；应用回滚后旧版本仍可访问旧阅读记录，新增书评数据等待后续版本处理。
- API 回滚点：阅读记录 POST 的 `review` 是可选字段，旧客户端不发送时保持原行为。
- UI 回滚点：书评功能可从图书卡片和阅读记录弹窗移除，不影响书籍下载、阅读记录查看和原有 owner-only 操作。

## 开始实现前检查

- [x] PRD 已记录独立书评、浏览器范围和不支持编辑的产品决策。
- [x] 设计已确认书评权限使用认证 UID，管理员使用现有 `users:manage` 权限。
- [x] 设计已确认书评从阅读记录创建时与阅读记录写入同一事务，编辑阅读日期不修改书评。
- [x] 用户审核本 `prd.md`、`design.md` 和本实施计划后，再运行 `task.py start` 进入实现阶段。

## 临时部署验证

- [x] 未提交 Git、未推送远程仓库，按用户要求直接部署当前运行文件。
- [x] 生产代码和 MySQL 回滚备份已创建于 `/opt/orbit-backups/orbit-reviews-20260715112538`。
- [x] 上传后远程 `orbit` 服务为 `active`，公网 `/api/ping` 返回 200。
- [x] 生产管理员登录、共享图书馆列表（14 本书）和书评列表接口均通过只读冒烟检查。
- [x] 生产 `book_reviews` 表已创建，当前书评数量为 0；未写入测试评论。
- [x] 前端缓存版本已更新为 `20260715-library-reviews`，公网首页已返回该版本号。
