# v0.5.0 需求：联动、系统验收与体验打磨

> 阶段目标：完成跨场景联动（由 v0.4 移至，2026-10-11 项目负责人决定），用完整业务和安全评测证明核心系统可用，并修复影响演示和评分的问题。
> 交付状态见[完成情况](completion.md)；当前任务与开放问题见[项目跟踪](../../01-项目跟踪.md)。

## 背景

三个核心场景完成后，需要统一验证任务完成率、安全合规、恢复能力和适老化体验。

## 范围

- **跨场景联动**（v0.4 移至：先账单后联动；涉及资金的逐笔确认、部分成功与收尾）：业务能力、评测与前端接入。**未开工。**
- **任务评测与安全评测**：跑三场景任务评测与安全评测；生产检测器装配（[#160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)）按实际排期推进；样例扩充（[#215](https://github.com/DrErwin/hackerthon-bank-agent/issues/215)）**PM 2026-10-24 决定只扩充样例、不再做候选模型比较**。
- **跨模块集成测试与缺陷修复**；核对审计证据、恢复、防重复和用户状态表达。
- **管理端审计导出 F35 与 F24 audit 分支**（来源 [Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)，2026-10-13 PM 决定挂 v0.5）：**已交付**——[v05-platform/01](../../../.scratch/v05-platform/issues/01-audit-export.md)（[PR #214](https://github.com/DrErwin/hackerthon-bank-agent/pull/214) `b01ceb9`）；管理前端入口按 PM 决定不做（已知限制），历史轮次导出维持与 F33/F34 一致的当前轮次口径。
- **可信观察接缝与四项体验能力**（[Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)，PM 2026-10-22 决定当日实施）：**已交付**——[v05-observer-seams](../../../.scratch/v05-observer-seams/spec.md) 十票合入：工具返回与用户资料以不可信数据块进模型提示、F37/F38 记忆查看/删除、输出侧敏感信息探针；v0.4 例外 E7 部分解除。未做：前端粘贴框/记忆管理页（另开前端票）、生产检测器装配、真实页面粘贴走查、批次 B/C 全量。
- **关键演示路径与适老化交互打磨**：卡片版式与连续办理已交付（#252/#253/#254）；200% 缩放与完整读屏待做。
- **前端剩余范围**：v0.4 已交付的转账插槽（[PR #142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142) `92ee700`）与账单插槽/主入口替换（#199/#201）不回退；**订阅场景 05 前端插槽已交付**（清单/退订/回执/刷新，#230–#232、#247、#253/#254 真实页面验证）。剩余为已知非阻塞项（如旧会话历史条目逐条 F14/F16 刷新返回 409 `SESSION_RECONFIRMATION_REQUIRED`；F39 视图已直接渲染、页面无缺失）与适老化细节（200%/读屏）。票据与证据入口：[`.scratch/liangshuang-frontend-complete/`](../../../.scratch/liangshuang-frontend-complete/spec.md)、[Issue #89](https://github.com/DrErwin/hackerthon-bank-agent/issues/89)。
- **形成核心能力验收记录**：按实际证据记录，不写"全部通过"；例外与缺口如实登记。

## 验收标准

1. 三个核心场景的主要和关键异常路径通过（联动接入后）。
2. 安全评测能够证明确认、权限、注入防御和隐私边界。
3. 演示环境可重置，结果可重复。
4. 已知限制和遗留问题有明确记录。

## 本版本不做

- 为提高展示数量而新增未验证场景。
- 真实银行和生产部署。
- 比赛材料最终提交动作。
