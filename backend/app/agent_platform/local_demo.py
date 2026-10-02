"""Local GLM composition: server-owned configuration, policy and durable stores."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator

from app.api.app import ApiConfig, create_app
from app.audit.journal import AuditJournal
from app.contracts.bank import SavedPayee
from app.memory.adapter import MemoryAdapter
from app.modules.transfer.tools import TransferSnapshots
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.database import StoragePaths
from app.storage.mock_bank.repository import MockBankStore

from .model import DeepAgentPlanner, ModelSettings
from .transfer_runtime import TransferRuntime


class RiskFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    signals: list[DemoRiskSignal]
    checked_signals: list[DemoRiskSignal]

    def evidence(self, version: str) -> DemoRiskEvidence:
        return DemoRiskEvidence(
            source="server-local-demo-fixture", source_version=version,
            evidence_ref=self.fixture_id, signals=frozenset(self.signals),
            checked_signals=frozenset(self.checked_signals),
        )


class TransferFixture(RiskFixture):
    payer_account_id: str
    payee_id: str
    amount_fen: int = Field(gt=0, strict=True)


class LocalDemoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr
    api_secret: SecretStr
    bank_secret: SecretStr
    admin_key: SecretStr
    model_name: str = "glm-4.7"
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    data_directory: Path
    demo_round_id: str = "D1"
    # The existing mock bank's seeded demonstration account belongs to U1.
    demo_user_id: str = "U1"
    admin_actor_id: str = "demo-admin"
    origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    facts_version: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    read_fixture: RiskFixture
    transfer_fixtures: list[TransferFixture]

    @model_validator(mode="after")
    def validate_local_scope(self):
        if not self.api_key.get_secret_value().strip() or not self.admin_key.get_secret_value().strip():
            raise ValueError("credentials are required")
        if any(len(secret.get_secret_value().encode()) < 32 for secret in (self.api_secret, self.bank_secret)):
            raise ValueError("fixed server secrets require at least 32 bytes")
        if not self.data_directory.is_absolute():
            raise ValueError("data_directory must be an absolute stable path")
        if self.demo_user_id != "U1" or self.admin_actor_id == self.demo_user_id:
            raise ValueError("identities must match the seeded demo and separate admin")
        if not self.demo_round_id.strip() or not self.model_name.startswith("glm-"):
            raise ValueError("demo round and GLM model must be configured")
        endpoint = urlparse(self.base_url)
        if (endpoint.scheme != "https" or endpoint.hostname != "open.bigmodel.cn"
                or endpoint.path.rstrip("/") not in {"/api/paas/v4", "/api/coding/paas/v4"}
                or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.port):
            raise ValueError("use an explicitly configured Zhipu chat-completion endpoint")
        for origin in self.origins:
            parsed = urlparse(origin)
            if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}
                    or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
                raise ValueError("only explicit local browser origins are supported")
        if not self.origins:
            raise ValueError("browser origins must be configured")
        seen = set()
        for fixture in [self.read_fixture, *self.transfer_fixtures]:
            fixture.evidence(self.facts_version)
        for fixture in self.transfer_fixtures:
            identity = (fixture.payer_account_id, fixture.payee_id, fixture.amount_fen)
            if identity in seen:
                raise ValueError("transfer fixture bindings must be unique")
            seen.add(identity)
        return self


def load_config(path: Path) -> LocalDemoConfig:
    try:
        return LocalDemoConfig.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValidationError, ValueError):
        # Pydantic's normal diagnostics may include the complete input (secrets).
        raise ValueError("LOCAL_DEMO_CONFIG_INVALID") from None


def build_runtime(config: LocalDemoConfig) -> TransferRuntime:
    model = ChatOpenAI(
        model=config.model_name, api_key=config.api_key,
        base_url=config.base_url, temperature=0, max_retries=0, timeout=60,
        use_responses_api=False,
    )
    version = hashlib.sha256(json.dumps({
        "model": config.model_name, "endpoint": config.base_url,
        "facts_version": config.facts_version,
        "fixtures": [item.model_dump(mode="json") for item in config.transfer_fixtures],
        "read_fixture": config.read_fixture.model_dump(mode="json"),
    }, sort_keys=True).encode()).hexdigest()[:16]
    planner = DeepAgentPlanner(ModelSettings(
        model=model, provider="openai", model_name=config.model_name,
        config_version=f"zhipu-local-{version}",
    ))
    paths = StoragePaths(config.data_directory)
    application = ApplicationStore(paths.application)
    snapshots = TransferSnapshots(paths.application)

    def risk_facts(context, action, declaration):
        parameters = snapshots.resolve(context, action)
        if not declaration.side_effect:
            return config.read_fixture.evidence(config.facts_version)
        # These are operator-defined fictional scenarios, bound to the same
        # immutable parameters used for confirmation and eventual execution.
        for fixture in config.transfer_fixtures:
            if (parameters.get("payer_account_id") == fixture.payer_account_id
                    and parameters.get("payee") == SavedPayee(kind="saved", payee_id=fixture.payee_id).model_dump()
                    and parameters.get("amount_fen") == fixture.amount_fen):
                return fixture.evidence(config.facts_version)
        raise RiskFactsUnavailable(
            "no server-owned fixture covers this transfer",
            rule_id="local-demo-fixture-required",
            policy_version=DemoSecurityPolicy.policy_version,
        )

    policy = DemoSecurityPolicy(
        demo_user_id=config.demo_user_id, admin_actor_id=config.admin_actor_id,
        current_demo_round=lambda: config.demo_round_id, risk_facts=risk_facts,
    )
    return TransferRuntime(
        application, MemoryAdapter(application, active_round=lambda: config.demo_round_id),
        AuditJournal(paths.application),
        MockBankService(MockBankStore(paths.bank), demo_secret=config.bank_secret.get_secret_value().encode()),
        planner, authorize_capability=policy.authorize_capability,
        authorize_tool=policy.authorize_tool, assess_risk=policy.assess_risk,
        authorize_face=policy.authorize_face,
    )


def create_local_app():
    """uvicorn app.agent_platform.local_demo:create_local_app --factory --workers 1."""
    configured_path = os.environ.get("BANK_LOCAL_CONFIG")
    if not configured_path:
        raise ValueError("BANK_LOCAL_CONFIG_REQUIRED")
    config = load_config(Path(configured_path))
    return create_app(build_runtime(config), ApiConfig(
        secret=config.api_secret.get_secret_value().encode(),
        demo_user_id=config.demo_user_id, demo_round_id=config.demo_round_id,
        admin_user_id=config.admin_actor_id, admin_key=config.admin_key.get_secret_value(),
        origins=tuple(config.origins),
    ))
