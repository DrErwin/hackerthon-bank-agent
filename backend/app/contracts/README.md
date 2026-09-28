# contracts —— 唯一公共契约

归属：底座（Erwin）。

放什么：能力调用、执行结果、事件、安全上下文、审计事件的公共格式（Pydantic 模型）。语义出处：[契约大纲](../../../docs/contracts/公共契约-2026-09-23.md)及其银行、确认验证、安全审计字段附件。

边界：业务模块**引用**这里，不复制一份；修改走契约变更流程（契约第 8 章）。

## 公共入口

从 `app.contracts` 导入所需类型，例如 `TaskView`、`TransferTaskView`、`OperationResult`、`SecurityDecision`、`AuditEvent`。`common.py` 定义编号、金额、带时区时间及共用枚举；`bank.py`、`tasks.py`、`security.py`、`audit.py`、`api.py` 和 `platform.py` 分别对应冻结文档的接口边界。`OperationId` 限定银行业务写动作使用 UUID v4；`RequestId` 和 `SubmissionId` 仅要求 UUID，不与银行操作编号混用。

`CapabilityCall` 的 `trusted_context` 只能由服务端注入，不能直接使用模型参数或前端请求体填充。验证码专用输入模型用 `SecretStr` 避免普通日志和对象表示泄露原文；实际接口也必须遵守冻结文档的秘密处理规则。

普通转账的银行查询使用 `QueryResult[AccountList]`、`QueryResult[PayeeList]` 和 `QueryResult[PayeeVerification]` 等具名结果；收款资料经 F36 的 `SubmitDetailsRequest` 专用表单提交，回传 `DetailsResponse[TransferTaskView]`，不可转入普通聊天输入。

02 票的测试在本目录，按目录边界从 `backend/` 执行：

```powershell
python -m pytest -q app/contracts/test_contracts.py tests
```
