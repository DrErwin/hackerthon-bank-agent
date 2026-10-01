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
npm run build
```

build 包含 TypeScript 检查与 Vite 生产构建。

后端公共 Pydantic 模型变更后，在已安装后端依赖的 Python 环境中运行：

```powershell
npm run generate:contracts
```

该命令从 `backend/app/contracts/` 生成 `src/api.generated.ts`；页面使用的类型从生成文件导出，不要手改生成文件。
