# 21：逐项填写转账的演示话术衔接
Ticket ID: bank-e2e-remediation/21
Package: [Demo 修复](../packages/01-demo-remediation.md)
Spec: [连续办理体验规格](../experience-spec.md)
Core scenarios: UX02、UX05、UX06
Owner: Erwin（用户授权实施；安全专业审查归 Ringo）
Directory: `backend/app/security/`
Status: in_progress
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

隔离真实页面首次发起“我要转账”，再依次选择500元、A1、妈妈，原任务保留正确，但有限演示话术不认识“我要转账”，安全事实不足而暂停，未提交银行。失败任务327b6284-5f90-45ad-98d5-3aa67bf09f68留作证据。

修复仅支持不带其他叙述的转账发起语句；必须仍与现有服务端演示金额/账户/收款人事实匹配。没有匹配事实、额外未知叙述、异常检测失败继续暂停；任何正向高风险信号仍优先阻断。不得删除原请求或只保留后续字段来掩盖风险。版本递增，注明这仍为有限演示规则，不代表真实检测全面通过。

- [ ] 纯转账发起 + 逐项选择进入确认，不直接执行。
- [ ] 相同开头附带保密/共享屏幕仍阻断，未知附言/无夹具仍暂停。
- [ ] 本地验证、真实页面重放及 Ringo 专业审查状态分别记录。
