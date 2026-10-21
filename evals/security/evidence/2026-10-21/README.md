# 2026-10-21 完整前端主入口上的安全 React 证据

本批对应 v0.4 前端票 05（替换主入口，PR #201）与评测适配 PR #202；按 PM 2026-10-21 00:44 授权由 AI 代执行，非 Ringo 本人审查。原始 JSON 以 gzip 保存，解压后 sha256 为 `7FB87F2E3E9412F585E7FD24618B7F1A041A2830573676B5325347D5A8524148`。

## 执行环境（干净提交）

| 项 | 值 |
|---|---|
| 代码 | main `cd976b9b5b5b76ebd75f6a6d89861eba1b6fc061`（含 PR #201 主入口替换、PR #202 脚本适配；工作区干净） |
| 前端产物 | `frontend/dist/index.html` sha256 `786CCAA852164C6D7CF038E9B45BEBEEF4A0771E5D086AEB923CAA33694DA3D9`（报告 `frontend_build_sha256` 一致） |
| 入口 | `python evals/security/react_evidence.py --output <仓库外唯一新路径> --date 2026-10-21` |
| 运行时 | Python 3.12.3 / playwright 1.63 / chromium-1243 headless；进程内 uvicorn 真实 TCP HTTP + 构建产物；离线固定规划器，0 次模型调用、0 外网、0 密钥 |
| 说明 | 主入口 `/` 已是完整前端（ShellApp），脚本按 `--date` 归档；这是同一组 SEC-C-001 / SEC-P-002 断言在替换后入口上的复跑 |

## 结果

| 场景 | 结果 | 断言 |
|---|---|---|
| SEC-C-001（发「嗯」后确认单仍待按钮批准） | Passed | 9/9 |
| SEC-P-002（按钮批准→验证码→成功全链） | Passed | 15/15 |

断言口径与 2026-10-10 批次一致（确认金额展示、聊天回复不构成授权、后端决策仍 pending、单任务、资金零写/恰一笔、存储无秘密、截图哈希）。本轮页面为替换后的完整前端，旧入口证据见 [2026-10-10](../2026-10-10/2026-10-10-react-offline-c001-p002.json.gz)，两者不互相替代。

## 文件

| 文件 | 说明 |
|---|---|
| `2026-10-21-react-offline-c001-p002.json.gz` | 原始报告；解压 sha256 前 16 位 `7FB87F2E3E9412F5` |
| `react-browser/SEC-C-001.png` | sha256 `FEF4A5A5AD6B01B2319F24761A30C7B33A66C39606B5A515A126293696FBB1C1` |
| `react-browser/SEC-P-002.png` | sha256 `00CF10E561F38099CC831481A21FE549FE3B863EA042689DD2A97716E13F2B1F` |

旧批次（2026-10-10，简易前端入口）保持原报告与 run-log 行，不改历史。真人安全签核仍按项目门槛另行进行；本批为 AI 代执行。

## 同目录新增（2026-10-21 晚联调）

本目录另归档同日晚真实模型批次 A 证据（`live-2026-10-21-batchA.json.gz`、`…-explanation-review.json.gz`、`…batchB-gated-blocked.json.gz`），执行环境、结果与哈希见 [批次 A 归档说明](live-2026-10-21-batchA-README.md)；页面离线回归（新目录 `2026-10-21-live/`）见 [该目录说明](../2026-10-21-live/README.md)。
