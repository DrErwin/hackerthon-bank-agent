# 对话驱动原型 v2

2026-10-26。用户认可组件基础后，指出原方案像常规银行软件，并同意改为 Agent 对话主导。

- 当前入口 phone.html 使用实际 React 前台的稳定预览；原方案保留在 phone-v1.html 和 index.html。
- 实现与字段边界见 [PR #319](https://github.com/DrErwin/hackerthon-bank-agent/pull/319)；实施票 frontend-design-system/02。
- 对话正文展示回复，卡片跟到最新相关回复；输入常驻；工具抽屉查资料后继续原任务。
- 原型服务依赖本地构建 5189：在实现分支 frontend 中设置 VITE_API_MODE=contract-demo，npm run build，然后 npm run preview -- --host 127.0.0.1 --port 5189。
- 这些回复和资料为固定演示；真实自由语言能力另行联调。

本分支是原型历史快照，不合入 main。当前设计与验证以实现票和 PR 的记录为准。
