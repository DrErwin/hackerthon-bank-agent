# 后端开发

本目录是后端工程（Python 3.11 或更新版本）：平台 / 底座（`app/api/`、`app/agent_platform/`、`app/contracts/`、`app/audit/`、`app/memory/`、`app/services/`、`app/storage/`）与业务模块（`app/modules/`）。各目录的边界、接口与验证口径见其 README（[api](app/api/README.md) · [agent_platform](app/agent_platform/README.md) · [contracts](app/contracts/README.md) · [security](app/security/README.md) · [services](app/services/README.md) · [modules](app/modules/README.md)）。从 `backend/` 目录运行以下命令。

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
.venv\Scripts\python -m uvicorn app.main:app --reload
```

macOS / Linux：

```sh
.venv/bin/python -m uvicorn app.main:app --reload
```

服务默认监听 `http://127.0.0.1:8000`。当前只提供 FastAPI 工程入口；业务接口由后续票据接入。
