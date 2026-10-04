# 纯文档变更跳过GitHub CI

Status: Confirmed
Date: 2026-10-04
Owner: Erwin / 项目共享CI

## Problem Statement

纯文档PR和main推送仍触发完整后端CI，浪费时间和算力。用户已明确要求更改GitHub配置使其实际跳过。

## Solution

在pull_request与main push使用相同paths-ignore；仅当本次全部改动为Markdown、reST及docs中的图示资源时不创建Repository checks运行。任一代码、依赖或执行配置文件仍触发原检查。

## User Stories

1. 文档作者提交README、AGENTS、规格、用例与进度说明，不启动或等待CI。
2. 开发者混合改文档和代码时，原CI完整执行。
3. 配置维护者修改工作流、依赖或部署配置时，CI仍执行。

## Implementation Decisions

仅修改.github/workflows/中的现有Repository checks触发条件；不改job、权限和测试步骤。不添加新服务、action依赖或文件分类脚本。docs图示为mmd/png/jpg/jpeg/svg/pdf；未列入的文件继续检查，不能因为在docs中就忽略可执行代码/配置。

## Testing Decisions

使用YAML解析检查两个入口的过滤一致、main分支和现有jobs不变；检查纯文档、文档加代码、requirements.txt、工作流及docs内脚本/配置的触发结果；配置PR需通过现有CI。只增加瞬时验证，不建立重复的永久测试框架。

## Out of Scope

关闭整个仓库的Actions、修改业务运行与安全规则、修改其他CI步骤。

## Further Notes

依照项目to-spec、to-tickets、implement指南执行；用户明确单次授权完成此小项，无额外范围或拆票审批问题。主工作区有既有未提交修改，使用已清理至main的独立worktree。维护工作不改变v0.3验收状态。


## 交付证据（2026-10-04）

PR #49已合入`fd6c677`；GitHub main工作流逐字节确认已包含两个事件的paths-ignore。独立AI规范/需求复审0阻塞，YAML和14组路径分类通过，配置PR及主线CI通过。本票仅改变CI触发条件，不修改产品规则或业务验收。
