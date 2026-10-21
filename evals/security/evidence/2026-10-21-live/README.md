# 2026-10-21 联调夜批：页面离线回归（完整前端主入口）

本目录是 2026-10-21 晚联调（真实模型批次 A + 页面回归）的页面部分，按 [Erwin 联调清单](../../live-model-page-run-plan.md) §4.4 执行；留痕：**PM Erwin 授权代行执行、AI 整理与审查、非 Ringo 本人审查；真人安全签核仍缺**。

## 为什么单开目录

`evidence/2026-10-21/` 已有同日早些时候归档的 `react-browser/SEC-C-001.png`、`SEC-P-002.png`，脚本按 `--date` 写同名截图时会拒绝覆盖。本批用 `--date 2026-10-21-live` 另开目录，旧证据原样保留、不互相替代。

## 执行环境

| 项 | 值 |
|---|---|
| 代码 | main `b32ea6e`（含 #211/#212/#213 安全离线收尾与账单证据；工作区干净） |
| 前端产物 | `frontend/dist/index.html` sha256 `786CCAA852164C6D7CF038E9B45BEBEEF4A0771E5D086AEB923CAA33694DA3D9`（#201 产物，与报告 `frontend_build_sha256` 一致） |
| 入口 | `python evals/security/react_evidence.py --output <仓库外唯一新路径> --date 2026-10-21-live` |
| 运行时 | Python 3.12.3 / playwright chromium headless；进程内 uvicorn 真实 TCP HTTP + 构建版 React；离线固定规划器，**0 次模型调用、0 外网、0 密钥** |
| 耗时 | 35.5 秒（2026-10-21 22:12 前后） |

## 结果

| 场景 | 结果 | 检查项 |
|---|---|---|
| SEC-C-001（聊天回「嗯」不构成批准，确认单仍待按钮） | Passed | 9/9 |
| SEC-P-002（按钮批准 → 专用验证码 → 成功全链） | Passed | 15/15 |

24 项检查全过、无失败项。断言口径与 `evidence/2026-10-21/`、`evidence/2026-10-10/` 的同类批次一致。

## 文件

| 文件 | 说明 |
|---|---|
| `2026-10-21-react-offline-c001-p002-live.json.gz` | 原始报告；gzip sha256 `614E635294AB34491732C9AC2FA4976F961A18D0F2AB6AD1B8387C6F00A4C746`，解压 sha256 `FAB45BD47FBBCCBAF2DCFA0D2FF342B0581B5214E9120A384FE25DADDCAE7E53`（gzip 用 `filename=""`、`mtime=0`，解压与原 JSON 逐字节一致） |
| `react-browser/SEC-C-001.png` | sha256 `E6C455FF8B4644F167EAF2A74BB6D2A6CD1427BE8B658BA94ED9396CA59C08F1` |
| `react-browser/SEC-P-002.png` | sha256 `217FED4D62096A3BC4251BF649CB030C10D7E5194454328125061C0FFB6A9646` |

## 边界

- 本批**只证明页面能正确展示后端决策**，不证明真实模型在页面上的表现；真实模型页面 6 步走查属 Erwin 人工步骤，本会话未执行则如实标 Pending，不伪造截图或勾选。
- 旧目录（2026-10-21、2026-10-10 等）的报告与截图不改写。
