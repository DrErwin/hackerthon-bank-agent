# 2026-10-29 模型诊断证据

最终观察见[流式扩展诊断](streaming-diagnosis.md)：14:59当前请求HTTP429/业务码1302，账户速率限制；不是欠费证据。原配置、业务及银行未改，后续live调用已停止。

- [第一阶段原JSON](2026-10-29-minimal-probe.json)：同模型、无工具最小sync invoke在60.562秒后ReadTimeout；GETmodels在578毫秒内HTTP200。SHA256 `4447ca93473744bd8644454dcc74ab758f4b65ca2401e2c5bde28f5743547e2b`。
- [第一阶段报告](diagnosis.md)：只保留14:48阶段的结论，不将后续1302倒填进旧超时。
- [第二阶段原JSON](2026-10-29-stream-probe.json)：同模型单次async stream，672毫秒HTTP429/1302，0chunk/有效事件/可见内容。SHA256 `71606ed28ea3dc66ce57e39a0ff46e0da85061c25de98ac89a57001de75f0b14`。

执行者：根明确委派的 `live_model_diagnostic`。仅本自有诊断目录及忽略的临时探针，未修改生产源码、真实配置、凭据、安全、模型、运行银行或页面；未提交、推送或合并。原根任务页面失败和先前成功各自保留。
