"""Persistent, atomic state used by the v0.3 security gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Callable, Literal
from uuid import UUID, uuid4

from app.audit.journal import run_key
from app.contracts.audit import AuditEvent, SecurityDecidedPayload
from app.contracts.common import (
    ContractModel, ID, OperationId, OperationLevel, Phase, PositiveInt,
    PositiveMoney, SecurityDecisionCode, Timestamp,
)
from app.contracts.security import (
    ActionDescriptor,
    ConfirmationRecord,
    ExecutionSecurityContext,
    SecurityDecision,
    VerificationChallenge,
)
from app.storage.database import connect, transaction


RETIREMENT_POLICY_VERSION = "v05-birthday-retirement-1"
SESSION_RETIREMENT_POLICY_VERSION = "v05-birthday-session-retirement-1"
RecoveryValidator = Callable[[sqlite3.Connection, ExecutionSecurityContext, dict[str, object]], bool]


class SecurityStateError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class FreezeReleaseAuthorization(ContractModel):
    """The §3.5 backend-controlled limited-release record (safety annex §3.1)."""

    release_authorization_id: ID
    user_id: ID
    session_id: ID
    demo_round_id: ID
    task_id: ID
    account_id: ID
    freeze_operation_id: OperationId
    freeze_id: ID | None
    confirmation_id: ID
    confirmation_version: PositiveInt
    max_amount_fen: PositiveMoney
    granted_at: Timestamp
    status: Literal["pending_freeze", "active", "completed", "invalid"]
    # Optional (old rows read as None): the exact attempt this authority belongs
    # to, so a sealed retirement of another revision cannot block a later one.
    action_revision: PositiveInt | None = None
    # Only a proven-unsubmitted retirement writes this reason; a bank failure
    # keeps it empty so the ending keeps reporting FREEZE_FAILED.
    invalid_reason: Literal["RETIRED_UNSUBMITTED"] | None = None


class RetirementRecord(ContractModel):
    """One unsubmitted attempt's acceptance or sealed, auditable withdrawal."""

    retirement_id: ID
    user_id: ID
    demo_round_id: ID
    task_id: ID
    operation_id: OperationId
    action_revision: PositiveInt
    state: Literal["pending_proof", "sealed", "conflict"]
    original_binding: dict[str, object]
    bank_evidence: dict[str, object] | None
    audit_ref: ID | None
    created_at: Timestamp
    sealed_at: Timestamp | None


_SAFE_BINDING_FIELDS = (
    "action_name", "parameters_ref", "resource_refs", "phase",
    "confirmation_id", "confirmation_version",
)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_RELEASE_TRANSITIONS = frozenset({
    ("pending_freeze", "active"),
    ("pending_freeze", "invalid"),
    ("active", "completed"),
    ("active", "invalid"),
})


@dataclass(frozen=True)
class ExecutionClaim:
    operation_id: str
    user_id: str
    demo_round_id: str
    task_id: str
    action_name: str
    parameters_ref: str
    action_revision: int
    state: Literal["processing", "completed", "unknown"]
    decision: SecurityDecision
    result_ref: str | None


class SQLiteSecurityState:
    """Stores confirmations and execution claims in the application database."""

    def __init__(self, path: Path):
        self.path = path
        with transaction(path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS security_confirmations (
                    confirmation_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    action_name TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    confirmation_json TEXT NOT NULL,
                    claimed INTEGER NOT NULL DEFAULT 0 CHECK(claimed IN (0, 1)),
                    UNIQUE(task_id, action_name, operation_id)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS security_executions (
                    operation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    action_name TEXT NOT NULL,
                    parameters_ref TEXT NOT NULL,
                    action_revision INTEGER NOT NULL CHECK(action_revision > 0),
                    state TEXT NOT NULL CHECK(state IN ('processing', 'completed', 'unknown')),
                    decision_json TEXT NOT NULL,
                    result_ref TEXT
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS security_terminated_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    reason_code TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS security_verification_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    challenge_json TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS security_release_authorizations (
                    release_authorization_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    freeze_operation_id TEXT NOT NULL,
                    authorization_json TEXT NOT NULL,
                    UNIQUE(task_id, freeze_operation_id)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS security_retirements (
                    retirement_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    action_revision INTEGER NOT NULL CHECK(action_revision > 0),
                    state TEXT NOT NULL
                        CHECK(state IN ('pending_proof', 'sealed', 'conflict')),
                    original_binding_json TEXT NOT NULL,
                    bank_evidence_json TEXT,
                    audit_ref TEXT,
                    created_at TEXT NOT NULL,
                    sealed_at TEXT,
                    UNIQUE(user_id, demo_round_id, task_id, operation_id, action_revision)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS security_confirmation_history (
                    confirmation_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version > 0),
                    record_json TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    PRIMARY KEY(confirmation_id, version)
                )
            """)

    def remember_challenge(self, context: ExecutionSecurityContext, challenge: VerificationChallenge) -> None:
        with transaction(self.path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO security_verification_challenges VALUES (?, ?, ?, ?, ?)",
                (challenge.challenge_id, context.user_id, context.demo_round_id,
                 context.task_id, challenge.model_dump_json()),
            )

    def issued_challenges(self, context: ExecutionSecurityContext) -> list[VerificationChallenge]:
        connection = connect(self.path)
        try:
            rows = connection.execute(
                "SELECT challenge_json FROM security_verification_challenges WHERE user_id = ? AND demo_round_id = ? AND task_id = ?",
                (context.user_id, context.demo_round_id, context.task_id),
            ).fetchall()
            return [VerificationChallenge.model_validate_json(row["challenge_json"]) for row in rows]
        finally:
            connection.close()

    def is_task_terminated(self, context: ExecutionSecurityContext) -> bool:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM security_terminated_tasks WHERE task_id = ?", (context.task_id,),
            ).fetchone()
            if row is None:
                return False
            if (row["user_id"], row["demo_round_id"]) != (
                context.user_id, context.demo_round_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            return True
        finally:
            connection.close()

    def terminate_task(self, context: ExecutionSecurityContext, reason_code: str) -> None:
        with transaction(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM security_terminated_tasks WHERE task_id = ?", (context.task_id,),
            ).fetchone()
            if row is not None and (row["user_id"], row["demo_round_id"]) != (
                context.user_id, context.demo_round_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            connection.execute(
                """INSERT OR IGNORE INTO security_terminated_tasks
                   (task_id, user_id, demo_round_id, reason_code) VALUES (?, ?, ?, ?)""",
                (context.task_id, context.user_id, context.demo_round_id, reason_code),
            )

    @staticmethod
    def _record(row) -> ConfirmationRecord:
        return ConfirmationRecord.model_validate_json(row["confirmation_json"])

    @staticmethod
    def _claim(row) -> ExecutionClaim:
        return ExecutionClaim(
            operation_id=row["operation_id"],
            user_id=row["user_id"],
            demo_round_id=row["demo_round_id"],
            task_id=row["task_id"],
            action_name=row["action_name"],
            parameters_ref=row["parameters_ref"],
            action_revision=row["action_revision"],
            state=row["state"],
            decision=SecurityDecision.model_validate_json(row["decision_json"]),
            result_ref=row["result_ref"],
        )

    @staticmethod
    def _check_owner(context: ExecutionSecurityContext, record: ConfirmationRecord) -> None:
        if (
            record.user_id,
            record.session_id,
            record.demo_round_id,
            record.task_id,
        ) != (
            context.user_id,
            context.session_id,
            context.demo_round_id,
            context.task_id,
        ):
            raise SecurityStateError("ACCESS_DENIED")

    def create_confirmation(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        display_fields: list,
        now: datetime,
        expires_at: datetime,
    ) -> ConfirmationRecord:
        if context.operation_id is None or context.action_revision is None:
            raise SecurityStateError("INPUT_REQUIRED")
        with transaction(self.path) as connection:
            # A withdrawal in progress/settled must not reissue an approved-looking
            # confirmation for the old attempt.
            self._ensure_attempt_not_retired(connection, context)
            row = connection.execute(
                """SELECT * FROM security_confirmations
                   WHERE task_id = ? AND action_name = ? ORDER BY rowid DESC LIMIT 1""",
                (context.task_id, action.action_name),
            ).fetchone()
            if row is not None:
                current = self._record(row)
                if (current.user_id, current.demo_round_id, current.task_id) != (
                    context.user_id, context.demo_round_id, context.task_id,
                ):
                    raise SecurityStateError("ACCESS_DENIED")
                if row["claimed"]:
                    # One unresolved confirmation per action: a claimed record
                    # whose execution already settled makes room for the next
                    # sequential write of the same action (birthday items).
                    settled = connection.execute(
                        """SELECT state FROM security_executions
                           WHERE operation_id = ? AND state != 'processing'""",
                        (str(current.operation_id),),
                    ).fetchone()
                    if settled is None:
                        raise SecurityStateError("OPERATION_UNKNOWN")
                if current.decision == "cancelled":
                    raise SecurityStateError("TASK_TERMINATED")
                if current.operation_id == context.operation_id and (
                    current.action_revision != context.action_revision
                    or current.parameters_ref != action.parameters_ref
                    or current.display_fields != display_fields
                ):
                    raise SecurityStateError("OPERATION_CONFLICT")
                if (
                    current.operation_id != context.operation_id
                    and context.action_revision <= current.action_revision
                ):
                    raise SecurityStateError("OPERATION_CONFLICT")
                if (
                    current.operation_id == context.operation_id
                    and current.session_id == context.session_id
                    and current.action_revision == context.action_revision
                    and current.parameters_ref == action.parameters_ref
                    and current.decision in {"pending", "approved"}
                    and now < current.expires_at
                ):
                    return current
                # The UPSERT below overwrites this complete record: keep what the
                # user actually saw and decided before only its id/version remain.
                connection.execute(
                    """INSERT OR IGNORE INTO security_confirmation_history
                       (confirmation_id, version, record_json, captured_at)
                       VALUES (?, ?, ?, ?)""",
                    (current.confirmation_id, current.confirmation_version,
                     current.model_dump_json(), now.isoformat()),
                )
                confirmation_id = current.confirmation_id
                version = current.confirmation_version + 1
            else:
                confirmation_id = str(uuid4())
                version = 1
            record = ConfirmationRecord(
                confirmation_id=confirmation_id,
                confirmation_version=version,
                user_id=context.user_id,
                session_id=context.session_id,
                demo_round_id=context.demo_round_id,
                task_id=context.task_id,
                operation_id=context.operation_id,
                action_name=action.action_name,
                action_revision=context.action_revision,
                parameters_ref=action.parameters_ref,
                display_fields=display_fields,
                created_at=now,
                expires_at=expires_at,
                decision="pending",
                decided_at=None,
            )
            connection.execute(
                """INSERT INTO security_confirmations VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                   ON CONFLICT(confirmation_id) DO UPDATE SET
                     task_id=excluded.task_id, user_id=excluded.user_id,
                     session_id=excluded.session_id, demo_round_id=excluded.demo_round_id,
                     action_name=excluded.action_name, operation_id=excluded.operation_id,
                     confirmation_json=excluded.confirmation_json, claimed=0""",
                (
                    record.confirmation_id, record.task_id, record.user_id, record.session_id,
                    record.demo_round_id, record.action_name, str(record.operation_id),
                    record.model_dump_json(),
                ),
            )
            return record

    def get_confirmation(
        self,
        context: ExecutionSecurityContext,
        confirmation_id: str,
        now: datetime,
    ) -> ConfirmationRecord:
        with transaction(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM security_confirmations WHERE confirmation_id = ?",
                (confirmation_id,),
            ).fetchone()
            if row is None:
                raise SecurityStateError("CONFIRMATION_STALE")
            record = self._record(row)
            self._check_owner(context, record)
            if (
                not row["claimed"]
                and record.decision in {"pending", "approved"}
                and now >= record.expires_at
            ):
                record = record.model_copy(update={"decision": "expired", "decided_at": None})
                connection.execute(
                    "UPDATE security_confirmations SET confirmation_json = ? WHERE confirmation_id = ?",
                    (record.model_dump_json(), confirmation_id),
                )
            return record

    def get_confirmation_history(
        self,
        context: ExecutionSecurityContext,
        confirmation_id: str,
        version: int | None = None,
    ) -> list[ConfirmationRecord]:
        """Read-only replay of versions replaced before this confirmation was reused."""
        connection = connect(self.path)
        try:
            query = "SELECT * FROM security_confirmation_history WHERE confirmation_id = ?"
            parameters: list[object] = [confirmation_id]
            if version is not None:
                query += " AND version = ?"
                parameters.append(version)
            rows = connection.execute(query + " ORDER BY version", parameters).fetchall()
        finally:
            connection.close()
        records = [ConfirmationRecord.model_validate_json(row["record_json"]) for row in rows]
        for record in records:
            self._check_owner(context, record)
        return records

    def answer_confirmation(
        self,
        context: ExecutionSecurityContext,
        confirmation_id: str,
        version: int,
        choice: str,
        now: datetime,
    ) -> ConfirmationRecord:
        with transaction(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM security_confirmations WHERE confirmation_id = ?",
                (confirmation_id,),
            ).fetchone()
            if row is None:
                raise SecurityStateError("CONFIRMATION_STALE")
            record = self._record(row)
            self._check_owner(context, record)
            if version != record.confirmation_version:
                raise SecurityStateError("CONFIRMATION_STALE")
            if choice == "approve":
                # A late approval must not recreate an "approved" fact for an
                # attempt whose edit/withdrawal is in progress or settled.
                self._ensure_attempt_not_retired(connection, context)
            if (
                not row["claimed"]
                and record.decision in {"pending", "approved"}
                and now >= record.expires_at
            ):
                record = record.model_copy(update={"decision": "expired", "decided_at": None})
            wanted = "approved" if choice == "approve" else "cancelled"
            if record.decision == wanted:
                return record
            if record.decision == "expired":
                connection.execute(
                    "UPDATE security_confirmations SET confirmation_json = ? WHERE confirmation_id = ?",
                    (record.model_dump_json(), confirmation_id),
                )
            else:
                if wanted == "cancelled" and record.decision == "approved" and not row["claimed"]:
                    changed = record.model_copy(update={"decision": "cancelled", "decided_at": now})
                elif record.decision == "pending":
                    changed = record.model_copy(update={"decision": wanted, "decided_at": now})
                else:
                    raise SecurityStateError("CONFIRMATION_CONFLICT")
                connection.execute(
                    "UPDATE security_confirmations SET confirmation_json = ? WHERE confirmation_id = ?",
                    (changed.model_dump_json(), confirmation_id),
                )
                return changed
        raise SecurityStateError("CONFIRMATION_EXPIRED")

    @staticmethod
    def _validate_execution_row(
        row,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
    ) -> None:
        if (row["user_id"], row["demo_round_id"], row["task_id"]) != (
            context.user_id, context.demo_round_id, context.task_id,
        ):
            raise SecurityStateError("ACCESS_DENIED")
        if (
            row["action_name"], row["parameters_ref"], row["action_revision"]
        ) != (
            action.action_name, action.parameters_ref, context.action_revision,
        ):
            raise SecurityStateError("OPERATION_CONFLICT")

    def get_execution(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
    ) -> ExecutionClaim | None:
        if context.operation_id is None:
            return None
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM security_executions WHERE operation_id = ?",
                (str(context.operation_id),),
            ).fetchone()
            if row is None:
                return None
            self._validate_execution_row(row, context, action)
            return self._claim(row)
        finally:
            connection.close()

    def claim_execution(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        decision: SecurityDecision,
        now: datetime,
        task_state_resolver: Callable[[ExecutionSecurityContext], bool],
    ) -> tuple[ExecutionClaim, bool]:
        if (
            context.operation_id is None
            or context.action_revision is None
            or context.confirmation_id is None
            or context.confirmation_version is None
        ):
            raise SecurityStateError("CONFIRMATION_REQUIRED")
        with transaction(self.path) as connection:
            terminated = connection.execute(
                "SELECT * FROM security_terminated_tasks WHERE task_id = ?", (context.task_id,),
            ).fetchone()
            if terminated is not None:
                raise SecurityStateError("TASK_TERMINATED")
            try:
                task_result = task_state_resolver(context)
            except Exception as exc:
                raise SecurityStateError("DEPENDENCY_UNAVAILABLE") from exc
            if not isinstance(task_result, bool):
                raise SecurityStateError("DEPENDENCY_UNAVAILABLE")
            if task_result:
                raise SecurityStateError("TASK_TERMINATED")
            retirement = self._retirement_row(connection, context)
            if retirement is not None and retirement["state"] == "sealed":
                # A sealed retirement proves the attempt was never submitted, so
                # it can never be claimed afterwards (authority §2).
                raise SecurityStateError("ACTION_RETIRED")
            existing = connection.execute(
                "SELECT * FROM security_executions WHERE operation_id = ?",
                (str(context.operation_id),),
            ).fetchone()
            if existing is not None:
                self._validate_execution_row(existing, context, action)
                return self._claim(existing), False
            row = connection.execute(
                "SELECT * FROM security_confirmations WHERE confirmation_id = ?",
                (context.confirmation_id,),
            ).fetchone()
            if row is None:
                raise SecurityStateError("CONFIRMATION_STALE")
            record = self._record(row)
            self._check_owner(context, record)
            if record.confirmation_version != context.confirmation_version:
                raise SecurityStateError("CONFIRMATION_STALE")
            if not row["claimed"] and now >= record.expires_at:
                expired = record.model_copy(update={"decision": "expired", "decided_at": None})
                connection.execute(
                    "UPDATE security_confirmations SET confirmation_json = ? WHERE confirmation_id = ?",
                    (expired.model_dump_json(), record.confirmation_id),
                )
            else:
                if record.decision == "cancelled":
                    raise SecurityStateError("TASK_TERMINATED")
                if record.decision != "approved":
                    raise SecurityStateError("CONFIRMATION_REQUIRED")
                if (
                    record.operation_id != context.operation_id
                    or record.action_name != action.action_name
                    or record.action_revision != context.action_revision
                    or record.parameters_ref != action.parameters_ref
                ):
                    raise SecurityStateError("CONFIRMATION_STALE")
                connection.execute(
                    """INSERT INTO security_executions VALUES (?, ?, ?, ?, ?, ?, ?, 'processing', ?, NULL)""",
                    (
                        str(context.operation_id), context.user_id, context.demo_round_id,
                        context.task_id, action.action_name, action.parameters_ref,
                        context.action_revision, decision.model_dump_json(),
                    ),
                )
                connection.execute(
                    "UPDATE security_confirmations SET claimed = 1 WHERE confirmation_id = ?",
                    (record.confirmation_id,),
                )
                if retirement is not None and retirement["state"] == "pending_proof":
                    # The claim wins in this same transaction: the accepted edit
                    # attempt turns into evidence that it lost and can never seal.
                    connection.execute(
                        "UPDATE security_retirements SET state = 'conflict' WHERE retirement_id = ?",
                        (retirement["retirement_id"],),
                    )
                created = connection.execute(
                    "SELECT * FROM security_executions WHERE operation_id = ?",
                    (str(context.operation_id),),
                ).fetchone()
                return self._claim(created), True
        raise SecurityStateError("CONFIRMATION_EXPIRED")

    def record_execution(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        state: Literal["processing", "completed", "unknown"],
        result_ref: str | None,
    ) -> ExecutionClaim:
        if context.operation_id is None:
            raise SecurityStateError("INPUT_REQUIRED")
        with transaction(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM security_executions WHERE operation_id = ?",
                (str(context.operation_id),),
            ).fetchone()
            if row is None:
                raise SecurityStateError("OPERATION_UNKNOWN")
            self._validate_execution_row(row, context, action)
            if row["state"] == "completed" and (
                row["state"], row["result_ref"]
            ) != (state, result_ref):
                raise SecurityStateError("OPERATION_CONFLICT")
            connection.execute(
                "UPDATE security_executions SET state = ?, result_ref = ? WHERE operation_id = ?",
                (state, result_ref, str(context.operation_id)),
            )
            updated = connection.execute(
                "SELECT * FROM security_executions WHERE operation_id = ?",
                (str(context.operation_id),),
            ).fetchone()
            return self._claim(updated)

    # --- unsubmitted-attempt retirement (v05-birthday-platform-dependencies/02) ---

    @staticmethod
    def _retirement_binding(
        context: ExecutionSecurityContext, action: ActionDescriptor,
    ) -> dict[str, object]:
        return {
            "action_name": action.action_name,
            "parameters_ref": action.parameters_ref,
            "resource_refs": list(action.resource_refs),
            "phase": action.phase.value,
            "confirmation_id": context.confirmation_id,
            "confirmation_version": context.confirmation_version,
            "session_id": context.session_id,
            "run_id": context.run_id,
            "source_task_id": context.source_task_id,
        }

    @staticmethod
    def _binding_key(binding: dict[str, object]) -> str:
        return _canonical({field: binding.get(field) for field in _SAFE_BINDING_FIELDS})

    @staticmethod
    def _retirement(row) -> RetirementRecord:
        return RetirementRecord(
            retirement_id=row["retirement_id"],
            user_id=row["user_id"],
            demo_round_id=row["demo_round_id"],
            task_id=row["task_id"],
            operation_id=row["operation_id"],
            action_revision=row["action_revision"],
            state=row["state"],
            original_binding=json.loads(row["original_binding_json"]),
            bank_evidence=(
                json.loads(row["bank_evidence_json"])
                if row["bank_evidence_json"] is not None else None
            ),
            audit_ref=row["audit_ref"],
            created_at=datetime.fromisoformat(row["created_at"]),
            sealed_at=(
                datetime.fromisoformat(row["sealed_at"])
                if row["sealed_at"] is not None else None
            ),
        )

    @staticmethod
    def _ensure_task_open(
        connection,
        context: ExecutionSecurityContext,
        task_state_resolver: Callable[[ExecutionSecurityContext], bool],
    ) -> None:
        """Same task gate and priority as claim_execution, inside the transaction."""
        terminated = connection.execute(
            "SELECT * FROM security_terminated_tasks WHERE task_id = ?",
            (context.task_id,),
        ).fetchone()
        if terminated is not None:
            raise SecurityStateError("TASK_TERMINATED")
        try:
            task_result = task_state_resolver(context)
        except Exception as exc:
            raise SecurityStateError("DEPENDENCY_UNAVAILABLE") from exc
        if not isinstance(task_result, bool):
            raise SecurityStateError("DEPENDENCY_UNAVAILABLE")
        if task_result:
            raise SecurityStateError("TASK_TERMINATED")

    @staticmethod
    def _retirement_row(connection, context: ExecutionSecurityContext):
        if context.operation_id is None or context.action_revision is None:
            return None
        return connection.execute(
            """SELECT * FROM security_retirements
               WHERE user_id = ? AND demo_round_id = ? AND task_id = ?
                 AND operation_id = ? AND action_revision = ?""",
            (
                context.user_id, context.demo_round_id, context.task_id,
                str(context.operation_id), context.action_revision,
            ),
        ).fetchone()

    @classmethod
    def _ensure_attempt_not_retired(cls, connection, context) -> None:
        retirement = cls._retirement_row(connection, context)
        if retirement is not None and retirement["state"] in {"pending_proof", "sealed"}:
            raise SecurityStateError("ACTION_RETIRED")

    def begin_retirement(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        now: datetime,
        *,
        task_state_resolver: Callable[[ExecutionSecurityContext], bool],
    ) -> RetirementRecord:
        """Accept one unsubmitted attempt for retirement without granting anything.

        Claim and acceptance share this transaction, so exactly one of "claim"
        and "pending proof" can win; the record is evidence, not an edit right.
        The caller must pass the same trusted task-state resolver claim_execution
        uses: an ended/cancelled/needs-attention task must never yield edit proof.
        """
        if context.operation_id is None or context.action_revision is None:
            raise SecurityStateError("INPUT_REQUIRED")
        binding = self._retirement_binding(context, action)
        with transaction(self.path) as connection:
            self._ensure_task_open(connection, context, task_state_resolver)
            return self._accept_retirement(connection, context, binding, now)

    def begin_session_retirement(
        self, context: ExecutionSecurityContext, action: ActionDescriptor, now: datetime,
        *, source_session_id: str, source_confirmation_id: str,
        source_confirmation_version: int, recovery_validator: RecoveryValidator,
    ) -> RetirementRecord:
        """Withdraw an exact old-session attempt, never transfer its approval.

        The provider must freeze the source before creating any new-session card.
        Its validator reads the current target task and original publication/CAS
        and parameter snapshot through this transaction's connection. Only after
        bank retirement and seal may it publish a separate, freshly gated attempt.
        """
        if context.operation_id is None or context.action_revision is None:
            raise SecurityStateError("INPUT_REQUIRED")
        if (context.confirmation_id is not None or context.confirmation_version is not None
                or source_session_id == context.session_id):
            raise SecurityStateError("INPUT_REQUIRED")
        if action.action_name not in {
            "bank.freeze_funds", "bank.create_order", "bank.capture_frozen",
        } or action.phase is not Phase.EXECUTION:
            raise SecurityStateError("POLICY_VIOLATION")
        with transaction(self.path) as connection:
            row = connection.execute(
                "SELECT confirmation_json AS record_json FROM security_confirmations "
                "WHERE confirmation_id = ?", (source_confirmation_id,),
            ).fetchone()
            source = ConfirmationRecord.model_validate_json(row["record_json"]) if row else None
            if source is None or source.confirmation_version != source_confirmation_version:
                row = connection.execute(
                    "SELECT record_json FROM security_confirmation_history "
                    "WHERE confirmation_id = ? AND version = ?",
                    (source_confirmation_id, source_confirmation_version),
                ).fetchone()
                source = ConfirmationRecord.model_validate_json(row["record_json"]) if row else None
            if source is None:
                raise SecurityStateError("CONFIRMATION_STALE")
            if (source.user_id, source.demo_round_id, source.task_id, source.session_id) != (
                context.user_id, context.demo_round_id, context.task_id, source_session_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            if (source.operation_id, source.action_revision, source.action_name, source.parameters_ref) != (
                context.operation_id, context.action_revision, action.action_name, action.parameters_ref,
            ):
                raise SecurityStateError("OPERATION_CONFLICT")
            if source.decision == "cancelled":
                raise SecurityStateError("TASK_TERMINATED")
            source_context = context.model_copy(update={
                "session_id": source_session_id, "confirmation_id": source.confirmation_id,
                "confirmation_version": source.confirmation_version,
            })
            binding = {**self._retirement_binding(source_context, action),
                       "recovery_target_session_id": context.session_id}
            release = connection.execute(
                "SELECT authorization_json FROM security_release_authorizations "
                "WHERE task_id = ? AND freeze_operation_id = ?",
                (context.task_id, str(context.operation_id)),
            ).fetchone()
            if release is not None and FreezeReleaseAuthorization.model_validate_json(
                    release["authorization_json"]).status in {"active", "completed"}:
                raise SecurityStateError("OPERATION_UNKNOWN")
            self._ensure_session_recovery(connection, context, binding, recovery_validator)
            return self._accept_retirement(connection, context, binding, now)

    @staticmethod
    def _ensure_session_recovery(connection, context, binding, validator: RecoveryValidator) -> None:
        if context.operation_id is None or context.action_revision is None:
            raise SecurityStateError("INPUT_REQUIRED")
        if context.confirmation_id is not None or context.confirmation_version is not None:
            raise SecurityStateError("INPUT_REQUIRED")
        if binding.get("recovery_target_session_id") != context.session_id:
            raise SecurityStateError("ACCESS_DENIED")
        if connection.execute("SELECT 1 FROM security_terminated_tasks WHERE task_id = ?",
                              (context.task_id,)).fetchone() is not None:
            raise SecurityStateError("TASK_TERMINATED")
        proof_binding = {
            **binding, "user_id": context.user_id, "demo_round_id": context.demo_round_id,
            "task_id": context.task_id, "operation_id": str(context.operation_id),
            "action_revision": context.action_revision,
        }
        try:
            valid = validator(connection, context, proof_binding)
        except Exception as exc:
            raise SecurityStateError("DEPENDENCY_UNAVAILABLE") from exc
        if not isinstance(valid, bool):
            raise SecurityStateError("DEPENDENCY_UNAVAILABLE")
        if not valid:
            raise SecurityStateError("RETIREMENT_STALE")

    def _accept_retirement(self, connection, context, binding, now) -> RetirementRecord:
        binding_key = self._binding_key(binding)
        claim = connection.execute(
            "SELECT * FROM security_executions WHERE operation_id = ?",
            (str(context.operation_id),),
        ).fetchone()
        if claim is not None:
            if (claim["user_id"], claim["demo_round_id"], claim["task_id"]) != (
                context.user_id, context.demo_round_id, context.task_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            raise SecurityStateError("OPERATION_UNKNOWN")
        row = connection.execute(
            "SELECT * FROM security_retirements WHERE operation_id = ?",
            (str(context.operation_id),),
        ).fetchone()
        if row is not None:
            record = self._retirement(row)
            if (record.user_id, record.demo_round_id, record.task_id) != (
                context.user_id, context.demo_round_id, context.task_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            if record.action_revision != context.action_revision or record.state == "conflict":
                raise SecurityStateError("OPERATION_CONFLICT")
            if self._binding_key(record.original_binding) != binding_key:
                raise SecurityStateError("OPERATION_CONFLICT")
            if record.original_binding.get("recovery_target_session_id") or binding.get("recovery_target_session_id"):
                if (record.original_binding.get("recovery_target_session_id"),
                    record.original_binding.get("session_id")) != (
                        binding.get("recovery_target_session_id"), binding.get("session_id")):
                    raise SecurityStateError("OPERATION_CONFLICT")
            return record
        record = RetirementRecord(
            retirement_id=str(uuid4()), user_id=context.user_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id,
            operation_id=context.operation_id, action_revision=context.action_revision,
            state="pending_proof", original_binding=binding, bank_evidence=None,
            audit_ref=None, created_at=now, sealed_at=None,
        )
        connection.execute(
            """INSERT INTO security_retirements
               (retirement_id, user_id, demo_round_id, task_id, operation_id,
                action_revision, state, original_binding_json,
                bank_evidence_json, audit_ref, created_at, sealed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)""",
            (record.retirement_id, record.user_id, record.demo_round_id, record.task_id,
             str(record.operation_id), record.action_revision, record.state,
             _canonical(binding), now.isoformat()),
        )
        return record

    def seal_retirement(
        self,
        context: ExecutionSecurityContext,
        retirement_id: str,
        bank_evidence: object,
        now: datetime,
        *,
        audit_writer: Callable[..., object],
        task_state_resolver: Callable[[ExecutionSecurityContext], bool],
    ) -> RetirementRecord:
        """Seal the accepted attempt with the bank's retirement fact and one audit event.

        ``bank_evidence`` is the ticket-06 bank retirement fact (a
        ``VerificationRetirement`` or its JSON dump). The audit event reuses the
        frozen ``security.decided`` shell because the Literal event enum has no
        ``security.retired_unsubmitted``; the synthetic decision is BLOCK with
        reason RETIRED_UNSUBMITTED and the real binding/bank evidence snapshot.
        """
        return self._seal_retirement(context, retirement_id, bank_evidence, now,
                                     audit_writer=audit_writer, task_state_resolver=task_state_resolver)

    def seal_session_retirement(
        self, context: ExecutionSecurityContext, retirement_id: str,
        bank_evidence: object, now: datetime, *, audit_writer: Callable[..., object],
        recovery_validator: RecoveryValidator,
    ) -> RetirementRecord:
        """Seal only for the recorded target session and freshly revalidated source."""
        return self._seal_retirement(context, retirement_id, bank_evidence, now,
                                     audit_writer=audit_writer, recovery_validator=recovery_validator)

    def _seal_retirement(
        self, context, retirement_id, bank_evidence, now, *, audit_writer,
        task_state_resolver=None, recovery_validator=None,
    ) -> RetirementRecord:
        evidence = self._normalise_bank_evidence(bank_evidence)
        with transaction(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM security_retirements WHERE retirement_id = ?",
                (retirement_id,),
            ).fetchone()
            if row is None:
                raise SecurityStateError("RETIREMENT_STALE")
            record = self._retirement(row)
            if (record.user_id, record.demo_round_id, record.task_id) != (
                context.user_id, context.demo_round_id, context.task_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            self._check_retirement_context(record, context, session_recovery=recovery_validator is not None)
            if recovery_validator is not None:
                self._ensure_session_recovery(connection, context, record.original_binding, recovery_validator)
            else:
                self._ensure_task_open(connection, context, task_state_resolver)
            if record.state == "sealed":
                if _canonical(record.bank_evidence) != _canonical(evidence):
                    raise SecurityStateError("OPERATION_CONFLICT")
                return record
            if record.state == "conflict":
                raise SecurityStateError("OPERATION_CONFLICT")
            self._check_evidence_attempt(record, evidence)
            claim = connection.execute(
                "SELECT 1 FROM security_executions WHERE operation_id = ?",
                (str(record.operation_id),),
            ).fetchone()
            if claim is not None:
                connection.execute(
                    """UPDATE security_retirements
                       SET state = 'conflict', bank_evidence_json = ?
                       WHERE retirement_id = ?""",
                    (_canonical(evidence), retirement_id),
                )
            else:
                retired_authorization = self._retire_pending_release_authorization(
                    connection, record,
                )
                event, evidence_snapshot = self._retirement_audit_event(
                    context, record, evidence, retired_authorization, now,
                )
                event = event.model_copy(update={
                    "sequence": self._next_audit_sequence(connection, event),
                })
                try:
                    saved = audit_writer(
                        connection, event,
                        evidence=evidence_snapshot,
                        snapshots=self._retirement_evidence_snapshots(
                            connection, context, record,
                        ),
                    )
                except Exception as exc:
                    raise SecurityStateError("AUDIT_UNAVAILABLE") from exc
                audit_ref = getattr(saved, "event_id", None)
                if not isinstance(audit_ref, str) or not audit_ref:
                    raise SecurityStateError("AUDIT_UNAVAILABLE")
                connection.execute(
                    """UPDATE security_retirements
                       SET state = 'sealed', bank_evidence_json = ?,
                           audit_ref = ?, sealed_at = ?
                       WHERE retirement_id = ?""",
                    (_canonical(evidence), audit_ref, now.isoformat(), retirement_id),
                )
                sealed = connection.execute(
                    "SELECT * FROM security_retirements WHERE retirement_id = ?",
                    (retirement_id,),
                ).fetchone()
                return self._retirement(sealed)
        # Only the recorded-conflict path leaves the transaction without returning:
        # a claim appeared, so the original operation must be observed from now on.
        raise SecurityStateError("OPERATION_UNKNOWN")

    def get_retirement(
        self,
        context: ExecutionSecurityContext,
        task_id: str,
        operation_id: UUID,
        action_revision: int,
    ) -> RetirementRecord | None:
        """Read-only recovery by the original task/attempt; never an edit right by itself."""
        if context.task_id != task_id:
            raise SecurityStateError("ACCESS_DENIED")
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT * FROM security_retirements
                   WHERE user_id = ? AND demo_round_id = ? AND task_id = ?
                     AND operation_id = ? AND action_revision = ?""",
                (
                    context.user_id, context.demo_round_id, task_id,
                    str(operation_id), action_revision,
                ),
            ).fetchone()
            if row is not None:
                return self._retirement(row)
            foreign = connection.execute(
                """SELECT 1 FROM security_retirements
                   WHERE operation_id = ? AND action_revision = ?""",
                (str(operation_id), action_revision),
            ).fetchone()
            if foreign is not None:
                raise SecurityStateError("ACCESS_DENIED")
            return None
        finally:
            connection.close()

    @staticmethod
    def _check_retirement_context(
        record: RetirementRecord, context: ExecutionSecurityContext,
        *, session_recovery: bool = False,
    ) -> None:
        if (context.operation_id is not None
                and str(context.operation_id) != str(record.operation_id)):
            raise SecurityStateError("OPERATION_CONFLICT")
        if (context.action_revision is not None
                and context.action_revision != record.action_revision):
            raise SecurityStateError("OPERATION_CONFLICT")
        binding = record.original_binding
        if (context.confirmation_id is not None
                and context.confirmation_id != binding.get("confirmation_id")):
            raise SecurityStateError("OPERATION_CONFLICT")
        if (context.confirmation_version is not None
                and context.confirmation_version != binding.get("confirmation_version")):
            raise SecurityStateError("OPERATION_CONFLICT")
        if session_recovery:
            if context.session_id != binding.get("recovery_target_session_id"):
                raise SecurityStateError("ACCESS_DENIED")
        elif binding.get("recovery_target_session_id") is not None or context.session_id != binding.get("session_id"):
            # The old action's session is part of its binding (same rule as
            # _check_owner); a stale/foreign session must not seal edit evidence.
            raise SecurityStateError("ACCESS_DENIED")

    @staticmethod
    def _normalise_bank_evidence(bank_evidence: object) -> dict[str, object]:
        if isinstance(bank_evidence, dict):
            evidence = dict(bank_evidence)
        elif callable(getattr(bank_evidence, "model_dump", None)):
            evidence = bank_evidence.model_dump(mode="json")
        else:
            raise SecurityStateError("INPUT_REQUIRED")
        required = {
            "retirement_id", "operation_id", "action_revision",
            "retired_challenge_ids", "retired_at",
        }
        if not required <= set(evidence):
            raise SecurityStateError("INPUT_REQUIRED")
        if not isinstance(evidence["retirement_id"], str) or not evidence["retirement_id"]:
            raise SecurityStateError("INPUT_REQUIRED")
        return evidence

    @staticmethod
    def _check_evidence_attempt(
        record: RetirementRecord, evidence: dict[str, object],
    ) -> None:
        try:
            operation_id = str(evidence["operation_id"])
            action_revision = int(evidence["action_revision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SecurityStateError("INPUT_REQUIRED") from exc
        if (operation_id != str(record.operation_id)
                or action_revision != record.action_revision):
            raise SecurityStateError("OPERATION_CONFLICT")

    @staticmethod
    def _retire_pending_release_authorization(
        connection, record: RetirementRecord,
    ) -> FreezeReleaseAuthorization | None:
        row = connection.execute(
            """SELECT * FROM security_release_authorizations
               WHERE task_id = ? AND freeze_operation_id = ?""",
            (record.task_id, str(record.operation_id)),
        ).fetchone()
        if row is None:
            return None
        authorization = FreezeReleaseAuthorization.model_validate_json(
            row["authorization_json"],
        )
        if (authorization.user_id, authorization.demo_round_id,
                authorization.task_id) != (
            record.user_id, record.demo_round_id, record.task_id,
        ):
            raise SecurityStateError("ACCESS_DENIED")
        if authorization.status == "active":
            # A real freeze under this attempt contradicts "unsubmitted".
            raise SecurityStateError("OPERATION_CONFLICT")
        if authorization.status != "pending_freeze":
            return None
        binding = record.original_binding
        if binding.get("recovery_target_session_id") is not None and (
            authorization.session_id != binding.get("session_id")
            or authorization.action_revision not in (None, record.action_revision)
        ):
            raise SecurityStateError("OPERATION_CONFLICT")
        if binding.get("confirmation_id") is not None and (
            authorization.confirmation_id != binding.get("confirmation_id")
            or authorization.confirmation_version
            != binding.get("confirmation_version")
        ):
            raise SecurityStateError("OPERATION_CONFLICT")
        updated = authorization.model_copy(update={
            "status": "invalid", "invalid_reason": "RETIRED_UNSUBMITTED",
        })
        connection.execute(
            """UPDATE security_release_authorizations SET authorization_json = ?
               WHERE release_authorization_id = ?""",
            (updated.model_dump_json(), updated.release_authorization_id),
        )
        return updated

    @staticmethod
    def _next_audit_sequence(connection, event: AuditEvent) -> int:
        highest = connection.execute(
            "SELECT MAX(sequence) FROM audit_events WHERE run_key = ?",
            (run_key(event),),
        ).fetchone()[0]
        return 0 if highest is None else highest + 1

    @staticmethod
    def _retirement_evidence_snapshots(
        connection, context: ExecutionSecurityContext, record: RetirementRecord,
    ) -> dict[str, object]:
        """The action parameters snapshot unless an earlier decision already stored it.

        audit_evidence.evidence_id is global, so writing a second snapshot for the
        same parameters_ref would abort the sealing transaction.
        """
        parameters_ref = record.original_binding["parameters_ref"]
        stored = connection.execute(
            """SELECT 1 FROM audit_evidence
               WHERE evidence_id = ? AND demo_round_id = ? AND task_id IS ?""",
            (parameters_ref, context.demo_round_id, context.task_id),
        ).fetchone()
        return {} if stored is not None else {parameters_ref: record.original_binding}

    @staticmethod
    def _retirement_audit_event(
        context: ExecutionSecurityContext,
        record: RetirementRecord,
        evidence: dict[str, object],
        authorization: FreezeReleaseAuthorization | None,
        now: datetime,
    ) -> tuple[AuditEvent, dict[str, object]]:
        # The retirement seam currently only serves birthday funds writes, which
        # the frozen birthday declarations all declare SENSITIVE. A caller trying
        # to retire a lower-level action must first carry its real level into the
        # binding; do not widen this synthetic audit decision silently.
        binding = record.original_binding
        evidence_ref = f"retirement:{record.retirement_id}"
        decision = SecurityDecision(
            decision_id=str(uuid4()), task_id=record.task_id,
            run_id=context.run_id, action_name=binding["action_name"],
            parameters_ref=binding["parameters_ref"],
            operation_id=record.operation_id,
            action_revision=record.action_revision,
            phase=Phase(binding["phase"]),
            operation_level=OperationLevel.SENSITIVE, risk_level=None,
            decision=SecurityDecisionCode.BLOCK,
            reason_codes=["RETIRED_UNSUBMITTED"],
            rule_ids=["retirement-before-bank-submit"],
            policy_version=(SESSION_RETIREMENT_POLICY_VERSION
                            if binding.get("recovery_target_session_id") else RETIREMENT_POLICY_VERSION),
            authorization_snapshot_ref=None, evidence_refs=[], interaction=None,
            checked_at=now,
            message="旧动作在提交银行前已安全撤离，未产生提交。",
        )
        event = AuditEvent(
            event_id=str(uuid4()), trace_id=str(uuid4()), span_id=str(uuid4()),
            sequence=0, parent_span_id=None,
            demo_round_id=context.demo_round_id, actor_id=context.user_id,
            session_id=context.session_id, target_session_id=context.session_id,
            target_user_id=context.user_id, thread_id=None,
            task_id=context.task_id, run_id=context.run_id, module="security",
            event_type="security.decided", timestamp=now, logical_at=None,
            outcome="denied", evidence_ref=evidence_ref,
            evidence_status="available", missing_reason=None,
            payload=SecurityDecidedPayload(
                decision=decision,
                release_authorization_id=(
                    authorization.release_authorization_id
                    if authorization is not None else None
                ),
            ),
        )
        snapshot = {
            "retirement_id": record.retirement_id,
            "user_id": record.user_id,
            "demo_round_id": record.demo_round_id,
            "task_id": record.task_id,
            "operation_id": str(record.operation_id),
            "action_revision": record.action_revision,
            "original_binding": binding,
            "bank_evidence": evidence,
            "captured_at": now.isoformat(),
            "release_authorization_id": (
                authorization.release_authorization_id
                if authorization is not None else None
            ),
        }
        return event, snapshot

    # --- limited-release authorizations and controlled release claims ---

    def store_release_authorization(
        self, record: FreezeReleaseAuthorization,
    ) -> FreezeReleaseAuthorization:
        with transaction(self.path) as connection:
            sealed_query = (
                "SELECT 1 FROM security_retirements"
                " WHERE user_id = ? AND demo_round_id = ? AND task_id = ?"
                " AND operation_id = ? AND state = 'sealed'"
            )
            sealed_parameters: list[object] = [
                record.user_id, record.demo_round_id, record.task_id,
                str(record.freeze_operation_id),
            ]
            if record.action_revision is not None:
                # Same attempt key as claim_execution: a sealed retirement of
                # another revision must not block a later attempt.
                sealed_query += " AND action_revision = ?"
                sealed_parameters.append(record.action_revision)
            sealed = connection.execute(sealed_query, sealed_parameters).fetchone()
            if sealed is not None:
                # A late grant callback must not recreate authority for a sealed attempt.
                raise SecurityStateError("ACTION_RETIRED")
            row = connection.execute(
                """SELECT * FROM security_release_authorizations
                   WHERE task_id = ? AND freeze_operation_id = ?""",
                (record.task_id, str(record.freeze_operation_id)),
            ).fetchone()
            if row is not None:
                stored = FreezeReleaseAuthorization.model_validate_json(
                    row["authorization_json"],
                )
                identity = (
                    stored.user_id, stored.session_id, stored.demo_round_id,
                    stored.task_id, stored.account_id,
                    str(stored.freeze_operation_id), stored.confirmation_id,
                    stored.confirmation_version, stored.max_amount_fen,
                )
                granted = (
                    record.user_id, record.session_id, record.demo_round_id,
                    record.task_id, record.account_id,
                    str(record.freeze_operation_id), record.confirmation_id,
                    record.confirmation_version, record.max_amount_fen,
                )
                if identity == granted and stored.status == record.status:
                    return stored
                raise SecurityStateError("OPERATION_CONFLICT")
            connection.execute(
                "INSERT INTO security_release_authorizations VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.release_authorization_id, record.user_id,
                    record.demo_round_id, record.task_id,
                    str(record.freeze_operation_id), record.model_dump_json(),
                ),
            )
            return record

    def get_release_authorization(
        self,
        context: ExecutionSecurityContext,
        release_authorization_id: str,
    ) -> FreezeReleaseAuthorization | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT * FROM security_release_authorizations
                   WHERE release_authorization_id = ?""",
                (release_authorization_id,),
            ).fetchone()
            if row is None:
                return None
            record = FreezeReleaseAuthorization.model_validate_json(
                row["authorization_json"],
            )
            if (record.user_id, record.demo_round_id, record.task_id) != (
                context.user_id, context.demo_round_id, context.task_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            return record
        finally:
            connection.close()

    def update_release_authorization(
        self,
        context: ExecutionSecurityContext,
        record: FreezeReleaseAuthorization,
    ) -> FreezeReleaseAuthorization:
        with transaction(self.path) as connection:
            row = connection.execute(
                """SELECT * FROM security_release_authorizations
                   WHERE release_authorization_id = ?""",
                (record.release_authorization_id,),
            ).fetchone()
            if row is None:
                raise SecurityStateError("OPERATION_UNKNOWN")
            current = FreezeReleaseAuthorization.model_validate_json(
                row["authorization_json"],
            )
            if (current.user_id, current.demo_round_id, current.task_id) != (
                context.user_id, context.demo_round_id, context.task_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            if current == record:
                return current
            immutable = (
                current.release_authorization_id, current.user_id,
                current.session_id, current.demo_round_id, current.task_id,
                current.account_id, current.freeze_operation_id,
                current.confirmation_id, current.confirmation_version,
                current.max_amount_fen, current.granted_at,
            )
            same_identity = (
                record.release_authorization_id, record.user_id,
                record.session_id, record.demo_round_id, record.task_id,
                record.account_id, record.freeze_operation_id,
                record.confirmation_id, record.confirmation_version,
                record.max_amount_fen, record.granted_at,
            )
            if immutable != same_identity:
                raise SecurityStateError("OPERATION_CONFLICT")
            if current.freeze_id is not None and record.freeze_id != current.freeze_id:
                raise SecurityStateError("OPERATION_CONFLICT")
            if (current.status, record.status) not in _RELEASE_TRANSITIONS:
                raise SecurityStateError("OPERATION_CONFLICT")
            if record.status in {"active", "completed"} and record.freeze_id is None:
                raise SecurityStateError("OPERATION_CONFLICT")
            connection.execute(
                """UPDATE security_release_authorizations SET authorization_json = ?
                   WHERE release_authorization_id = ?""",
                (record.model_dump_json(), record.release_authorization_id),
            )
            return record

    def find_execution(self, operation_id: UUID) -> ExecutionClaim | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM security_executions WHERE operation_id = ?",
                (str(operation_id),),
            ).fetchone()
            return None if row is None else self._claim(row)
        finally:
            connection.close()

    def unresolved_executions(
        self,
        context: ExecutionSecurityContext,
    ) -> list[str]:
        connection = connect(self.path)
        try:
            rows = connection.execute(
                """SELECT * FROM security_executions
                   WHERE task_id = ? AND state != 'completed'""",
                (context.task_id,),
            ).fetchall()
        finally:
            connection.close()
        unresolved = []
        for row in rows:
            if (row["user_id"], row["demo_round_id"]) != (
                context.user_id, context.demo_round_id,
            ):
                raise SecurityStateError("ACCESS_DENIED")
            unresolved.append(row["operation_id"])
        return sorted(unresolved)

    def release_claim(
        self,
        context: ExecutionSecurityContext,
        release_authorization_id: str,
    ) -> ExecutionClaim | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT * FROM security_executions
                   WHERE task_id = ? AND action_name = 'bank.release_frozen'
                     AND parameters_ref LIKE ? ORDER BY rowid DESC LIMIT 1""",
                (context.task_id, f"release:{release_authorization_id}:%"),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        if (row["user_id"], row["demo_round_id"]) != (
            context.user_id, context.demo_round_id,
        ):
            raise SecurityStateError("ACCESS_DENIED")
        return self._claim(row)

    def claim_release_execution(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        decision: SecurityDecision,
    ) -> tuple[ExecutionClaim, bool]:
        """Persists the controlled release operation before any bank submit.

        Unlike claim_execution this path carries no new user confirmation: the
        authority is the already-granted limited-release authorization, and the
        caller has verified the task has ended.
        """
        if context.operation_id is None or context.action_revision is None:
            raise SecurityStateError("INPUT_REQUIRED")
        with transaction(self.path) as connection:
            existing = connection.execute(
                "SELECT * FROM security_executions WHERE operation_id = ?",
                (str(context.operation_id),),
            ).fetchone()
            if existing is not None:
                self._validate_execution_row(existing, context, action)
                return self._claim(existing), False
            connection.execute(
                """INSERT INTO security_executions
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'processing', ?, NULL)""",
                (
                    str(context.operation_id), context.user_id,
                    context.demo_round_id, context.task_id,
                    action.action_name, action.parameters_ref,
                    context.action_revision, decision.model_dump_json(),
                ),
            )
            created = connection.execute(
                "SELECT * FROM security_executions WHERE operation_id = ?",
                (str(context.operation_id),),
            ).fetchone()
            return self._claim(created), True
