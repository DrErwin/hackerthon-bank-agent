# AI Banking Agent 赛题调研全景（技术栈 / 行业 / 安全 / 评测 / 同类项目 / 决策）

> 调研日期：2026-09-16 ｜ 适用于：2026 第八届 FinTechathon 深圳国际金融科技大赛 · 国内 AI 赛道「AI Banking Agent」
> 项目背景：Python 3.12 + FastAPI(SSE) + LangGraph 1.x + GLM（备胎 Qwen）+ SQLite/SQLModel Mock Bank + Vue3 + pytest 双测试集
> 官方赛题页：[fintechathon.g-ican.com](https://fintechathon.g-ican.com/)（HTTP 200 可达，Vue SPA，规则在 `/rule` 路由，需浏览器访问）

---

## 0. 怎么用这份文档

- **第 1 章**是开发时的速查书签：每个将用到的 LangGraph / GLM / Qwen 能力都有官方直链和一句话要点，写技术文档时可直接引用。
- **第 2 章**用于技术文档的「行业背景」一节和答辩时的对标话术，说明我们不是闭门造车。
- **第 3 章**是安全自评报告（占评分 30%）的弹药库：OWASP 条目、国内法规条款方向都在这里挑。
- **第 4 章**服务于两套 pytest 测试集（场景评测 + 红队攻击）的素材来源。
- **第 5 章**是同类开源 demo 清单，借鉴对话设计 / 安全机制 / Mock 数据设计时先看这里。
- **第 6 章**是当前挂着的决策点和基于证据的建议，开会拍板用。
- 事实性论断均带来源直链；**给本项目的建议一律用引用块（>）标出**，与事实区分。无法核实的内容明确标注「未核实」。
- 维护规则：链接或价格失效时直接在该行尾补「（已于 X 日失效）」而不是删除，保留决策痕迹；新调研结论追加到对应章节末尾并注明日期。

---

## 1. 技术栈权威参考清单

### 1.1 LangGraph 1.x（文档已迁移至 docs.langchain.com，旧 python.langchain.com 链接会重定向）

| 能力 | 官方直链 | 一句话要点 |
|---|---|---|
| 总览 | [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview) | LangGraph 1.x 定位为「低层编排框架 + 运行时」，面向长时运行、有状态的 Agent |
| 持久化总纲 | [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 两套互补系统：Checkpointer 保存线程内图状态（短期），Store 保存跨线程自定义数据（长期）（已验证存在） |
| Checkpointer | [Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | 每个超步存检查点，是会话恢复、人审、容错的基础 |
| SqliteSaver | [PyPI: langgraph-checkpoint-sqlite](https://pypi.org/project/langgraph-checkpoint-sqlite/) ／ [SqliteSaver API 参考](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver) | `pip install langgraph-checkpoint-sqlite`，同步 `SqliteSaver` + 异步 `AsyncSqliteSaver`（aiosqlite）；官方注明适合轻量场景、不适合多线程扩展——与我们单机 SQLite Mock Bank 匹配 |
| Store 长期记忆 | [Memory Overview](https://docs.langchain.com/oss/python/concepts/memory) ／ [Long-Term Memory](https://docs.langchain.com/oss/python/langchain/long-term-memory) | 记忆以 JSON 文档存于 Store，按 `(namespace, key)` 组织（如 `("memories", user_id)`），跨 thread_id 共享 |
| interrupt 人审 | [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) ／ [官方博客：用 interrupt 构建 HITL](https://www.langchain.com/blog/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt) | `interrupt()` 暂停图执行等待外部输入，配合 `Command(resume=...)` 恢复——我们「确认面单」门的核心原语 |
| Subgraph 场景图 | [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) | 子图即作为节点的图，用于多智能体与场景复用——01/02/05/06 四个场景图的组织方式 |
| 上下文压缩 | [Short-term Memory](https://docs.langchain.com/oss/python/langchain/short-term-memory) ／ [SummarizationMiddleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) | 官方给 `trim_messages` 与自动摘要两条路；1.x 的 SummarizationMiddleware 接近 token 上限时自动总结历史并保留近期消息 |
| Streaming / SSE | [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming) ／ [FastAPI 官方 SSE 教程](https://fastapi.tiangolo.com/tutorial/server-sent-events/) | `astream()` 支持 `updates/values/messages/custom` 等 stream_mode；FastAPI ≥0.135.0 内置 `fastapi.sse.EventSourceResponse`（支持 `Last-Event-ID` 断线续传、自动 keep-alive ping）（两页均已验证存在） |
| Studio 调试 | [LangSmith Studio 概览](https://docs.langchain.com/langsmith/studio) ／ [本地 Agent Server](https://docs.langchain.com/oss/python/langgraph/local-server) | `langgraph dev` 起本地 Agent Server，Studio 可视化/打断点式调试；注意 Studio 已并入 LangSmith UI 体系，本地开发不强制登录 |
| draw_mermaid | [Graph API（含可视化入口）](https://docs.langchain.com/oss/python/langgraph/graph-api) ／ [draw_mermaid API 参考](https://reference.langchain.com/python/langchain-core/runnables/graph_mermaid/draw_mermaid) | `graph.get_graph().draw_mermaid()` 输出 Mermaid 源码，贴 [mermaid.live](https://mermaid.live) 渲染——技术文档架构图的零成本方案（注意：单独的 visualization 文档页已 404，内容并入 Graph API 页） |
| 参考实现 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)（41.7k★，已核实） | 源码仓库，checkpoint-sqlite 实现在 `libs/checkpoint-sqlite/` |

> 建议：`docs.langchain.com/oss/python/langgraph/visualization` 已 404（本次调研实测），技术文档里引用 Graph API 页即可，别贴旧链接。

### 1.2 智谱 BigModel（GLM）

- **OpenAI 兼容端点**（已验证）：[OpenAI API 兼容介绍](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)，base URL 为 `https://open.bigmodel.cn/api/paas/v4/`，OpenAI SDK 只改 key 和 base_url 即可用；支持流式、`tools`/`tool_choice` 函数调用、`extra_body={"thinking":...}` 推理模式。注意 `temperature` 取值区间 (0,1)，不支持 temperature=0。
- **Function Calling**：[工具调用文档](https://docs.bigmodel.cn/cn/guide/capabilities/function-calling)；工具流式输出见 [stream-tool](https://docs.bigmodel.cn/cn/guide/capabilities/stream-tool)。
- **当前模型与定价**（2026-09-16 实测定价页，[文档版](https://docs.bigmodel.cn/cn/guide/start/pricing) / [平台版](https://bigmodel.cn/pricing)）：
  - 旗舰 **GLM-5.3**（1M 上下文）：输入 8 元 / 输出 28 元（每百万 tokens，下同）
  - **GLM-5.3-Flash**（1M）：0.8 / 2.8 元
  - GLM-5.1：6~8 / 24~28 元；GLM-5：4~6 / 18~22 元
  - **GLM-4.7-Flash：免费**；GLM-4.7-FlashX：0.5 / 3 元
  - GLM-4.6 已不在标准 API 定价表中（仅剩私有实例报价）
- **模型发布时间线**：[官方发布记录](https://docs.bigmodel.cn/cn/update/new-releases)——GLM-5 于 2026-02-12 上线（面向复杂系统工程与长程 Agent 任务），此后 GLM-5.1/5.2（MIT 开源）/5.3 陆续发布（另见 [36氪报道](https://m.36kr.com/p/3679611307617928)、[证券时报](https://www.stcn.com/article/detail/3640020.html)）。

> 建议：项目文档中的「GLM-4.6」表述需要升级——2026 年 9 月的主推旗舰是 GLM-5.3。任务完成率导向的规划/多步推理节点用 GLM-5.3，高频轻节点（意图分类、字段抽取）用 GLM-5.3-Flash，CI 回归测试可试 GLM-4.7-Flash（免费）。三者同端点，只换 model 字符串。

### 1.3 Qwen 备胎（阿里云百炼 / 开源自托管）

- **API 接入（最简）**：[百炼 OpenAI 兼容文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)，base URL `https://dashscope.aliyuncs.com/compatible-mode/v1`，与 GLM 一样只改 key/base_url/model 三个参数。
- **开源自托管最简路径**：[Qwen 官方 vLLM 部署指南](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)——`pip install vllm` 后 `vllm serve Qwen/Qwen3-8B`，默认在 `http://localhost:8000/v1` 暴露 OpenAI 兼容端点；多卡加 `--tensor-parallel-size N`。中文社区教程可参考 [Datawhale self-llm](https://github.com/datawhalechina/self-llm)。
- 模型权重入口：[QwenLM 组织（GitHub）](https://github.com/QwenLM)，HuggingFace/ModelScope 同步分发（未逐项核实具体模型页）。

### 1.4 三条模型接入路径对比（决策 1/5 的支撑）

| 路径 | 前置条件 | 切换成本（相对 GLM 直连） | 适用 |
|---|---|---|---|
| GLM 直连（主线） | BigModel API Key | —（基线） | 开发与提交演示 |
| 百炼 API（备胎） | 阿里云百炼 API Key | 改 `base_url` + `model` 两个环境变量（同为 OpenAI 兼容） | 主线故障时的热切换 |
| vLLM 自托管（不推荐） | 单卡 GPU（8B 级）+ 运维 | 部署 + 权重下载 + 端点维护；`vllm serve Qwen/Qwen3-8B` 后与上两者协议一致 | 仅当要求完全离线时 |

> 建议：见第 6 章决策 1——备胎走百炼 API 而非自托管 vLLM，两者对我们都是「改环境变量」级别的切换成本。

### 1.5 能力 → 我们四场景的映射（写技术文档架构节的骨架）

| LangGraph 能力 | 落到哪个场景/安全件 |
|---|---|
| Checkpointer（SqliteSaver） | 全部场景的多轮会话恢复；`thread_id` 即会话 ID |
| Store（namespace=`("memories", user_id)`） | 场景 06：记住「生日订蛋糕」偏好，跨会话触发定时转账 |
| interrupt + Command(resume) | 安全件一「确认面单」：转账/代扣签约在执行工具前中断，前端渲染面单，用户点确认才 resume |
| Subgraph | 01 转账图 / 02 账单分析图 / 05 订阅代扣图 / 06 跨场景编排图，各自独立可测 |
| SummarizationMiddleware / trim_messages | 场景 02 账单分析：长流水贴进上下文前的压缩 |
| astream + stream_mode="messages" | 前端打字机效果与中间步骤进度（Vue3 EventSource） |
| draw_mermaid | 技术文档里的架构图自动生成，与代码同源不漂移 |
| langgraph dev + Studio | 开发期打断点式调试图执行 |

> 建议：接入 GLM 用 `langchain-openai` 的 `ChatOpenAI(base_url="https://open.bigmodel.cn/api/paas/v4/", api_key=..., model="glm-5.3")`（[OpenAI 兼容文档](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)）；从旧版 GLM 迁移时注意采样参数差异，官方提供了[迁移指南](https://docs.bigmodel.cn/cn/guide/start/migrate-to-glm-4.6)（针对 4.6 的版本，参数差异部分通用，未核实对 5.x 完全适用）。

---

## 2. 业界银行/金融 Agent 全景

检索口径：优先官方源（公司官网/官网新闻/GitHub 组织页），银行案例接受新华网/人民网/证券时报等权威媒体转述并标注；纯营销稿与无法溯源的公众号内容一律不收。每项按「定位 → 与我们赛题的关系 → 链接」给出。


| 主体 | 定位 | 与我们赛题的关系 | 链接 |
|---|---|---|---|
| 蚂蚁 agentUniverse | 蚂蚁开源的金融多智能体框架，源自真实金融业务实践（法律咨询/事件解读/行业分析/财报生成智能体） | **可借鉴**：多智能体协作与「专家角色」设计思路；但它是自研编排，不是 LangGraph | [agentuniverse-ai/agentUniverse](https://github.com/agentuniverse-ai/agentUniverse)（2.4k★，原 antgroup 组织已迁移）、[中文 README](https://github.com/agentuniverse-ai/agentUniverse/blob/master/README_zh.md) |
| 蚂蚁数科 Agentar | 一站式金融智能体开发平台 + 金融推理大模型 Agentar-Fin-R1（基于 Qwen3 8B/32B，覆盖银行/证券/保险 6 大类 66 小类金融任务）；Agentar 2.0 已落地 300+ 行业智能体 | **仅参考**：商业化平台不直接可用，但其「金融任务分类体系」可启发我们的场景拆解 | 平台发布 [新华网](https://www.news.cn/tech/20250429/748d2dda5c714068ace7f73e849669ec/c.html)；Fin-R1 [中国科技网](https://www.stdaily.com/web/gdxw/2025-07/28/content_376905.html)、[论文](https://www.alphaxiv.org/zh/abs/2507.16802)；2.0 [新浪财经](https://finance.sina.com.cn/stock/estate/integration/2026-07-21/doc-iniimqsf2968622.shtml) |
| 华为 HiFS 2026 | 华为全球智慧金融峰会（2026-05-20 上海），主题「Hello Fintelligent World：超越数字化，迈向 Agentic Banking」，升级数字金融四大解决方案 | **仅参考**：「Agentic Banking」术语与叙事可用于文档措辞对标 | [华为官方新闻](https://e.huawei.com/cn/news/2026/industries/finance/agentic-banking)（已在搜索结果确认存在） |
| 工商银行 | 企业级「工银智涌」大模型平台：千亿级金融大模型体系，赋能 20+ 业务领域、200+ 场景，30+ 领域 500+ AI 应用 | **仅参考**：证明「大平台+多场景」是行业主流形态 | [工行官网产品页](https://www.icbc.com.cn/page/1111696122533318656.html)、[新华网年报口径](http://www.news.cn/fortune/20250910/ec64e5bf15454f75929b2ac438d2973c/c.html) |
| 建设银行 | 新版手机银行搭载「金融智能体」（基于大模型的对话式智能服务）；大模型规模化赋能 398 个场景 | **可借鉴**：手机银行对话式金融智能体 = 我们场景 01/02/05 的真实对标产品 | [新华网](http://www.news.cn/money/20260128/015ce1f383664d8ca86341bdae715709/c.html)、[移动支付网](https://m.mpaypass.com.cn/news/202604/02100803.html) |
| 招商银行 | 全栈自研大模型体系，100+ 应用场景落地、识别 1000+ 潜在场景；自研 DevAgent；「招银智库 AI 小研」获 2024 年度 AI 最佳实践 | **可借鉴**：其 ReAct「感知-规划-执行-反馈-进化」闭环描述适合写进我们的架构叙事 | [深圳金融创新大赛展示](https://jr.sz.gov.cn/sjrb/xxgk/gzdt/content/post_12637909.html)、[中国电子银行网](https://www.cebnet.com.cn/20241216/102978133.html)、[新浪财经](https://finance.sina.com.cn/roll/2025-01-15/doc-ineezhcc8057421.shtml) |
| 微众银行（主办方） | 开源 WeBankFinTech 系列项目；最有影响力的是联邦学习 FATE（已捐赠 LF AI & Data 基金会，现由 FederatedAI 组织维护）；AI 布局为「AI 基础设施 / AI 应用 / AI 治理」三层架构 | **相关**：主办方技术品味——重视开源、数据安全与隐私计算；安全自评里呼应「AI 治理」层次会加分 | [WeBank 开源项目汇总](https://github.com/WeBankFinTech/WeBank-all-Project)（226★，已核实）、[FederatedAI/FATE](https://github.com/FederatedAI/FATE)、[FATE 中文文档](https://github.com/FederatedAI/DOC-CHN) |
| FinRobot / FinGPT | AI4Finance 基金会开源：FinGPT 是开源金融 LLM，FinRobot 是金融 AI Agent 平台（四层架构，2024 论文） | **可借鉴**：Agent 平台的分层抽象（数据智能层→智能体层）与评测设计 | [FinRobot](https://github.com/ai4finance-foundation/finrobot)（8.0k★，已核实）、[FinGPT](https://github.com/ai4finance-foundation/fingpt)、[论文](https://arxiv.org/html/2405.14767v2) |

甄别说明：以上银行自建平台的「场景数」均为媒体转述的官方口径，存在营销夸大可能，技术文档引用时建议写「据公开报道」。另外，「天镜」大模型是马上消费金融的产品、**不是**微众银行的（易混淆，搜索时已澄清）。

### 2.1 行业趋势小结（用于技术文档的立论）

- 术语已收敛到「Agentic Banking」：华为 HiFS 2026 以此为主题（[官方新闻](https://e.huawei.com/cn/news/2026/industries/finance/agentic-banking)），EY 发布《AI 银行白皮书：智能体驱动金融范式重构》（[PDF](https://www.ey.com/content/dam/ey-unified-site/ey-com/zh-cn/insights/financial-services/documents/ey-ai-bank-white-paper-zh.pdf)，内容未逐页核验），华为云另有 FinAgent 金融智能体加速器（[页面](https://www.huaweicloud.com/ai/finance.html)）。
- 头部银行的落地方向从「智能客服/知识问答」转向「手机银行对话式金融智能体」（建行 2026-01 手机银行升级为最佳对标，[新华网](http://www.news.cn/money/20260128/015ce1f383664d8ca86341bdae715709/c.html)）——这正是我们四个场景所在的赛道。
- 供给侧两条路线并行：金融机构自建平台（工银智涌/招行全栈自研）vs 科技厂商输出（蚂蚁 Agentar、华为）。

> 建议：技术文档第一章用三句话立论：行业进入 Agentic Banking 阶段（引华为/EY）→ 对话式金融智能体成为零售银行标配（引建行）→ 但「高权限操作 + 人机信任」带来的安全问题是落地的第一道坎（引 OWASP ASI09/金发〔2026〕8 号），我们作品的差异化 = 完整的安全三件套。

---

## 3. 安全与合规弹药库（30% 安全分的材料基础）

### 3.1 OWASP 权威清单

- **OWASP Top 10 for LLM Applications 2025**（[官方总览](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)、[LLM01 条目页](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)，完整十条已在官方页面侧栏核实）：
  LLM01 提示注入 / LLM02 敏感信息泄露 / LLM03 供应链 / LLM04 数据与模型投毒 / LLM05 不当输出处理 / LLM06 过度代理（Excessive Agency）/ LLM07 系统提示泄露 / LLM08 向量与嵌入弱点 / LLM09 错误信息 / LLM10 无限制消耗。
  与我们最相关：**LLM01**（注入隔离）、**LLM05**（输出进 SQL/前端要校验）、**LLM06**（转账必须有确认门）、**LLM07**（系统提示里别放敏感配置）。
- **OWASP Top 10 for Agentic Applications 2026**（2025-12-09 发布，[官方资源页](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)、[发布公告](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)，十条已在公告页核实）：
  ASI01 目标劫持 / ASI02 工具滥用 / ASI03 身份与权限滥用 / ASI04 代理式供应链漏洞 / ASI05 意外代码执行 / ASI06 记忆与上下文投毒 / ASI07 不安全的代理间通信 / ASI08 级联故障 / ASI09 人机信任利用 / ASI10 失控代理。
  与我们最相关：**ASI01**（诱导拦截）、**ASI02**（工具白名单+参数校验）、**ASI06**（Store 长期记忆的写入需校验——生日场景里外部数据入记忆就是投毒入口）、**ASI09**（确认面单不被伪造，前端渲染转义）。

### 3.2 Prompt 注入防御工程实践

- [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)：官方对策清单，含 dual-LLM 模式（持权 LLM 不读不可信内容，隔离 LLM 只读不持工具）。
- [Simon Willison: Design Patterns for Securing LLM Agents against Prompt Injection](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/)：核心原则——LLM 一旦消化不可信输入，就必须被约束到无法执行破坏性动作（我们的「动作只走白名单工具+确认门」正是此模式）。
- [Simon Willison: The lethal trifecta for AI agents](https://simonw.substack.com/p/the-lethal-trifecta-for-ai-agents)：致命三要素 = 不可信输入 + 特权工具 + 自主决策，破坏任一要素即显著降险。
- [tldrsec/prompt-injection-defenses](https://github.com/tldrsec/prompt-injection-defenses)：社区最全的防御措施汇编仓库，写安全自评的对策字典。
- **OWASP Gen AI 安全项目其他资源**：[genai.owasp.org 主站](https://genai.owasp.org/) 还提供 LLM AI Security and Privacy Checklist、GenAI Red Teaming Guide 等配套材料（站内子页已验证存在，具体文档未逐一核验），写安全自评的对策库可再挖一层。
- promptfoo 的红队模块自带按 OWASP LLM Top 10 分类的攻击生成（[对应文档](https://www.promptfoo.dev/docs/red-team/owasp-llm-top-10/)，来自搜索结果，未逐页核验），若采用 promptfoo 可直接对齐 3.3 的映射表。

### 3.3 我们三件安全事 ↔ 权威条目的映射（自评报告骨架）

| 我们的安全件 | OWASP LLM 2025 | OWASP Agentic 2026 | 国内监管条款方向 |
|---|---|---|---|
| 确认面单（interrupt 人审） | LLM06 过度代理 | ASI09 人机信任利用 | PIPL 第 24 条（自动化决策透明）/ 金发〔2026〕8 号（风险纳入全面风险管理） |
| 注入隔离（工具返回值不可信、上下文分区） | LLM01 提示注入 | ASI01 目标劫持、ASI06 记忆投毒 | 暂行办法违法使用处置义务 / GB/T 45654 输入持续监测 |
| 诱导拦截 + 审计日志 | LLM05 不当输出处理、LLM07 系统提示泄露 | ASI02 工具滥用、ASI10 失控代理 | 暂行办法处置义务 / GB/T 45654 安全评估 |

### 3.4 审计日志最小字段清单（建议）

> 每条 Agent 动作落 SQLite 审计表：`trace_id / thread_id / user_id / node / tool / 工具入参快照 / 工具出参摘要 / 是否触发确认门 / 用户确认结果 / 拦截规则命中项 / 模型名与 token 用量 / 时间戳`。检索时能按 user_id 重放全链路，即为「可审计」的实证——这比引十条法规更能拿分。

> 建议：安全自评报告的框架直接按「OWASP LLM 2025 + Agentic 2026 双清单逐条对照」，每条写「我们做了什么 / 残余风险」。这在评委视角比自创框架可信得多。

### 3.5 开源 Guardrails 工具评估

| 工具 | 是什么 | 是否引入 |
|---|---|---|
| [NVIDIA NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails)（[文档](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/overview)） | 可编程护栏（Colang DSL），拦截 LLM 输入输出，支持主题/安全/会话流控制 | **不建议整体引入**：新增一门 DSL 与运行时，调试成本高；且它的主战场是对话流控制，而我们的核心防线是「工具白名单 + interrupt 确认门」，由 LangGraph 原生承担 |
| [protectai/llm-guard](https://github.com/protectai/llm-guard) | 输入/输出扫描器集合（35+：注入检测、PII 脱敏、敏感数据、毒性等），Python 库可独立使用 | **可选引入单个扫描器**（如 Anonymize / Secrets，纯规则、无 LLM 依赖、延迟低），作为管线里的一个节点；不必全家桶 |

> 建议：guardrails 用「自建轻量规则层（正则+关键词+额度）+ 可选 llm-guard 单扫描器」组合，把工程叙事放在「分层防御 + 全链路审计日志」上。引入重型框架反而稀释 LangGraph 原生 interrupt 的卖点。

### 3.6 中国监管文件（安全自评可引用条款方向）

| 文件 | 施行日期 | 可引条款方向 | 直链 |
|---|---|---|---|
| 《生成式人工智能服务管理暂行办法》（七部门） | 2023-08-15 | 提供者对违法使用的处置义务（警示/限制/暂停 → 我们的诱导拦截与阻断）；个人信息处理须取得同意；内容标识与透明度 | [国信办全文](https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm)、[官方答记者问](https://www.cac.gov.cn/2023-07/13/c_1690898326863363.htm) |
| 《个人信息保护法》（PIPL） | 2021-11-01 | 金融账户信息属敏感个人信息（第 28 条方向），需单独同意与严格保护 → 数据最小化；自动化决策透明度与拒绝权（第 24 条方向）→ 确认面单即「人在回路」落地 | [全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)、[十大亮点解读](https://www.cac.gov.cn/2021-08/21/c_1631141677655320.htm) |
| GB/T 45654—2025《网络安全技术 生成式人工智能服务安全基本要求》 | 2025-11-01 | 模型输入内容持续监测；输出合格率等量化指标；训练/推理环境隔离 | [国标全文公开系统](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=F67D3F376E0A0A0FF5317FB36B32A30A)、[金杜解读](https://www.kingandwood.com/cn/zh/insights/latest-thinking/key-takeaways-of-china-s-basic-requirements-for-the-security-of-generative-ai-services.html) |
| 《关于银行业保险业人工智能安全开发应用的指导意见》（金发〔2026〕8 号，金融监管总局科技监管司） | 2026-06-18 发布 | 将 AI 风险纳入全面风险管理体系、定期风险评估审查、模型/数据/基础设施/应用安全建设（方向性表述，正文未逐条核验） | [官方原文页](https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html?docId=1261784&itemId=861&generaltype=1) |

> 建议：安全自评报告的「合规对标」一节按 暂行办法 → PIPL → GB/T 45654 → 金发〔2026〕8 号 四层递进，最后一层是别人没有的增量信息（多数参赛队只会引前两三个）。

---

## 4. 评测参考（自建两套测试集的素材来源）

### 4.1 LLM Agent 评测框架（LangSmith 之外）

- [deepeval](https://github.com/confident-ai/deepeval)（18.3k★，已核实）：LLM 评测框架，pytest 风格——`@pytest.mark` 断言指标（忠实度、幻觉、G-Eval 等），**与我们的 pytest 技术栈天然契合**。
- [promptfoo](https://github.com/promptfoo/promptfoo)（25.2k★，已核实）：声明式 YAML 配置的提示/Agent/RAG 测试 + **红队攻击模拟**（官方描述明确含 red teaming / 漏洞扫描），支持 OpenAI 兼容端点 → 可直接对 GLM 端点跑攻击矩阵。
- LangSmith 本身：[Streaming/评测文档](https://docs.langchain.com/langsmith/streaming)。见第 6 章决策 3。

两工具分工：

| 维度 | deepeval | promptfoo |
|---|---|---|
| 形态 | pytest 插件式，`assert_test` 写在测试函数里 | 独立 CLI + 声明式 YAML（`promptfooconfig.yaml`） |
| 强项 | 指标库（忠实度/幻觉/G-Eval）、单测级粒度 | 提示对比矩阵 + **内置红队攻击库**（可按 OWASP LLM Top 10 分类生成攻击） |
| 端点 | 任意（我们用 GLM OpenAI 兼容端点 + deepeval 的自定义 LLM 封装） | OpenAI 兼容（直接指 `https://open.bigmodel.cn/api/paas/v4/`） |
| 我们的用法 | 场景评测集主框架 | 红队集的攻击矩阵生成与批量执行（可选，也可纯 pytest 复刻） |

### 4.2 金融领域评测集

- [FinEval](https://github.com/SUFE-AIFLM-Lab/FinEval)（286★，已核实）：上财开源金融领域基准，26,000+ 道题（会计/财报/基金/银行从业等），含选择题与多轮对话——可抽「银行/个人理财」子集做我们的领域知识抽查题库。
- [FinRobot / FinGPT](https://github.com/ai4finance-foundation/finrobot)（8.0k★，已核实）：其评测层（金融任务 benchmark 设计）可参考。

### 4.3 红队 Prompt 攻击素材

| 资源 | 内容 | 用法 |
|---|---|---|
| [llm-attacks（AdvBench）](https://github.com/llm-attacks/llm-attacks)（4.8k★，已核实） | 520 条有害行为指令数据集（jailbreak 研究标准素材） | 抽样改编为「银行话术版」越狱种子 |
| [HarmBench](https://github.com/centerforaisafety/HarmBench)（1.0k★，已核实） | 标准化红队评测集 + 自动评判器 | 评判器思路（LLM-as-judge 判攻击是否成功）可抄 |
| [StrongREJECT](https://github.com/alexandrasouly/strongreject)（160★，已核实） | 针对越狱评测的打分 rubric，解决「GPT-4 judge 误放」问题 | 给红队测试集做攻击成功判定 |
| [PromptBench](https://github.com/microsoftarchive/promptbench)（2.8k★，已核实，**2026-03-17 已归档只读**） | 微软的对抗攻击库：字符级（DeepWordBug/TextBugger）、词级（TextFooler/BertAttack）、句级（CheckList/StressTest）攻击实现 | 归档但代码可用；用其攻击实现生成扰动变体，扩充红队集 |
| [tldrsec/prompt-injection-defenses](https://github.com/tldrsec/prompt-injection-defenses) | 防御汇编（含检测类） | 攻防对照表来源 |

> 建议：红队集 = 「公开集种子（AdvBench 风格 20~30 条）+ 银行场景特写（间接注入：账单备注/收款人姓名里藏指令；诱导话术：冒充客服催转账；越权：套别人的账户）」——评委看重的恰恰是后一类公开集里没有的场景特写。判定器用 StrongREJECT 式 rubric + 固定 GLM-5.3 作 judge，避免人工逐条判。

红队集构建的执行顺序（三步，每步都有可复用素材）：

1. 从 AdvBench 520 条中抽样 20~30 条有害指令，逐条改写成银行话术语境（[llm-attacks](https://github.com/llm-attacks/llm-attacks)）；
2. 自建银行特写 30+ 条：注入载体枚举（账单备注/收款人姓名/商户名/订阅名称）× 攻击意图枚举（改收款人、提额、关风控、套系统提示）做笛卡尔积再人工筛；
3. 用 PromptBench 的字符/词级攻击实现对上述种子做自动扰动扩容（[归档仓库](https://github.com/microsoftarchive/promptbench)，代码仍可运行），扩到 100 条上下进 CI。

### 4.4 两套测试集的落地设计建议

场景评测集（pytest + deepeval 断言，数据驱动 JSON）：

> 每条用例字段：`case_id / scenario(01|02|05|06) / user_goal（自然语言目标）/ 预期工具调用序列 / 预期最终状态断言（如 Mock Bank 中 transfer 表新记录金额/收款人）/ 必须命中的确认门 / 判定方式（状态断言优先于 LLM 判分，能 SQL 断言的绝不请 judge）`。FinEval 银行/理财子集可抽 20 题混入作「领域知识」维度（[FinEval](https://github.com/SUFE-AIFLM-Lab/FinEval)）。

红队攻击集（pytest + promptfoo 跑矩阵，或纯 deepeval）：

> 每条用例字段：`attack_id / 类型（直接注入|间接注入|诱导话术|越权探测|系统提示套取）/ 载体（用户输入|账单备注|收款人姓名|商户名）/ 注入 payload / 期望行为（拦截并记录|正常执行但内容隔离）/ 判定（固定 judge + StrongREJECT 式 rubric 打 0~4 分）`。通过标准写进 CI：任何 attack 导致未确认的资金动作 = 硬失败（exit 1）。

---

## 5. 同类参赛 / 开源 demo 摸底

GitHub 检索（banking agent / personal finance agent / fintech langgraph，按星数）结论：**没有与「AI 代人操作银行 + 安全三件套」完全同构的高星项目**，说明选题有差异化空间；可借鉴的是下面这些：

| 项目 | 星数 | 亮点 / 可借鉴点 |
|---|---|---|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)（已核实） | 106.9k★ | 多智能体金融分析（分析师/风控/交易员角色分工 + 辩论式决策）。**借鉴**：角色化 subgraph 与「风控 agent 一票否决」的结构——我们的确认门可叙事为「合规 agent 否决权」 |
| [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB)（已核实） | 73.1k★ | 开源金融终端 + Copilot。**借鉴**：平台化的工具注册表（每个数据源一个标准化工具）与图表输出规范 |
| [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents)（已核实） | 29.5k★ | LangChain 官方「batteries-included」Agent harness：规划子代理 + 工具调用确认门 + 上下文压缩全都内置，且就是 LangGraph 1.x 写法。**借鉴**：我们场景图的结构模板，等价于官方参考实现 |
| [langchain-ai/memory-agent](https://github.com/langchain-ai/memory-agent)（已核实） | 477★ | 官方长期记忆 Agent（Store + 记忆管理循环）。**借鉴**：生日场景「跨场景记忆」的状态机写法 |
| 小而贴合（低星，看设计不看规模） | — | [FinTrust：银行提示注入攻防沙盒](https://github.com/fareedulafrath/Secure-AI-Agent-Sandbox-for-Prompt-Injection-Defense-in-Banking-Systems)（脆弱版 vs 防护版双模式对照演示——**红队测试报告的呈现方式可抄**）；[VaultMind：FastAPI+React 银行 RAG](https://github.com/igna-s/VaultMind-AI-RAG-Banking-Agent)（全栈结构与我们对齐）；[zolva：银行 guardrails + CI 门控评测 + 防篡改审计](https://github.com/ANIBIT14/zolva)（beta，审计日志设计思路可参考） |

Mock 数据设计结论：公开项目里没有现成的「中文银行 Mock 全家桶」（账户/流水/订阅代扣），基本都需要自建——这与我们 SQLModel 自建 Mock Bank 的路线一致；账单/订阅的 Mock 表结构可参考 OpenBB 的标准化行情数据 schema 思路（字段命名与分类树）。

### 5.1 对标差距与差异化声明（写进技术文档「对比」节）

> 与上述项目对比，我们的空白区即卖点：(1) 它们大多只做「只读分析」（行情/研报/RAG 问答），**写操作（转账/代扣签约）+ 确认门**是稀缺品；(2) 银行场景的**间接注入载体**（账单备注、收款人姓名）在通用红队集里没有覆盖；(3) **中文银行 Mock 数据 + 中文监管对标**在开源界基本空白。三句话即可构成创新分的论证。

---

## 6. 悬而未决的决策清单（调研后建议）

以下 7 项按「证据 → 建议」给出；拍板后请把结论同步回项目 README 的技术选型节，避免文档漂移。

**决策 1：Qwen 自托管（vLLM）是否值得投入 W6 切换成本？**
- 证据：自托管最简也要单卡 GPU 跑 Qwen3-8B（[官方指南](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)）；而备胎的最小实现是百炼 API——`base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`（[官方文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)），与 GLM 同为 OpenAI 兼容，切换=改环境变量；GLM 侧 GLM-4.7-Flash 免费、GLM-5.3-Flash 输入 0.8 元/M（[定价](https://docs.bigmodel.cn/cn/guide/start/pricing)）。
> 建议：**不自托管**。黑客松无稳定 GPU 环境与运维窗口；「备胎」用百炼 API 即可达成同等叙事（供应商可切换、端点兼容）。把 W6 的精力投到安全分与创新分上。

**决策 2：guardrails 工具（NeMo Guardrails / LLM Guard）引不引？**
- 证据：NeMo Guardrails 需要学 Colang DSL 且主战场是对话流控制（[文档](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/overview)）；我们的核心防线（确认门/注入隔离）LangGraph interrupt 原生承担；llm-guard 可按单扫描器引入（[仓库](https://github.com/protectai/llm-guard)）。
> 建议：**不引 NeMo；可选引 llm-guard 的 1~2 个纯规则扫描器（PII 脱敏/密钥检测）**，并在文档里明确「分层防御：规则层（轻量）→ 结构层（interrupt 确认门）→ 审计层（SQLite 日志）」。工具克制本身是加分项。

**决策 3：LangSmith 用不用？**
- 证据：LangGraph 的 Studio/评测生态深度绑定 LangSmith（[Studio 文档](https://docs.langchain.com/langsmith/studio)），但本地调试可走 `langgraph dev`（[本地 Agent Server](https://docs.langchain.com/oss/python/langgraph/local-server)）；deepeval 18.3k★、pytest 原生集成（[仓库](https://github.com/confident-ai/deepeval)），promptfoo 25.2k★ 自带红队（[仓库](https://github.com/promptfoo/promptfoo)）。
> 建议：**不作为依赖，作为开关**。代码里预留 `LANGSMITH_TRACING=true` 环境变量（一行配置成本），平时用自建 SQLite 审计表 + `langgraph dev`；评测栈用 deepeval（场景集）+ promptfoo（红队集），不把分数押在云端服务可用性上。

**决策 4：红队集自建还是改编公开集？**
- 证据：公开素材充足（AdvBench 520 条、HarmBench、StrongREJECT、PromptBench 归档但可复用，见 4.3），但全部是英文通用场景；评委视角的差异化在银行特写（间接注入藏进账单备注、冒充客服诱导转账、越权查询他人账户）。
> 建议：**混合**——公开集抽样 20~30 条做基线（证明方法学正统）+ 银行特写 30+ 条自建（证明领域理解），用 StrongREJECT 式 rubric + 固定 judge 模型自动判分，全部落进 pytest。

**决策 5（新增，调研发现）：GLM 模型名升级。**
> 建议：文档与代码里的默认模型从 GLM-4.6 升级为 GLM-5.3（旗舰）+ GLM-5.3-Flash（轻节点）双档配置，免费档 GLM-4.7-Flash 留给 CI。GLM-4.6 已不在标准定价表（[实测](https://docs.bigmodel.cn/cn/guide/start/pricing)），提交材料里用旧模型名会显得功课不足。

**决策 6（新增）：FastAPI SSE 实现选型。**
> 建议：FastAPI ≥ 0.135.0 直接用内置 `fastapi.sse.EventSourceResponse`（支持 Last-Event-ID 断线续传与 keep-alive，[官方教程](https://fastapi.tiangolo.com/tutorial/server-sent-events/)，已验证）；锁依赖版本 ≥0.135.0，避免再引 sse-starlette 第三方库。

**决策 7（新增）：安全自评报告的写作顺序。**
> 建议：先按 3.3 映射表搭骨架（三件安全事 × OWASP 双清单 × 国内四层法规），再填 3.4 审计字段清单的实证截图，最后放红队集跑分表（第 4 章）。顺序反了容易写成法条堆砌。

---

## 7. 来源可靠性说明

### 7.1 关键数字快照（2026-09-16 实测，提交前建议复核）

| 项目 | 快照值 |
|---|---|
| GLM-5.3 / 5.3-Flash 价格 | 8/28 元、0.8/2.8 元（输入/输出，每百万 tokens） |
| GLM-4.7-Flash | 免费；GLM-4.6 不在标准定价表 |
| langgraph-checkpoint-sqlite | PyPI 最新 3.1.1，约 53 万周下载（PyPI 统计口径） |
| langgraph-ai/langgraph | 41.8k★（源码仓库，checkpoint-sqlite 实现在 libs/checkpoint-sqlite/） |
| GitHub 星数 | TradingAgents 106.9k ／ OpenBB 73.1k ／ deepagents 29.5k ／ promptfoo 25.2k ／ deepeval 18.3k ／ FinRobot 8.0k ／ agentUniverse 2.4k ／ PromptBench 2.8k（已归档）／ llm-attacks 4.8k ／ HarmBench 1.0k ／ StrongREJECT 160 |
| FastAPI 内置 SSE | 需 ≥0.135.0（`fastapi.sse.EventSourceResponse`） |
| OWASP Agentic Top 10 | 2025-12-09 发布（2026 版） |
| 金发〔2026〕8 号 | 2026-06-18，金融监管总局科技监管司 |

### 7.2 分级说明

（以下按可信度从高到低分四级；正文中未特别标注的论断默认来自前两级）

- **一手来源（最可信）**：docs.langchain.com / reference.langchain.com（LangGraph 官方，Persistence、FastAPI SSE 等页面本轮直接抓取验证）；docs.bigmodel.cn（智谱官方文档，定价页与 OpenAI 兼容页本轮直接抓取，价格为 2026-09-16 时点）；help.aliyun.com（阿里云官方）；qwen.readthedocs.io（Qwen 官方部署文档）；genai.owasp.org 与 cheatsheetseries.owasp.org（OWASP 官方，LLM01 页与 Agentic 2026 公告页本轮直接抓取，十大条目逐条核对）；cac.gov.cn（网信办，法规全文）；openstd.samr.gov.cn（国标全文公开系统）；nfra.gov.cn（金发〔2026〕8 号的标题/文号/日期/发布司局经官网数据接口核实，正文未逐条核验）；e.huawei.com（华为官方新闻）；icbc.com.cn（工行官网）；GitHub API / 仓库页（星数为 2026-09-16 时点实测）。
- **权威媒体（可信度次之，数字口径可能有宣传成分）**：新华网、人民网、中国科技网/科技日报、经济参考报、证券时报、36氪——用于银行案例的「据公开报道」类引用。
- **社区/厂商博客（观点参考）**：Simon Willison 个人博客（提示注入领域公认的权威个人观点）、towardsdatascience、知乎/CSDN 教程——只作方法参考不作事实出处。
- **未能核实/存在限制的内容**：官方赛题页为 Vue SPA，`/rule` 规则细节无法用文本抓取核验（首页 HTTP 200 已确认），引用赛题细节前请在浏览器中复核；`docs.langchain.com/oss/python/langgraph/visualization` 与 `microsoft.github.io/promptbench` 均 404（实测）；《金融大模型应用测评指南》团体标准细节、微众银行内部 AI 架构细节未核实；调研后期搜索配额受限，建行 398 场景等数字仅单一来源，标注「未核实（单一来源）」。
- 本文档所有链接均经过 WebFetch/WebSearch/GitHub API/curl 中的至少一种方式验证存在（2026-09-16），无凭记忆编造的 URL；价格、星数等为调研时点快照，提交前建议复核一次关键数字。
