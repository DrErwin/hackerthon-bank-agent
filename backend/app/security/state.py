"""Persistent, atomic state used by the v0.3 security gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal
from uuid import UUID, uuid4

from app.contracts.common import (
    ContractModel, ID, OperationId, PositiveInt, PositiveMoney, Timestamp,
)
from app.contracts.security import (
    ActionDescriptor,
    ConfirmationRecord,
    ExecutionSecurityContext,
    SecurityDecision,
    VerificationChallenge,
)
from app.storage.database import connect, transaction


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

    # --- limited-release authorizations and controlled release claims ---

    def store_release_authorization(
        self, record: FreezeReleaseAuthorization,
    ) -> FreezeReleaseAuthorization:
        with transaction(self.path) as connection:
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
        *,
        exclude_operation_id: UUID | None = None,
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
            if exclude_operation_id is not None and (
                row["operation_id"] == str(exclude_operation_id)
            ):
                continue
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
                     AND parameters_ref = ? ORDER BY rowid DESC LIMIT 1""",
                (context.task_id, f"release:{release_authorization_id}"),
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
