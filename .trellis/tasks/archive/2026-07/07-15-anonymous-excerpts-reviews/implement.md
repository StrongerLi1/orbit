# 实施计划：Web 摘录与书评匿名展示

## 开始前检查

- [x] 复核 `prd.md`、`design.md` 与现有摘录归属/书评契约一致；只修改 Web 相关文件，不触碰 Android。
- [x] 保留工作区已有未提交改动，不覆盖 `.trellis/` 外与本任务无关的用户修改。
- [x] 开始编码前加载 `trellis-before-dev`，读取 backend/frontend 相关具体规范。

## 实施步骤

1. **数据库兼容**
   - 在 `backend/database.py` 为 `excerpts`、`book_reviews` 增加 `is_anonymous` 默认列和幂等升级。
   - 更新 JSON 导入的摘录 INSERT，显式写入默认 false。
   - 检查旧数据库启动和旧客户端缺省 payload 的兼容行为。

2. **摘录后端契约**
   - 在 `backend/main.py` 的摘录校验中接受严格布尔匿名字段，并保持编辑时已有状态。
   - 在 `backend/repository.py` 更新摘录 mapper、创建 SQL、更新 SQL，按当前用户计算展示用户名与 `isAnonymous`。
   - 确认作者/管理员/其他普通用户的读取、编辑、删除授权不被匿名字段改变。

3. **书评后端契约**
   - 扩展书评 mapper、创建 SQL、阅读记录附带书评的事务写入，默认非匿名。
   - 阅读记录创建表单的可选书评同步传递匿名状态，保持编辑阅读日期时不创建或修改书评。
   - 增加作者限定的匿名状态更新 repository 方法和 `PATCH` 路由；只接受匿名字段，不开放正文编辑。
   - 对他人 PATCH 返回既有风格的 `404`，并保留管理员删除行为。

4. **浏览器 UI**
   - 摘录表单增加匿名 checkbox，编辑回填状态，卡片增加匿名标识并保持现有管理按钮。
   - 书评表单增加匿名 checkbox，列表按服务端展示名渲染匿名状态。
   - 增加作者自己的匿名切换按钮、PATCH 请求、成功刷新和错误 toast。
   - 检查所有新增输出经过 `escapeHtml`，移动端布局不出现横向溢出。

5. **测试与文档同步**
   - 扩展 `tests/test_excerpt_permissions.py` 和 `tests/test_library.py`，必要时新增针对匿名映射/路由的测试。
   - 运行 Python 编译、Node 语法检查和项目既有测试命令；修复回归。
   - 若实现过程中发现可复用的匿名展示契约，再更新对应 spec；不把 `.trellis/` 目录加入产品提交。

## 验证命令

- `python3 -m compileall backend run.py tests`
- `node --check public/app.js`
- `python3 tests/test_excerpt_permissions.py`
- `python3 tests/test_library.py`
- `npm test`

## 风险与回滚点

- 风险：匿名记录的展示名称必须由服务端按当前用户计算，否则前端可能泄露真实用户名；所有客户端都只消费展示字段。
- 风险：通用摘录 PATCH 是“已有记录 + 请求体”校验，匿名字段缺失时必须保留原值而不是重置为 false。
- 风险：阅读记录附带书评的事务写入不能因新增参数破坏旧调用；默认值必须保持 false。
- 回滚点：数据库列添加是向后兼容的；若 UI/API 出问题，可先回滚应用代码并保留列和数据，禁止删除列。

## 启动前审核门

- [x] PRD 无未决产品问题，设计覆盖数据、权限、API、UI、迁移和回滚。
- [x] 用户审核并同意 `prd.md`、`design.md`、`implement.md` 后，再执行 `task.py start` 进入实现阶段。
