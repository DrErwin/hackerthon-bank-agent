# API22 验证

受测源码 `3e9ec5f2ab9b83800a73c1bbc4764c3083f3dee2`，API树 `a1a38205312105db7fdc44f721e6488ec188e1b5`；仅API及自有票据证据。测试均新隔离库、明确脚本模型与服务端测试dispatch，不是完整P01或页面。

- 原真实链 **1 failed /6.82s**：子dispatch能确认，HTTP批准后因缺父风险来源变needs_attention，银行未写。[原红XML压缩](evidence/2026-10-27-api22-before.xml.gz)，解压SHA256 `bc8390b2dd3e4b2d85942a913b790627eb0c0626a8d36e8094f6cceefca4c515`。
- 修后确认/验证码与银行成功均已到达，但测试误用终态F15查询得到既有ACTION_UNAVAILABLE，**1 failed /7.55s**。此为测试入口错误，不修改动作策略；[中间XML压缩](evidence/2026-10-27-api22-after.xml.gz)，解压SHA256 `3b335fe68ebb234215430d96cbaff311b72ee8043068675ecfb73bc50a5049d7`。改为正常终态GET后同链 **1 passed /7.77s**，[绿色XML](evidence/2026-10-27-api22-green.xml)，SHA256 `f3fd224e158312a08f6b4be544e61e82255356593d3e2415b2b72fa5c5e2d70b`。
- 加上同链的foreign用户/轮次/会话在parent lookup前拒绝，以及既有转账确认验证、cookie/origin/ownership、跨会话已完成/processing/timeout原号恢复、历史归属和会话重入，最终 **8 passed /0 failed/error/skipped，41.84s**。[受影响XML](evidence/2026-10-27-api22-affected.xml)，SHA256 `f4dcf8f32822b5bf9dee8519e3db04e772785535b4c7ce96a90e2bf1c310e170`。单例包含其中，不重复加总。

新链通过HTTP确认与验证码后仅原操作一笔银行效果，GET保留同操作，根任务parent=None，非法身份/会话在原API门被拒绝，未查询父来源；19继续严格核持久关系、step/plan与参数/op/rev。没有放宽未知、重试、确认或验证规则。

Spec独立0必须项，Standards继续核；21须在本票合后按原完整断言复验两笔P01，root后续真实模型另开新批。无真实模型调用、无共享库或私密配置操作。
