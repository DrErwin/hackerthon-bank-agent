# 生日走查失败的最小模型诊断（2026-10-29）

Status: diagnostic_complete / completion_response_timeout_unresolved

范围：根任务明确委派的只读诊断，执行者 `live_model_diagnostic`。仅自有诊断JSON、本文与忽略的临时探针；未修改生产代码、配置、凭据、模型选择、风险/确认规则、运行银行或浏览器，未重发原用户消息。

## 结论与实际证据

同一份本机配置实际为 `glm-5.3`，端点 `https://open.bigmodel.cn/api/coding/paas/v4/`。客户端与生产 `local_demo.py` 一样：temperature=0、max_retries=0、timeout=60、use_responses_api=false；没有HTTP/HTTPS/ALL/NO_PROXY环境变量。

一次不带业务工具、聊天历史或银行资料的 `model.invoke('只回复 OK。')` 仍在 **60.562秒** 后失败，实际异常链：

```text
langchain_openai.chat_models.base.OpenAITimeoutError
  → openai.APITimeoutError
  → httpx2.ReadTimeout
  → httpcore2.ReadTimeout
  → TimeoutError
```

同期同端点一次带既有凭据的 `GET /models` 在 **578毫秒** 返回HTTP200，11个列表模型包含配置模型。GET成功只证明这个读取端点可响应，不替代chat completion成功，也不证明额度或所有鉴权权限正确。

这证明当前故障**不需要生日话语、长上下文或业务工具schema才能复现**。当前最小聊天补全也在等待响应时超过原60秒时限；不能把它定性为生日规则失败。仍不能从一次超时断言提供商全局故障、排队、模型服务、网络响应路径、SDK问题或额度耗尽；本探针没有取得429、401或额度错误响应。

[脱敏原始JSON](2026-10-29-minimal-probe.json)，SHA256 `4447ca93473744bd8644454dcc74ab758f4b65ca2401e2c5bde28f5743547e2b`。UTC窗口06:48:17.247471—06:49:17.942531，即本地14:48:17—14:49:17。JSON没有保存凭据、供应商响应体或银行资料；配置文件前后原字节相同。

## 循环与边界

- 源码：`ffa42936c172f3114fa0a826f99ea4373f39058a`。独立核原API进程PID110480的命令仍为本checkout的 `serve.py http-live-40cedee160da`；该helper只覆盖data/round/origins，模型配置来自根指定的原 `BANK_LOCAL_CONFIG`。
- 探针：忽略目录 `.mnemon/v05-live-model-diagnostic-20261029/probe.py`。命令使用既有venv、显式本checkout的backend导入路径、原配置路径及原profile；单次执行已完成，脚本存在结果时拒绝重复调用。
- 此诊断没有调用 `build_runtime()`、打开应用/银行库或注册/调用业务工具。不是页面通过证据，也没有修复原生日失败；根保留的两次页面失败记录仍有效。
- 原始页面的通用 `MODEL_UNDERSTANDING_FAILED` 抹平异常类型，因此不能直接由旧JSON反推网络根因。最小探针只为新请求补出明确的read-timeout异常链，不改写两次旧调用的原因。

## 当前假设与可证伪下一步

1. **当前补全响应路径超过原60秒时限**：新最小请求已支持这个现象；原因尚未定位到某一网络/服务环节。
2. **SDK或POST补全路径特定问题**：若后续获准的同模型、同参数直接HTTP补全能及时响应而SDK仍超时，才支持这一归因；本轮未做第二次补全调用。
3. **单模型服务或默认推理耗时/排队**：若后续同一模型可观察到首响应或完整响应时间超过60秒，才支持；本轮未改streaming、thinking或timeout参数，也未比较/更换模型。
4. **仅生日schema/上下文触发**：干净最小调用也失败，说明它不是本次症状的必要条件；不排除同时存在其他输入问题。

最小行动是保留当前失败、暂停继续重复业务输入；同一最小聊天补全恢复后，再回原页面走生日/P01。若持续超时，应再针对同一端点/模型的响应路径做受控诊断；当前证据不支持换模型、放宽安全或用固定回复冒充闭环。未擅自延长生产timeout或创建定时重试。
