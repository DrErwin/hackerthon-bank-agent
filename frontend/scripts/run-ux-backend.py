"""Run the real local-demo stack with a fresh, isolated bank for browser QA.

BANK_LOCAL_CONFIG points to the existing private backend configuration. Its
credentials stay server-side; the configured data directory is never opened.
Run with the repository backend on PYTHONPATH and its installed dependencies.
"""
import os
from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4

import uvicorn

from app.agent_platform.local_demo import build_runtime, load_config
from app.api.app import ApiConfig, create_app


if __name__ == "__main__":
    config = load_config(Path(os.environ["BANK_LOCAL_CONFIG"]))
    config = config.model_copy(update={
        "data_directory": Path(mkdtemp(prefix="bank-frontend-ux-")),
        "demo_round_id": "frontend-ux-" + uuid4().hex[:12],
        "origins": ["http://127.0.0.1:5190", "http://localhost:5190"],
    })
    application = create_app(build_runtime(config), ApiConfig(
        secret=config.api_secret.get_secret_value().encode(),
        demo_user_id=config.demo_user_id,
        demo_round_id=config.demo_round_id,
        admin_user_id=config.admin_actor_id,
        admin_key=config.admin_key.get_secret_value(),
        origins=tuple(config.origins),
    ))
    print("Isolated UX bank:", config.data_directory, flush=True)
    uvicorn.run(application, host="127.0.0.1", port=5191, workers=1, access_log=False)
