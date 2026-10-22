# v0.5.0 需求：联动、系统验收与体验打磨

> 阶段目标：完成跨场景联动（由 v0.4 移至，2026-10-11 项目负责人决定），用完整业务和安全评测证明核心系统可用，并修复影响演示和评分的问题。

## 背景

三个核心场景完成后，需要统一验证任务完成率、安全合规、恢复能力和适老化体验。

## 范围

- 完成跨场景联动公开能力和评测（v0.4 移至：先账单后联动；涉及资金的逐笔确认、部分成功与收尾）。
- 运行三场景任务评测和安全评测。
- 完成跨模块集成测试与缺陷修复。
- 核对审计证据、恢复、防重复和用户状态表达。
- 补齐契约已定义、尚未实现的管理端审计导出：F35 `POST /admin/audit/exports`（按固定筛选范围导出，返回 `ExportView(kind=audit)`）与 F24 的 audit 下载分支（核验独立管理权限 + 创建时固定的导出范围；数据源用既有 `audit/journal` 只读端）。来源 [Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)：2026-10-13 PM 决定**不进 v0.4、挂 v0.5**；**2026-10-21 已交付**——[v05-platform/01](../../../.scratch/v05-platform/issues/01-audit-export.md)（[PR #214](https://github.com/DrErwin/hackerthon-bank-agent/pull/214) squash `b01ceb9` 已合入）落地 F35 与 F24 audit 分支，跨 `backend/app/api/` + `backend/app/audit/` 两个底座目录一次交付（PM 授权留痕）；管理前端入口按 PM 决定本次不做（已知限制），历史轮次导出维持与 F33/F34 一致的当前轮次口径。
- 可信观察接缝与四项体验能力（[Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)，PM 2026-10-22 决定当日实施）：**2026-10-22 已交付**——[v05-observer-seams](../../../.scratch/v05-observer-seams/spec.md) 九张实施票 + 记忆真实载入证据票合入 main：工具返回与用户投递资料以「不可信数据」块进模型提示（`untrusted_content` 按契约 §8 兼容扩展）、F37/F38 记忆查看/删除 HTTP、输出侧敏感信息探针接回复/SSE/导出出口；离线 E2E 26 checked、真实模型小批量（GLM Coding Plan 6 次调用）全部 Passed、v0.4 已验断言不回退；v0.4 例外 E7 部分解除。未做：前端粘贴框/记忆管理页（另开前端票）、生产检测器装配（#160）、真实页面粘贴走查、批次 B/C 全量。详见 [观察接缝交付记录](../../../evals/security/observers-2026-10-22.md)。
- 打磨关键演示路径和适老化交互。
- 前端剩余范围：**账单业务插槽（票 04）与替换简易前端 + 全面回归 / 适老化走查（票 05）已于 2026-10-20 01:45 由 PM 决定留在 v0.4 完成、不顺延**（01:41 版本曾记为顺延 v0.5，同日撤回）；v0.5 前端只保留**订阅场景 05 前端插槽（v0.5 第一优先，已定）**，以及 v0.4 收口时如实登记的已知非阻塞项（如旧会话历史条目逐条 F14/F16 刷新返回 409 `SESSION_RECONFIRMATION_REQUIRED`，F39 视图已直接渲染、页面无缺失）。票据与证据入口：[`.scratch/liangshuang-frontend-complete/`](../../../.scratch/liangshuang-frontend-complete/spec.md)、[Issue #89](https://github.com/DrErwin/hackerthon-bank-agent/issues/89)；v0.4 已交付的转账插槽（[PR #142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142) squash `92ee700`）不回退。
- 形成核心能力验收记录。

## 验收标准

1. 三个核心场景的主要和关键异常路径通过。
2. 安全评测能够证明确认、权限、注入防御和隐私边界。
3. 演示环境可重置，结果可重复。
4. 已知限制和遗留问题有明确记录。

## 本版本不做

- 为提高展示数量而新增未验证场景。
- 真实银行和生产部署。
- 比赛材料最终提交动作。
