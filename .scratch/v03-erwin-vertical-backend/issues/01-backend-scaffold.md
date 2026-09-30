# 01：建立可运行的后端工程骨架

Type: task\
Status: resolved\
Merged PR: #1\
Owner: Erwin\
Directory: `backend/`\
Blocked by: 无\
Unlocks: 02

## 业务目的

让后续所有后端目录使用同一套可安装、可测试、可启动的 Python 工程，不再各自猜依赖和运行方式。

## 交付

- v0.3 所需的最小 Python 项目与依赖配置。
- 统一的开发安装、测试和本地启动命令。
- 基础测试配置和应用包发现规则。
- 仅建立工程入口，不在本票实现 API、业务、安全或银行逻辑。

## 验收

- 新环境按仓库说明可以安装后端依赖。
- 测试命令能够运行，并在没有业务测试时正常给出明确结果。
- 后续 `backend/app/*` 包可以按统一路径导入。
- 依赖只覆盖 v0.3 已确定技术栈，没有加入未来场景专用框架。
- 本票改动不进入任何 `backend/app/<module>/` 目录。

## Handoff

工程安装与测试命令可用后，将 02 改为 `ready`。

## Comments
