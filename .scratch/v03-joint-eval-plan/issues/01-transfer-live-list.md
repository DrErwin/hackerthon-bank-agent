# 01：功能用例真实模型重点运行清单

Ticket ID: v03-joint-eval-plan/01
Package: [transfer-agent-framework/packages/03-v03-evaluation：v0.3 评测与专业审查](../../transfer-agent-framework/packages/03-v03-evaluation.md)
Spec: [功能与安全用例联合执行规格](../spec.md)
Owner: Erwin
Directory: evals/transfer/
Type: 文档
Status: resolved
Blocked by: None
Core scenarios: J01、J03、J04，见规格
Verification: 逐个核对现有样本 ID，核对 CLI 选择及重复运行轮次；原功能全集及报告分母保留。

## What to build

给出无需改现有运行脚本即可选择的真实模型重点清单，明确其余程序分支继续离线运行，当前支持的共享安全话术按三轮保留稳定性采样。

## Acceptance criteria

- 35 个功能样本唯一且存在，给出理由和直接可运行命令。
- 共享“嗯”样本共三轮，总计 37 次功能样本执行。
- 说明不等于 37 次供应商 API 调用、不替代完整联合验收。
- 内容、链接及空白检查通过，不调用真实模型。

## Answer

2026-10-07：交付[真实模型重点运行清单](../../../evals/transfer/live-model-plan.md)。35个样本存在且唯一；“嗯”追加两轮后共37轮。命令使用模拟python验证选择数35/1/1、PowerShell语法及首轮失败保留；链接与差异空白检查通过，未调用真实模型。
