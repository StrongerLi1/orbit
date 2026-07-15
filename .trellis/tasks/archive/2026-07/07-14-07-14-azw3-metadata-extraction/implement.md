# AZW3 书目信息与封面解析实施计划

## Implementation checklist

1. [x] 在 `backend/library_files.py` 增加有界大端整数、PalmDB 记录表和 record 读取辅助函数。
2. [x] 解析 MOBI 头的编码、full-name、首资源索引与 EXTH 区域。
3. [x] 提取 EXTH 503 书名、全部 EXTH 100 作者和 EXTH 201 封面偏移。
4. [x] 复用现有封面签名、大小限制和元数据优先级，只在 `.azw3` 分支启用。
5. [x] 在 `tests/test_library.py` 构造最小 AZW3 fixture，覆盖 UTF-8 元数据、多个作者、full-name 回退、JPEG/PNG/WebP 封面、手写覆盖和畸形/越界输入。
6. [x] 更新共享图书馆契约、README 的格式能力说明和任务验收结果。

## Validation commands

```bash
python3 tests/test_library.py
npm test
python3 -m pip check
git diff --check
```

## Risk points

- 所有文件偏移先与 `stat().st_size` 和相邻记录边界比较，再执行 seek/read。
- 解析失败只能丢失自动识别结果，不能改变合法 AZW3 的上传校验结果。
- 手写字段和手动封面必须继续覆盖解析结果。
- 不触碰当前工作区中 LX Music、HTTPS、Android 和视觉优化任务的未提交改动。

## Review gate

- 确认只处理 `.azw3`，不顺带扩展 `.mobi`。
- 确认 GIF/BMP 不转换，DRM/正文/混合 KF7-KF8 深度解析不在范围内。
- 用户批准本计划后运行 `task.py start`，再进入实现。

## Result

- `python3 tests/test_library.py`：通过。
- `npm test`：通过，包括现有 EPUB、PDF、MOBI、TXT、阅读记录及其他项目测试。
- `python3 -m pip check`：通过，无损坏依赖。
- `git diff --check`：通过。
- 额外对 1000 个带 `BOOKMOBI` 签名的随机畸形输入执行解析烟测，无未捕获异常。

## Bug Analysis: MOBI header fields read 16 bytes too late

### 1. Root Cause Category

- **Category**: E - Implicit Assumption, plus D - Test Coverage Gap.
- **Specific Cause**: MOBI-relative offsets were treated as later record-0 offsets. The synthetic fixture repeated the same wrong layout, so implementation and test falsely agreed.

### 2. Why the Initial Fix Passed

1. Synthetic cover offset `0` and first resource `1` did not distinguish the correct first-image field from the wrong later field.
2. No real Kindlegen-generated AZW3 was checked before the first deployment.

### 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|----------|-----------|-----------------|--------|
| P0 | Test coverage | Use non-zero EXTH 201, decoy data at the old field, and a different first-image index. | DONE |
| P0 | Documentation | Record both MOBI-relative and record-0 byte offsets in the shared-library contract. | DONE |
| P1 | Real-file smoke test | Verify the reported AZW3 resolves record 107 as a 124080-byte JPEG before deployment. | DONE |

### 4. Systematic Expansion

- **Similar Issues**: MOBI full-name offset and length shared the same 16-byte displacement and were fixed together.
- **Design Improvement**: Code now states MOBI-relative offsets as `16 + field_offset` instead of unexplained record-0 literals.
- **Process Improvement**: Binary-format fixtures must contain decoy values at plausible wrong offsets rather than mirroring only the implementation's happy path.

### 5. Knowledge Capture

- [x] Updated the backend shared-library contract locally.
- [x] Updated the synthetic fixture and checked the reported real AZW3.
- [x] Kept `.trellis/` local-only per repository policy; it will not be committed or pushed.

## PDF First-Page Cover Plan

1. [x] 固定并安装 pypdfium2 运行时依赖。
2. [x] 扩展 `_pdf_metadata()`，有界渲染第一页并编码封面。
3. [x] 增加第一页/多页、尺寸上限、手动覆盖和软失败测试。
4. [x] 更新 README 与共享图书馆契约。
5. [x] 运行 `npm test`、`pip check`、真实 PDF 烟测与 `git diff --check`。

部署前仍需单独获得用户确认；产品提交排除 `.trellis/`。

## PDF Validation Result

- `python3 tests/test_library.py`：通过，包括第一页、多页、超大页、加密、零页、损坏文件、大小上限和上传落盘。
- `npm test`：通过。
- `python3 -m pip check`：通过，无损坏依赖。
- 真实 PDF 烟测：生成 418005 字节 RGB JPEG，尺寸 `1132x1600`。
- `git diff --check`：通过。

## PDF Deployment Result

- 已部署至 `/opt/orbit`，生产虚拟环境安装 `pillow==10.4.0` 与 `pypdfium2==5.11.0`。
- 服务器图书馆测试与真实 PDF 烟测通过；Orbit 重启后为 `active/running`。
- 直连 `/api/auth/me` 返回预期 `401`，公网 `/api/ping` 返回 `200`。
- 回滚备份：`/opt/orbit-backups/20260715-102403-pdf-first-page`。
- 暂存目录已清理，`.trellis/` 未上传。
