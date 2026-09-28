"""Repeatable, disposable mock-bank fixtures for the v0.3 evaluation suite."""

from __future__ import annotations

import pytest

from app.contracts.platform import TrustedContext
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage import StoragePaths
from app.storage.mock_bank.repository import MockBankStore


DEMO_SECRET = b"mock-bank-eval-secret-is-at-least-32-bytes"


@pytest.fixture
def user_context() -> TrustedContext:
    return TrustedContext(
        user_id="U1", session_id="S1", task_id="T1", run_id="R1",
        parent_task_id=None, demo_round_id="D1",
    )


@pytest.fixture
def bank_runtime(tmp_path):
    database_path = StoragePaths(tmp_path).bank
    gateways: list[BankGateway] = []

    def new_bank(*, slow_seconds: float = 0.12) -> MockBankService:
        return MockBankService(
            MockBankStore(database_path), demo_secret=DEMO_SECRET,
            slow_seconds=slow_seconds,
        )

    bank = new_bank()

    def new_gateway(
        bank_service: MockBankService = bank, *, timeout: float = 2.0,
        authorized: bool | None = True,
    ) -> BankGateway:
        options = {"transfer_timeout_seconds": timeout}
        if authorized is not None:
            options["authorize_transfer"] = lambda *_: authorized
        options["authorize_face"] = lambda *_: True
        gateway = BankGateway(bank_service, **options)
        gateways.append(gateway)
        return gateway

    yield bank, database_path, new_bank, new_gateway

    for gateway in gateways:
        gateway.close()
