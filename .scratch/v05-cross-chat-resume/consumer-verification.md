# v05-cross-chat-resume/02：API 消费验证

基线为已合入提供方 PR #357 的 `bbfb6fd045dd6070f2928d366519d492dfd37849`。
生产修补固定于 `affd96d289f60841396b05e5e6729c960a3de2b1`；最后的新测试断言修正源为
`7d9d817ee4d29251d8cdf31094be2413a261ece9`，API 树
`9bd64f4dbe33fbf7b2df286034a5053775ad5e50`。后续只归档本票 scratch。

API 四行修补明确将无字段 `resume` 建议转换为现有 `choice=resume`，重新核对当前仍
running 且无交互。已有身份、线程、版本、allowed、recovery 和 receipt 门仍在原调用链上；
聊天不借用公开恢复入口的会话恢复权限。用户已批准的有限演示风险范围不变。

## 作者红例与补验

| 固定源 | 结果（XML suite 秒） | 归档 |
|---|---|---|
| badd5457 | 2 setup errors，18.271 | [夹具错误](consumer-fixture-error.xml.gz) |
| c55fa2e1 | 1 failed / 1 passed，18.046 | [消费红例](consumer-red.xml.gz) |
| 04a31f70 | 2 failed，18.638 | [消费及当前状态门红例](consumer-guard-red.xml.gz) |
| affd96d2 | 43 passed / 1 failed，104.181 | [必要组合原结果](consumer-combination-original.xml.gz) |
| 7d9d817e | 同一失败节点 1 passed，18.954 | [断言修正后补验](consumer-unknown-recheck.xml.gz) |

初次夹具错误误取银行路径，尚未抵达产品行为；改为运行时真实路径的只读 SQLite 连接。
真正消费红例中，公开恢复入口能推进原父任务，普通聊天却被误当 query。
扩大红例另覆盖规划后当前任务已改为专用交互时，API 必须再次拒绝普通 resume。

必要组合的唯一失败是新测试误要求未知任务只允许 query。既有公开投影同时提供受控
cancel，其含义为记录取消意图并查询原操作；本票仅修测试预期为 query 存在且 resume
不存在，并保留原操作编号、原提交次数 1、聊天 continue 次数 0 的断言。未改生产取消逻辑。
原 43 个绿节点与该节点补验覆盖 **44 个唯一节点**；新增文件的 8 个节点为原 7 加同 1
补验。没有重写原失败 XML，没有再跑全量，也没有一次 44 全绿的记录。

必要组合从 backend 运行，四文件为 API 新 resume、conversation_dispatch、child_parent_context
及平台提供方 test_chat_resume；补验从仓库根只选 unknown 的原节点。完整命令、逐节点状态、
raw/gzip SHA256 见 [JSON](consumer-verification.json)。XML 原样无损 gzip，解压字节与原件一致。

## 来源与证据边界

原依赖 c8d476ef 上的四个消费提交重放到 bbfb6fd0，range-diff 全为 `=`。
消费 API 树字节相同；提供方合入前后仅其 test_chat_resume guard 测试改变，不能声称整个
backend 树相同。准确证明见 [重放记录](consumer-rebase.json)。

affd96d2 到 7d9d817e 仅本票 test_chat_resume 改动；另外 274 个 backend 条目相同，
manifest SHA256 为 `dd7fb99a81fbec9298452322183811771afacd13a4a1d3ea1c9d3a89a8b2bd88`。
service.py blob 始终为 `bea0cf2b3df63c93e0f61cdfb9724d6a313ab94f`。

真实本地层为 ASGI HTTP、Cross、Harness、安全执行器与独立临时模拟银行。规划结果、规划后
五种当前 API 投影、银行查询超时及 receipt 写入中断使用声明的测试替身。原请求 UUID 重放、
中断后读回、旧版本、别的线程、新会话及真实未知操作均有断言；银行结果仍由模拟银行返回。
没有运行真实模型、原页面或共享银行；这些不等同于专业安全签核、CI、主线或用户验收。

## 独立审查与后续

独立 Spec 在 affd96d2 静态审查为 0 产品必须项；其 8 项 HTTP 原批 7 pass / 1 新断言错
（72.32 秒）。固定 7d9d817e 后仅补同节点 1 pass（18.87 秒），0 剩余必须项。
独立原 XML SHA256 为 `fba8c7648d3e9a8280f252588131077d55f44e11f01d7aae2b8eb42f3de9d2e7`，
补验为 `53e0754812a8c6dc5f2ecf55e46425080a7bf8003a5d74f75d50e147c76ae375`，由审查者留存。
独立结果不加入作者 44 个节点计数。Standards、最终 PR head CI 与原页面复验由根分别核定；
作者不合并、不重启演示服务、不操作运行银行。
