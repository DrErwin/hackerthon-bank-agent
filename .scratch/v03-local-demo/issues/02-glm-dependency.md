# 02 — GLM 模型连接依赖

Ticket ID: v03-local-demo/02\
Package: [transfer-agent-framework/packages/01-vertical-backend：纵向后端主链路](../../transfer-agent-framework/packages/01-vertical-backend.md)\
Spec: [本机简易前端与 GLM 联调准备规格](../spec.md)\
Type: 开发\
Owner: Erwin\
Directory: `backend/`（仅顶层工程依赖配置，不修改 app 子目录）\
Status: resolved\
Blocked by: None\
Unlocks: [v03-local-demo/04：GLM 本机运行组合](04-glm-runtime.md)

## What to build

让后端按团队工程依赖安装方式获得接入智谱普通 API 的标准模型连接能力，避免本机手工装包才能运行。只补必要依赖，不编写新的模型协议实现或更换既有模型框架。

## Acceptance criteria

- [x] 明确所选连接器支持普通 API、现有 BaseChatModel 与工具调用，选择和现有固定依赖兼容的版本并记录依据。
- [x] 工程依赖声明可在干净环境重复安装，连接器可导入；不只依赖开发机临时安装状态。
- [x] 不替换或静默升级 Deep Agents、LangGraph 等已固定的团队基线。
- [x] 现有后端与模拟银行回归通过；导入检查不以真实密钥为必要条件，不发起付费模型调用。
- [x] 不含 GLM 密钥、不修改 app 子目录的模型、API、安全或业务代码。

## Comments

- 2026-10-02：按项目负责人本次完整审查、修复及合并授权，独立 Standards/Spec AI 审查无阻塞；[PR #40](https://github.com/DrErwin/hackerthon-bank-agent/pull/40) 已 squash 合入，主线提交 `0e2663392f96fe0a6178e1cb267ffabef7355a73`。干净 Python 3.12 环境安装、依赖一致性检查、无真实调用的模型构造/工具绑定通过；后端240项、MockBank14项通过。固定 Deep Agents/LangGraph 版本保持不变；干净安装本次解析 langchain-core 1.6.6，连接器元数据支持 >=1.6.4，历史1.6.5记录仅代表当时环境。票02完成，不代表票04真实GLM或前端闭环完成。真人专业审查未冒称；本记录仅保存本机，未混入代码PR或同步飞书。

- 2026-10-01：本机检查未安装 langchain_openai 或 langchain_community；现有工程依赖没有声明普通 API 的模型连接器。本票是必要工程拆分，未实施；具体兼容版本在实施时核验并固定。
- 2026-10-01 实施记录：`backend/pyproject.toml` 固定 `langchain-openai==1.6.6`；兼容依据是现有 `langchain-core==1.6.5`，1.6.7 要求 core >=1.6.6。独立 Python 3.12 环境安装与导入检查通过，构造 ChatOpenAI/BaseChatModel 并绑定工具时未请求网络或使用真实密钥；全量后端测试 240 passed。Commit `d68ed72`，Standards/Spec AI 复核无发现；真人 PR 审查仍待完成。
- 2026-10-01：PR #40 已创建：https://github.com/DrErwin/hackerthon-bank-agent/pull/40；等待人工 review。
