# 后端开发

本目录是后端工程（Python 3.11 或更新版本）：平台 / 底座（`app/api/`、`app/agent_platform/`、`app/contracts/`、`app/audit/`、`app/memory/`、`app/services/`、`app/storage/`）与业务模块（`app/modules/`）。各目录的边界、接口与验证口径见其 README（[api](app/api/README.md) · [agent_platform](app/agent_platform/README.md) · [contracts](app/contracts/README.md) · [security](app/security/README.md) · [services](app/services/README.md) · [modules](app/modules/README.md)）。从 `backend/` 目录运行以下命令。

当前状态（2026-10-29）：业务 API、转账/账单/订阅及三个生活目标编排已合入，最近产品提交 `ffa42936`。验证来源、演示风险边界及未完成项见[v0.5 完成情况](../docs/versions/v0.5.0/completion.md)，不要将历史完整批当作最新代码的完整验收。

## 安装

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

不运行测试时，可把 `.[dev]` 改成 `.`，只安装运行依赖。

## 测试

Windows PowerShell：

```powershell
.venv\Scripts\python -m pytest
```

macOS / Linux：

```sh
.venv/bin/python -m pytest
```

默认测试命令会运行 `tests/` 中的工程入口测试和 `app/` 中各模块的业务测试。模拟银行场景评测需另行运行 `python -m pytest -q ../evals/mockbank/test_mockbank_eval.py`。

## 本地启动

Windows PowerShell：

```powershell
.venv\Scripts\python -m uvicorn app.api.app:app --reload
```

macOS / Linux：

```sh
.venv/bin/python -m uvicorn app.api.app:app --reload
```

服务默认监听 `http://127.0.0.1:8000`。启动前按[API 配置说明](app/api/README.md)设置本机配置；模型及演示授权配置保留在本机。与前台一起体验可按[前端运行说明](../frontend/README.md)启动隔离演示环境。
