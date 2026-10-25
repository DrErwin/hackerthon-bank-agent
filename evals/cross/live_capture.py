"""Observation-only S01 launcher; model/gate/bank decisions remain delegated."""

import argparse
from datetime import datetime, timezone
from functools import wraps
import json
from pathlib import Path
from threading import Lock

from langchain_core.callbacks import BaseCallbackHandler

from app.agent_platform.local_demo import load_config
from app.audit.journal import redact
from evals.cross.case_runner import create_case_app


class Capture(BaseCallbackHandler):
    def __init__(self, directory):
        self.path = directory / "observations.jsonl"
        config = load_config(directory / ".env.case.json")
        self.secrets = [getattr(config, name).get_secret_value()
                        for name in ("api_key", "api_secret", "bank_secret", "admin_key")]
        self.lock = Lock()

    def write(self, kind, **data):
        item = redact({"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **data},
                      self.secrets)
        with self.lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self.write("model.request", run_id=str(run_id), messages=[
            [{"role": item.type, "content": item.content} for item in group]
            for group in messages])

    def on_llm_end(self, response, *, run_id, **kwargs):
        self.write("model.response", run_id=str(run_id), generations=[
            [item.message.model_dump(mode="json") for item in group]
            for group in response.generations])

    def on_llm_error(self, error, *, run_id, **kwargs):
        self.write("model.error", run_id=str(run_id), error_type=type(error).__name__,
                   error_message=str(error))


def observe(app, directory):
    capture = Capture(directory)
    runtime = app.state.api.runtime
    model = runtime.harness.planner.model
    model.callbacks = [*(model.callbacks or []), capture]
    bank = runtime.gateway._bank
    original = bank.cancel_subscription

    @wraps(original)
    def cancel(context, operation_id, mandate_id):
        capture.write("bank.write_request", operation_id=str(operation_id),
                      mandate_id=mandate_id, action="bank.cancel_subscription")
        result = original(context, operation_id, mandate_id)
        capture.write("bank.write_response", operation_id=str(operation_id),
                      result=result.model_dump(mode="json"))
        return result

    bank.cancel_subscription = cancel

    @app.middleware("http")
    async def http(request, call_next):
        # No cookies, headers, codes or controlled request bodies are recorded.
        capture.write("http.request", method=request.method, path=request.url.path)
        response = await call_next(request)
        capture.write("http.response", method=request.method, path=request.url.path,
                      status=response.status_code)
        return response  # streaming bodies are never consumed or rewritten

    capture.write("capture.ready", provider=runtime.harness.planner.provider,
                  model=runtime.harness.planner.model_name,
                  config_version=runtime.harness.planner.config_version)
    return app


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8165)
    args = parser.parse_args()
    # create_case_app checks isolation before opening/observing the case.
    app = create_case_app(args.directory)
    uvicorn.run(observe(app, args.directory), host="127.0.0.1", port=args.port,
                workers=1, access_log=False)
