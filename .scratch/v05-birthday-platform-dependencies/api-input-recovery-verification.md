# API11：普通生日输入中断恢复

Owner: Erwin；执行：本对话 AI。代码目录 `backend/app/api/`，依赖 [PR323](https://github.com/DrErwin/hackerthon-bank-agent/pull/323) 的原转换查询与封存故障恢复。

- 原失败：预算输入转换已完成，但任务历史发布抛OSError后，API保存503；同request_id重试仍返回旧503。新回归在原基线真实失败，未改期望或历史证据。
- 改后：只有平台原转换或API原完成视图存在，才允许原摘要一致的请求续做；不存在持久受理事实的请求仍409。API保存真实TaskView后再发布，避免平台CAS版本和最终可见版本差异，也不依赖平台最近8条投影长期保留原HTTP视图。
- 恢复历史/SSE以用户、轮次、任务和原request组合生成稳定事件ID；不同任务复用同一UUID不互相覆盖。已完成请求不再调用业务；后继卡存在时只回原完成视图，不将旧卡作为当前事件重新广播。异参仍由原HMAC摘要拒绝，原身份、轮次与任务绑定保持。

## 实际运行

受测提交 `07eb319f`，平台代码 `5aae44b6`。从本worktree加载源码，解释器复用既有Python环境，数据库均为pytest新临时库。

- `pytest backend/app/api/test_birthday_input_recovery.py -q`：**7 passed**。
- `pytest backend/app/api -q --junitxml=.scratch/v05-birthday-platform-dependencies/evidence/2026-10-27-api11.xml`：**232 passed / 0 failed / 0 skipped**，461.19秒。
- 覆盖任务发布失败、封存前存储故障、HTTP回执保存中断、同请求异参、后继推进后的旧请求、无受理事实的中断请求拒绝及API存储重开。
- 本票使用真实FastAPI/Harness/安全/银行/存储组合，模型为现有脚本连接器；预算/日期输入阶段不是实际付款完成证据。未新跑真实模型、页面或完整资金E2E；CI、独立审查及真人接受分别记录。

JUnit：[原始XML](evidence/2026-10-27-api11.xml)。最后文档/证据提交不改受测Python实现。

## 独立审查后的补修

两位独立审查者指出：API原视图保存本身失败后，后继输入推进会使原请求被拒绝；不同任务使用相同UUID也会碰撞历史事件身份。新增两项回归在修复前均真实失败（2 failed / 7 deselected），原7项期望不改。

受测提交 `e44f281d7ccc1af633b335b7d22b0466f8cb0057`：专用文件 **9 passed / 0 failed**，19.92秒。保存断点后的旧请求只恢复平台已封存的原结果与原修订号；事件ID按用户/轮次/任务/请求隔离。原232项API结果属于前一实现，不能当作本补修后的完整API回归；最终组合回归另记。

JUnit：[补修XML](evidence/2026-10-27-api11-post-review.xml)，SHA256 `6f0b47ad45d0a5fd8326ddc09d49527797f2b9682c9b5319a6e877e6ce7774d8`。补修待两位原审查者复核，真实模型/页面/资金闭环仍另验。
