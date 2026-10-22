# v05-observer-seams 交付证据索引（2026-10-22）

> 授权与留痕：PM Erwin 授权代行、AI 实施与审查、**非 Ringo 本人审查**；真人安全签核仍缺。
> 详细交付记录与边界见 [观察接缝交付记录（2026-10-22）](../../../evals/security/observers-2026-10-22.md)。本目录只做索引，不复制报告正本。

## 主线合并记录（main）

| 顺序 | 票 | PR | squash 提交 |
|---|---|---|---|
| 1 | [04 输出观察接线](../issues/04-api-output-observation.md)（先合下部依赖） | [#218](https://github.com/DrErwin/hackerthon-bank-agent/pull/218) 探针 | `23f6d42` |
| 2 | [05 F37/F38 记忆接口](../issues/05-api-memory-endpoints.md) | [#217](https://github.com/DrErwin/hackerthon-bank-agent/pull/217) | `c637342` |
| 3 | [01 不可信数据接缝](../issues/01-untrusted-data-seam.md) | [#219](https://github.com/DrErwin/hackerthon-bank-agent/pull/219) | `83ff583` |
| 4 | [02 资料投递 HTTP 通路](../issues/02-api-untrusted-material.md) | [#220](https://github.com/DrErwin/hackerthon-bank-agent/pull/220) | `ad2d4f7` |
| 5 | [04 输出观察接线](../issues/04-api-output-observation.md) | [#222](https://github.com/DrErwin/hackerthon-bank-agent/pull/222) | `3f8d71d` |
| 6 | [08 探针精度](../issues/08-probe-precision.md)（修 main 红） | [#224](https://github.com/DrErwin/hackerthon-bank-agent/pull/224) | `86e3752` |
| 7 | [09 用例分层](../issues/09-output-observation-test-layering.md) | [#225](https://github.com/DrErwin/hackerthon-bank-agent/pull/225) | `4ee336a` |
| 8 | [07 回复凭据门槛](../issues/07-reply-credential-gate.md) | [#223](https://github.com/DrErwin/hackerthon-bank-agent/pull/223) | `a35b35f` |
| 9 | [06 Demo 切片 E2E 与证据](../issues/06-demo-slice-evidence.md) | [#221](https://github.com/DrErwin/hackerthon-bank-agent/pull/221) | `b11a9ce` |
| 10 | [10 记忆真实载入证据](../issues/10-memory-live-load.md) | [#226](https://github.com/DrErwin/hackerthon-bank-agent/pull/226) | `7932eb4` |

## 证据正本（仓库内，按约定归档）

| 产物 | 位置 | gzip / 解压 SHA256 |
|---|---|---|
| 离线 Demo 切片 E2E（26 passed / 0 / 0，退出码 0） | [evals/observer-seams/evidence/2026-10-22/2026-10-22-offline-demo-slice.json.gz](../../../evals/observer-seams/evidence/2026-10-22/2026-10-22-offline-demo-slice.json.gz) | `8a0f286c…` / `6f47f7c5…`（全量见 manifest） |
| 离线 E2E 历史（票 07 前，保留不改写） | [同目录 pre-ticket07.json.gz](../../../evals/observer-seams/evidence/2026-10-22/2026-10-22-offline-demo-slice-pre-ticket07.json.gz) | `b82096ac…` / `57bd0448…` |
| 真实模型 Demo 切片（5 次调用，5/0/0） | [evals/security/evidence/2026-10-22/live-2026-10-22-observer-seams-demo-slice.json.gz](../../../evals/security/evidence/2026-10-22/live-2026-10-22-observer-seams-demo-slice.json.gz) | `fb7ee510…` / `470debce…` |
| 记忆真实载入（1 次调用，J01–J04 全 Passed） | [evals/security/evidence/2026-10-22/live-2026-10-22-observer-seams-memory-load.json.gz](../../../evals/security/evidence/2026-10-22/live-2026-10-22-observer-seams-memory-load.json.gz) | `e12ddeb1…` / `d5d083b5…` |
| 离线 React 页面回归（2 场景 Passed） | [evals/security/evidence/2026-10-22/2026-10-22-react-offline-c001-p002.json.gz](../../../evals/security/evidence/2026-10-22/2026-10-22-react-offline-c001-p002.json.gz) + `react-browser/` 截图 | `C12B16D7…` / `AEA5BB22…` |

## 回归

- main `a35b35f` 工作树全量 `pytest -q backend`：**1233 passed / 0 failed**；mockbank 评测 14 passed。
- CI：各 PR 的 Repository checks 全绿；合并后 main push CI 绿（票 08 修复前曾红，原因与修复见票 08）。
