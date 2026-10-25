# 养老金真实入账与本人账户接入：business/07

Status: approved_scope / implementing — 2026-10-25 中控明确续派；与已完成规划的06分支独立。

Owner: Erwin 授权执行对话；Directory: `backend/app/modules/cross/`。

## Problem Statement / Solution

真实流水用 direction=inflow + nature=transfer 表示入账，现有业务却筛不存在的 transfer_in，
因此无法选择真实养老金。本人储蓄账户A5来自本人账户查询，不在保存联系人中，原去向菜单却只读联系人。
按现有 Transaction、OwnPayee/SavedPayee 及公开查询能力修复，不改银行数据、风险政策或参数配置。

来源：[已批准PRD](../../docs/prd/06-跨场景联动-PRD-2026-09-23.md)、
[夹具核查](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/v05-cross-e2e-01-fixtures/evals/cross/fixture-validation-2026-10-25.md)。

## User Stories

1. 用户按本人付款账户选择真实的当月转入流水，不用余额替代已选入账。
2. 多笔入账列出可区分的真实候选，由用户选择，不把所有流入自动叫养老金。
3. 用户可选其他本人账户（包括零余额的A5储蓄账户），也可继续选已保存的家人收款人。
4. 本人账户以OwnPayee、家人以SavedPayee交给原转账公开入口；两种都保留原确认/验证及银行规则。
5. 查询失败、旧选项、取消或未知仍保守等待，不放宽风险门、不重复转账。

## Implementation Decisions

- 入账只用当前付款账户、本期真实流水的 inflow+transfer 候选；refund/interest/outflow及其他账户不混入。
  选择保存真实 transaction_id 与金额；候选多笔由用户选明确的一笔，不默认汇总全部。
- 金额文本只作选择提示，不构造一条新流水，也不自动改用余额。
- 去向菜单同时使用 transfer.list_accounts 和 transfer.list_payees 的真实结果；本人去向排除当前付款账户，
  展示账户名称和掩码，不要求记编号。收款人查询失败不隐藏已查到的本人账户。
- 方案/步骤保留 target_account_id 或 payee_id，派发时分别构造既有 OwnPayee 或 SavedPayee。
  不伪造A5联系人、不复制转账内部流程；账户最终可执行性由原转账/银行复核。
- 既有采用、留存、D1、未知/暂停/停止保持原业务边界；预算06不在此实施。

## Testing Decisions

优先通过 CrossEntry/Harness 公开入口验证真实契约形状的入账选择及派发输入；
真实装配用原银行本人账户/联系人查询验证A5可选、原风险未知不写钱。
再用隔离组合 #284（账单 typed 输入）与 #292（装配断言）核对真实L01和选定入账，不把它们合入本票分支。

| ID | 场景 | 预期 |
|---|---|---|
| PI01 | 契约合法inflow+transfer500000分 | 资金范围选定该交易；排除退款、利息、转出及他账户 |
| PI02 | 多笔转入、文字仅提金额、重复/旧选项 | 不自动汇总为养老金；用当前候选选定真实编号 |
| PI03 | 本人A5有账户但不在联系人，当前付款A1 | A5可选、OwnPayee(A5)派发；A1不作为自身去向 |
| PI04 | 家人联系人与本人账户并存、联系人查询失败 | SavedPayee保留；可用本人账户不被失败掩盖 |
| PI05 | 入账5000/留存1500/选择本人2500与家人1000 | 原金额与对象正确、逐笔确认；风险事实缺失继续暂停 |
| PI06 | 原养老金取消/未知/失败/余额变化回归 | 不重转、不自动降低留存、不改政策或风险参数夹具 |

实际结果按契约替身/真实公开查询/组合装配/模型HTTP页面E2E分层记录。后两层未执行不填通过。

## Out of Scope / Start condition

不改risk/security、参数夹具、账单/平台源码、前端、evals或共享跟踪。独立业务实现已授权，
真实选定入账的完整装配验证依赖#284/#292合入；未合时可组合验证且PR如实声明，不将替身记成E2E。
设计06只规划，不导入本分支。本票不开模型、不使用共享数据库，不自行合并。
