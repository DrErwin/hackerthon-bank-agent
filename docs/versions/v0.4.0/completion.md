# v0.4.0 完成情况：账单、完整安全与完整前端（联动移至 v0.5）

> 状态：进行中（2026-10-11 正式启动，PM 决定提前于原 10-13；目标 10-20）

## 当前情况

- PRD 与公共契约已经存在。
- 2026-10-04：交付包04的开发前代表性评测准备已验收；[账单 PR #61](https://github.com/DrErwin/hackerthon-bank-agent/pull/61) 21条、[联动 PR #62](https://github.com/DrErwin/hackerthon-bank-agent/pull/62) 23条已合入，均待运行；联动用例随联动移至 v0.5 挂起。
- 2026-10-11：v0.3 收口（含明示例外）同日，版本范围调整为账单+完整安全+完整前端（转账+账单双场景），联动移至 v0.5（提交 `93da4f7`）；**v0.4 正式启动**。交付包齐备：[v04-bills/01 账单业务能力与评测](../../../.scratch/v04-bills/packages/01-bills-backend.md)（周恩宇）、[v04-security/01 检测器与评测完整性](../../../.scratch/v04-security/packages/01-detector-and-coverage.md)（Ringo+代行条款）、[frontend-complete/01 完整前端实现与替换](../../../.scratch/frontend-complete/packages/01-v04-complete-frontend.md)（梁爽/六水）、[v04-bills/02 联合验收与收口](../../../.scratch/v04-bills/packages/02-v04-acceptance.md)（Erwin 牵头）；底座 #84/#85 由 Erwin 自拆（#84 优先，安全线转正复跑依赖它）。
- 业务实现尚未开始；本版本尚无验收证据。

## 启动条件（已核验，2026-10-11）

- [x] v0.3.0 普通转账纵向链路通过联合验收（2026-10-11 收口，含明示例外）。
- [x] v0.3.0 的公共接缝和遗留问题已经记录（[Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87) 总索引）。
- [x] 负责人在正式项目跟踪表确认开始时间（PM 2026-10-11 决定启动）。

## 待完成

- 账单业务与评测（BF01—BF07）、安全检测器与评测完整性（#86/#88）、完整前端双场景与替换（FE-01—FE-06）、底座 #84/#85、联合验收与收口（含飞书 #90）。

## 验证状态

- 代表性用例文档的内容、链接、编号及差异空白检查通过，规范/规格 AI 复审无剩余阻塞。
- 尚无本版本业务实现和真实评测运行的完成验证；完整规模扩充、联合验收及真人专业安全审查仍待完成。
