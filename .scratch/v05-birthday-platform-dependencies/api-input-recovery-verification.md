# API11：普通生日输入中断恢复

Owner: Erwin；执行：本对话 AI。代码目录 `backend/app/api/`，依赖 [PR323](https://github.com/DrErwin/hackerthon-bank-agent/pull/323) 的原转换查询与封存故障恢复。

- 原失败：预算输入转换已完成，但任务历史发布抛OSError后，API保存503；同request_id重试仍返回旧503。新回归在原基线真实失败，未改期望或历史证据。
- 改后：只有平台原转换或API原完成视图存在，才允许原摘要一致的请求续做；不存在持久受理事实的请求仍409。API保存真实TaskView后再发布，避免平台CAS版本和最终可见版本差异，也不依赖平台最近8条投影长期保留原HTTP视图。
- 恢复历史/SSE沿原request稳定事件ID；已完成请求不再调用业务；后继卡存在时只回原完成视图，不将旧卡作为当前事件重新广播。异参仍由原HMAC摘要拒绝，原身份、轮次与任务绑定保持。

## 实际运行

受测提交 `07eb319f`，平台代码 `5aae44b6`。从本worktree加载源码，解释器复用既有Python环境，数据库均为pytest新临时库。

- `pytest backend/app/api/test_birthday_input_recovery.py -q`：**7 passed**。
- `pytest backend/app/api -q --junitxml=.scratch/v05-birthday-platform-dependencies/evidence/2026-10-27-api11.xml`：**232 passed / 0 failed / 0 skipped**，461.19秒。
- 覆盖任务发布失败、封存前存储故障、HTTP回执保存中断、同请求异参、后继推进后的旧请求、无受理事实的中断请求拒绝及API存储重开。
- 本票使用真实FastAPI/Harness/安全/银行/存储组合，模型为现有脚本连接器；预算/日期输入阶段不是实际付款完成证据。未新跑真实模型、页面或完整资金E2E；CI、独立审查及真人接受分别记录。

JUnit：[原始XML](evidence/2026-10-27-api11.xml)。最后文档/证据提交不改受测Python实现。
