# v0.3 本机 GLM 运行组合

## 一键启动（推荐）

首次配置后，用仓库根目录的一个命令同时拉起后端与前端：

```powershell
pwsh tools/start_local_dev.ps1            # 后端(8000) + 前端(5173)
pwsh tools/start_local_dev.ps1 -SkipNpmInstall   # 依赖已装好时更快
pwsh tools/start_local_dev.ps1 -BackendOnly      # 只起后端（调试）
```

脚本会校验首次配置（`.env.local-demo.json`、`backend/.venv`、`frontend/node_modules`），缺失时按本页指引处理；两个服务各自开窗口运行，脚本等待期间**按任意键或 Ctrl+C 停止两者**（含子进程树）。用户在 `http://127.0.0.1:5173/`，管理员在 `http://localhost:5173/admin`。演示剧本见下文"演示事实的范围"。脚本源 `tools/start_local_dev.ps1`，与本节保持同步修改。

从仓库根目录操作，使用票02声明的依赖：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -e 'backend[dev]'
Copy-Item backend/app/agent_platform/local_demo.example.json .env.local-demo.json
```

仅在首次配置时复制模板，已有配置保持不变。在被 Git 忽略的 `.env.local-demo.json` 中填写智谱普通 API 密钥、固定的 API 签名秘密、银行验证秘密及管理密钥。服务端两个秘密至少32字节，分别使用随机值；管理密钥另设随机值。重启、恢复和更换代码目录时继续读取同一配置，不重新生成秘密。

`data_directory` 必须是本机绝对路径，例如仓库内被忽略的 `.mnemon/v03-local-demo` 的完整路径。应用库、任务检查点、审计与银行库保存在这里；重启继续使用原数据，银行播种入口为既有幂等实现，不重置余额或原交易。

```powershell
$env:BANK_LOCAL_CONFIG = (Resolve-Path .env.local-demo.json).Path
backend/.venv/Scripts/python -m uvicorn app.agent_platform.local_demo:create_local_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

另开终端，在 `frontend/` 运行 `npm ci`、`npm run dev`。前端使用 `real-api`，代理目标为 `http://127.0.0.1:8000`。用户页面用 `http://127.0.0.1:5173/`，管理员页面用 `http://localhost:5173/admin`；两个主机名分别保存会话 Cookie。配置中的允许来源与这两个地址一致。普通用户固定为模拟银行的 `U1`，管理员为独立的 `demo-admin`。管理密钥仅在管理页面登录时输入，不放进前端配置或浏览器持久存储。

服务实际请求智谱普通 API `https://open.bigmodel.cn/api/paas/v4/`，默认模型 `glm-4.7`，可在本机改成账户可调用的 GLM 型号。`langchain-openai` 是兼容客户端，`ModelSettings.provider` 与客户端标识保持为 `openai`；这不代表请求了 OpenAI 服务。配置版本带 `zhipu-local` 前缀并绑定模型、地址和演示事实。默认仍使用普通 API。2026-10-02项目负责人明确要求使用 Coding Plan 入口做本机测试：在本机配置显式设置 `base_url` 为 `https://open.bigmodel.cn/api/coding/paas/v4/`，`model_name` 为 `glm-5.3`。两个入口不会自动切换；额度/权限错误仍明确失败。该入口的测试证据须标明 Coding Plan，不作为普通 API 或生产部署可用证据。其他服务商和 Anthropic 协议地址不在此连接器范围内。

## 演示事实的范围

模板中的风险信号是明确标注的虚构演示事实，覆盖每个信号维度，不是模型判断、金额阈值或诈骗检测结果。读取请求使用固定演示环境事实；资金动作还必须与服务端不可变参数快照中的账户、已保存收款人和整数分金额完全匹配。

| 请求 | 服务端场景 | 预期结果 |
|---|---|---|
| 给妈妈转500元，主账户A1 | 常用收款人、设备、金额与清楚表达 | 正式确认及基础验证码；同会话验证是否可复用由安全门决定 |
| 给妈妈转501元，主账户A1 | 虚构“不常见金额”事实 | 正式确认、专用验证码及管理员模拟人脸 |
| 给妈妈转502元，主账户A1 | 虚构“保密或紧迫施压”事实 | 高风险终止，不提交资金 |
| 给妈妈转600元，主账户A1 | 用于修改演示的低风险场景 | 重新核对新确认单 |
| 其他未配置的转账参数 | 缺少完整可信演示事实 | 暂停风险核对，不假定低风险 |

501、502仅是便于选择场景的准确金额，不是风险阈值。收款人事实仍由银行公开入口提供；完整账号、未知对象或其他金额不会通过此场景表获得风险放行。原始用户消息无法修改场景事实。

## 验证和故障

```powershell
backend/.venv/Scripts/python -m pytest -q backend/app/agent_platform/test_local_demo.py
```

该测试走真实 API、Deep Agents 规划入口、受控安全策略、转账流程与模拟银行，仅模型响应由测试替身提供。覆盖普通回复、无效模型输出、低风险完整转账、重复验证码回执、重新构建服务读取原交易、中风险双因子及独立管理身份、高风险拒绝、无事实暂停和配置错误脱敏。测试模型证据不能记作真实 GLM 或浏览器验收。

配置缺失、无效配置、模型故障或没有唯一受控模型结果时失败，不自动换测试模型。配置错误只输出固定错误编号，避免解析器回显包含秘密的输入。模型密钥、签名秘密、银行秘密和管理密钥不进入提示词或业务审计。秘密保留在本机后端配置，配置值不入库。

真实 GLM 验收需从浏览器发送普通聊天及明确转账，再完成确认、验证和银行回执。修改、取消、连续点击、刷新、重新登录及后端重启均保留原任务/操作证据；资金提交次数以银行台账核对。额度不足等提供商故障是未通过，不以测试模型通过替代。
