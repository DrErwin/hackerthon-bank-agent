# 2026-10-21 完整前端主入口上的转账全量回归

本批对应 v0.4 前端票 05（替换主入口，PR #201）与评测适配 PR #203；按 PM 2026-10-21 00:44 授权由 AI 代执行，非本人审查。原始 JSON 以 gzip 保存，解压后 sha256 为 `A7F1E809FB2B87F0C4B6A1DF58CAF23BA627155D4D00010FB05C61305A201E5B`。

## 执行环境（干净提交）

| 项 | 值 |
|---|---|
| 代码 | main `cd976b9b5b5b76ebd75f6a6d89861eba1b6fc061`（含 PR #201 主入口替换、PR #203 脚本适配；`dirty_paths=[]`） |
| 前端产物 | `frontend/dist/index.html` sha256 `786CCAA852164C6D7CF038E9B45BEBEEF4A0771E5D086AEB923CAA33694DA3D9`（OBS 样本 `react.frontend_build` 一致） |
| 入口 | `python evals/transfer/run_live_eval.py --react-dist frontend/dist --jobs 1` |
| 运行 | 离线固定规划器 + 真实 Harness/安全门/网关/隔离 MockBankService + 真实 TCP HTTP + Chromium（0 次模型调用、0 密钥、0 外网） |
| 时间 | started `2026-10-21T01:24:29+08:00`，串行 153 样本 |

## 结果

| 项 | 结果 |
|---|---|
| 样本 | 153/153 运行 |
| 状态 | **152 Passed / 0 Failed / 1 Blocked** |
| 标准任务 | 21/21（100%） |
| 缺项追问 | 8/8（100%） |
| 红线违规断言 | **0** |
| 红线结论 | **Unverified**（`missing_evidence=true`，唯一缺口为 TF-OBS-05） |
| React 证据 | OBS-03 / 04 / 06 / 07 **Passed**（构建哈希一致）；OBS-05 **Blocked** |
| 验收 | NotAccepted（本报告不是 v0.4 联合验收或 Ringo 专业安全结论） |

**TF-OBS-05 Blocked 的如实原因**：v0.4 完整前端是单会话入口，没有「切换对话」动作，切换后迟到响应的场景无法经新 UI 投递；等价保护由 `frontend/src/ui-recovery.test.tsx`（迟到历史不进入当前对话）覆盖，旧前端证据见 [2026-10-11](../2026-10-11/offline-react-full-20261011.json.gz)。未用变通断言伪装通过，故红线整体为 Unverified。

**并行运行偶发**：同一提交另跑 `--jobs 4` 时出现一次 TF-RCV-08（`redaction.credential`）偶发失败，单样本串行复跑通过；最终归档以串行 `--jobs 1` 结果为准，并行结果仅作为抖动观察记录。

## 文件

| 文件 | 说明 |
|---|---|
| `offline-react-full-20261021.json.gz` | 原始报告；解压 sha256 前 16 位 `A7F1E809FB2B87F0` |
| `offline-react-full-20261021.md` | 报告摘要（含报告 sha256） |
| `offline-react-full-20261021-browser/TF-OBS-03.png` | sha256 `1B79A72C24A5F7CF4135B2CBB255593A4BEE93095F90DE3714F166ED9BABA1D9` |
| `offline-react-full-20261021-browser/TF-OBS-04.png` | sha256 `7BDFD4C1CC6A1C7470A0FAAD6453932066461D6D4BEDFE5B55B4CAB84060BAA0` |
| `offline-react-full-20261021-browser/TF-OBS-06.png` | sha256 `49D460702B28C356123AF5FD5676D290F194702DF2F54F14264C9D49ACD25D89` |
| `offline-react-full-20261021-browser/TF-OBS-07.png` | sha256 `629B8B79DBDCC6A7F13C30814AA2CD7EA0972377D9BE50E4B296E434C154BBAB` |
| `manifest.json` | 运行目录、revision、summary、报告 sha256 |

旧批次（2026-10-11 全量 153/153，简易前端入口）保持原报告与 manifest，不互相替代。
