# 08c：查询任务的数据视图适配

Ticket ID: bank-e2e-remediation/08c
Package: [修复包](../packages/01-demo-remediation.md)
Spec: [规格](../spec.md)
Owner: Codex 按用户授权代行
Directory: `backend/app/api/`
Status: ready-for-agent
Priority: P1
Parent: bank-e2e-remediation/08
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

已有 API 按 transfer 模块把所有结果强制解释为转账回执。新增两条只读查询返回账户/联系人清单，应按服务端保存的 capability_name 选择现有 AccountList/PayeeList 模型；默认转账与订阅行为不变，未知能力不猜类型。不得从客户端指定能力来放宽视图或归属。

验收：两类清单读取和历史刷新正常，原转账仍校验 TransferTaskView，跨用户拒绝。平台业务注册与银行执行验证留在08，页面验收由10/11完成。
