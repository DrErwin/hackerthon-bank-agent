# 本机简易前端

## 使用契约测试响应

在 frontend 目录安装并启动：

```powershell
npm install
Copy-Item .env.example .env
```

把 .env 中的 VITE_API_MODE 设为 contract-demo，再运行：

```powershell
npm run dev
```

打开 Vite 显示的本机地址。页面会持续显示“契约测试响应”标记。发送“测试转账 500 元”可查看模拟收款人、确认单、专用验证码、管理员模拟人脸、时间线和模拟银行返回。测试验证码只在独立提示区临时显示为 123456。

契约测试响应只存在于浏览器演示数据，不会请求后端或银行。普通聊天会收到测试回复；聊天内容不会作为测试状态写入浏览器存储。测试模式下，输入任意非空管理员口令会模拟管理入口，这不代表真实权限。

## 接入真实本机 API

设置 VITE_API_MODE=real-api，并把 VITE_API_PROXY_TARGET 指向 API 服务地址。前端通过同源 /api/v1 代理发送请求，保留浏览器的 Cookie 和 Origin，不改写 API 路径，也不会在真实 API 出错时切到测试响应。

API 的 BANK_API_ORIGINS 需要允许浏览器来源 http://localhost:5173 和 http://127.0.0.1:5173。普通页面和管理员页面使用这两个不同主机名，浏览器会分别保存会话 Cookie；管理密钥只随管理员登录请求发送。

真实后端须按 backend/app/api/README.md 配置受控 runtime factory、演示用户、来源和管理密钥。v03-local-demo/04 尚未交付前，本机真实 API 组合可能无法启动；此时使用 contract-demo 检查页面，不把它记成真实接口验收。

## 检查

```powershell
npm test
npm run build
```

`npm test` 运行消息重试、跨会话恢复和权限按钮的 UI 检查。`npm run build` 包含 TypeScript 检查与 Vite 生产构建。

后端公共 Pydantic 模型变更后，在已安装后端依赖的 Python 环境中运行：

```powershell
npm run generate:contracts
```

该命令从 `backend/app/contracts/` 生成 `src/api.generated.ts`；页面使用的类型从生成文件导出，不要手改生成文件。

## 本次交付检查记录（2026-10-01）

- `npm run generate:contracts`、`npm test`（7 项通过）与 `npm run build` 通过。审查修复了迟到的旧对话响应混入当前对话、明确拒绝消息后输入框锁定、同一验证挑战状态不刷新及历史记录漏分页；回归检查覆盖这些情形。
- 契约测试响应下走查了普通聊天回复、收款人查询、脱敏确认、专用验证码、管理员模拟人脸、模拟银行回执、确认前取消，以及管理员只读时间线。所有结果均明确标为测试数据。
- 新会话任务若由 API 标记 `recovery_required`，前端提供单一“恢复原任务”入口并调用 `/tasks/{task_id}/resume`；旧确认与验证动作仍按服务端返回禁用，权限与当前任务状态由 API 再次核验。
- 此记录可供原票 `v03-erwin-vertical-backend/10-api-task-stream` 的前端普通回复验收和 `v03-erwin-vertical-backend/12-v03-acceptance-closeout` 查阅；仅证明契约测试响应中的页面交互，不证明真实 API、模型、银行或 AF01—AF14 验收。
- 真实 API 联调依赖 `v03-local-demo/04`；它被本地票 02、03 与可用凭据阻塞。真实接口恢复、AF01 主路径和联合验收仍待依赖就绪后执行。
- 本轮规范与规格审查均为 AI 审查；项目负责人在当前聊天明确授权修复与合并。此授权用于本次合入，不作为 Ringo 真人专业审查或真实接口验收的证据。
