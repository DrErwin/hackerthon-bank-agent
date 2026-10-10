"""Bank-owned demo identity facts; codes never enter ordinary bank responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Literal
from uuid import UUID, uuid4

from app.contracts.common import ContractModel
from app.contracts.platform import TrustedContext
from app.contracts.security import VerificationChallenge, VerificationRecord, VerificationSummary
from app.storage.database import parameter_digest, transaction


BEIJING = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(BEIJING)


@dataclass(frozen=True)
class AdminContext:
    actor_id: str
    authorized: bool
    demo_round_id: str
    target_user_id: str


class VerificationOutcome(ContractModel):
    kind: Literal["verified", "rejected", "error"]
    challenge: VerificationChallenge
    verification_id: str | None
    reason_code: str | None


class VerificationTerminated(ValueError):
    """Internal bank failure with a typed terminal fact, never a code or raw input."""

    def __init__(self, challenge: VerificationChallenge):
        super().__init__("TASK_TERMINATED")
        self.challenge = challenge


class MockBankVerification:
    def __init__(self, bank_path, demo_secret: bytes, *, clock=_now):
        if len(demo_secret) < 32:
            raise ValueError("demo_secret must contain at least 32 bytes")
        self.path = bank_path
        self._demo_secret = demo_secret
        self.clock = clock
        with transaction(self.path) as connection:
            columns = {row["name"] for row in connection.execute(
                "PRAGMA table_info(bank_verification_challenges)",
            )}
            if "demo_code" in columns:
                raise RuntimeError(
                    "legacy demo codes were stored in the bank database; retain the old "
                    "database for reference and start a fresh demo bank database explicitly"
                )
            connection.execute("""CREATE TABLE IF NOT EXISTS bank_verification_challenges (
                challenge_id TEXT PRIMARY KEY,
                challenge_json TEXT NOT NULL
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS bank_verification_submissions (
                submission_id TEXT PRIMARY KEY,
                challenge_id TEXT NOT NULL,
                method TEXT NOT NULL,
                input_digest TEXT NOT NULL,
                response_json TEXT NOT NULL
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS bank_verification_records (
                verification_id TEXT PRIMARY KEY,
                challenge_id TEXT NOT NULL UNIQUE,
                record_json TEXT NOT NULL
            )""")

    def _code(self, challenge_id: str) -> str:
        value = hmac.digest(self._demo_secret, f"code:{challenge_id}".encode(), "sha256")
        return f"{int.from_bytes(value, 'big') % 900000 + 100000:06d}"

    def _submission_digest(self, challenge_id: str, code: str) -> str:
        return hmac.new(
            self._demo_secret, f"submission:{challenge_id}:{code}".encode(), hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _save(connection, challenge: VerificationChallenge) -> None:
        connection.execute(
            "UPDATE bank_verification_challenges SET challenge_json = ? WHERE challenge_id = ?",
            (challenge.model_dump_json(), challenge.challenge_id),
        )

    @staticmethod
    def _load(connection, challenge_id: str) -> VerificationChallenge | None:
        row = connection.execute(
            "SELECT challenge_json FROM bank_verification_challenges WHERE challenge_id = ?",
            (challenge_id,),
        ).fetchone()
        return VerificationChallenge.model_validate_json(row["challenge_json"]) if row else None

    @staticmethod
    def _in_scope(challenge: VerificationChallenge, context: TrustedContext) -> bool:
        return (
            challenge.user_id, challenge.session_id, challenge.task_id, challenge.demo_round_id
        ) == (context.user_id, context.session_id, context.task_id, context.demo_round_id)

    def _expire(self, connection, challenge: VerificationChallenge) -> VerificationChallenge:
        if challenge.challenge_status != "pending":
            return challenge
        at = self.clock()
        code_expired = challenge.code_result == "pending" and at >= challenge.code_expires_at
        face_expired = (challenge.face_result == "pending" and
                        challenge.face_expires_at is not None and at >= challenge.face_expires_at)
        if code_expired or face_expired:
            challenge.challenge_status = "expired"
            if code_expired:
                challenge.code_result = "expired"
            if face_expired:
                challenge.face_result = "expired"
            self._save(connection, challenge)
        return challenge

    def create_verification(
        self, context: TrustedContext, purpose: Literal["basic_identity", "action_step_up"],
        operation_id: UUID | None = None, action_revision: int | None = None,
        summary: VerificationSummary | None = None,
    ) -> VerificationChallenge:
        with transaction(self.path) as connection:
            rows = connection.execute(
                "SELECT challenge_json FROM bank_verification_challenges ORDER BY rowid",
            ).fetchall()
            previous_failures = 0
            for row in rows:
                old = self._expire(connection, VerificationChallenge.model_validate_json(row["challenge_json"]))
                same_task = (old.user_id, old.task_id, old.demo_round_id) == (
                    context.user_id, context.task_id, context.demo_round_id,
                )
                if same_task and old.purpose == "basic_identity":
                    previous_failures = (
                        0 if old.challenge_status == "passed" else old.consecutive_code_failures
                    )
                if same_task and (old.challenge_status == "failed" or
                        (old.purpose == "action_step_up" and old.challenge_status == "expired")):
                    raise VerificationTerminated(old)
                if (old.user_id, old.session_id, old.task_id, old.demo_round_id, old.purpose,
                    old.operation_id, old.action_revision) == (
                    context.user_id, context.session_id, context.task_id, context.demo_round_id,
                    purpose, operation_id, action_revision,
                ) and old.challenge_status == "pending":
                    if old.summary != summary:
                        raise ValueError("VERIFICATION_SCOPE_MISMATCH")
                    return old
            now = self.clock()
            challenge = VerificationChallenge(
                challenge_id=str(uuid4()), user_id=context.user_id,
                session_id=context.session_id, demo_round_id=context.demo_round_id,
                task_id=context.task_id, purpose=purpose, operation_id=operation_id,
                action_revision=action_revision, summary=summary,
                required_methods=["code"] if purpose == "basic_identity" else ["code", "mock_face"],
                created_at=now, code_created_at=now, code_expires_at=now + timedelta(minutes=5),
                face_started_at=None, face_expires_at=None, challenge_status="pending",
                code_result="pending", face_result="not_required" if purpose == "basic_identity" else "pending",
                consecutive_code_failures=previous_failures if purpose == "basic_identity" else 0,
            )
            connection.execute(
                "INSERT INTO bank_verification_challenges VALUES (?, ?)",
                (challenge.challenge_id, challenge.model_dump_json()),
            )
            return challenge

    def get_verification(self, context: TrustedContext, challenge_id: str) -> VerificationChallenge:
        with transaction(self.path) as connection:
            challenge = self._load(connection, challenge_id)
            if challenge is None or not self._in_scope(challenge, context):
                raise ValueError("ACCESS_DENIED")
            return self._expire(connection, challenge)

    def get_demo_code(self, context: TrustedContext, challenge_id: str) -> str:
        """For the dedicated demo-code API only; never register as an Agent tool."""
        with transaction(self.path) as connection:
            challenge = self._load(connection, challenge_id)
            if challenge is None or not self._in_scope(challenge, context):
                raise ValueError("ACCESS_DENIED")
            challenge = self._expire(connection, challenge)
            if challenge.challenge_status != "pending":
                raise ValueError("CHALLENGE_EXPIRED")
            return self._code(challenge_id)

    def resend_code(self, context: TrustedContext, challenge_id: str,
                    submission_id: UUID) -> VerificationChallenge:
        with transaction(self.path) as connection:
            old = self._load(connection, challenge_id)
            if old is None or not self._in_scope(old, context):
                raise ValueError("ACCESS_DENIED")
            previous = connection.execute(
                "SELECT * FROM bank_verification_submissions WHERE submission_id = ?",
                (str(submission_id),),
            ).fetchone()
            digest = parameter_digest({"challenge_id": challenge_id})
            if previous is not None:
                if (previous["challenge_id"], previous["method"], previous["input_digest"]) != (
                    challenge_id, "resend", digest,
                ):
                    raise ValueError("VERIFICATION_SUBMISSION_CONFLICT")
                return VerificationChallenge.model_validate_json(previous["response_json"])
            old = self._expire(connection, old)
            basic_expired = (
                old.purpose == "basic_identity" and old.challenge_status == "expired"
                and old.code_result == "expired" and old.consecutive_code_failures < 3
            )
            if not basic_expired and (old.challenge_status != "pending" or old.code_result != "pending"):
                raise ValueError("TASK_TERMINATED")
            now = self.clock()
            new = old.model_copy(deep=True)
            new.challenge_id = str(uuid4())
            while self._code(new.challenge_id) == self._code(old.challenge_id):
                new.challenge_id = str(uuid4())
            new.created_at = now
            new.code_created_at = now
            new.challenge_status = "pending"
            new.code_result = "pending"
            new.code_expires_at = (
                old.code_expires_at if old.purpose == "action_step_up" else now + timedelta(minutes=5)
            )
            old.challenge_status = "superseded"
            self._save(connection, old)
            connection.execute(
                "INSERT INTO bank_verification_challenges VALUES (?, ?)",
                (new.challenge_id, new.model_dump_json()),
            )
            connection.execute(
                "INSERT INTO bank_verification_submissions VALUES (?, ?, ?, ?, ?)",
                (str(submission_id), challenge_id, "resend", digest, new.model_dump_json()),
            )
            return new

    @staticmethod
    def _previous_submission(connection, submission_id: UUID, challenge_id: str,
                             method: str, input_digest: str) -> VerificationOutcome | None:
        row = connection.execute(
            "SELECT * FROM bank_verification_submissions WHERE submission_id = ?",
            (str(submission_id),),
        ).fetchone()
        if row is None:
            return None
        if (row["challenge_id"], row["method"], row["input_digest"]) != (
            challenge_id, method, input_digest,
        ):
            raise ValueError("VERIFICATION_SUBMISSION_CONFLICT")
        return VerificationOutcome.model_validate_json(row["response_json"])

    @staticmethod
    def _save_submission(connection, submission_id: UUID, challenge_id: str,
                         method: str, input_digest: str, outcome: VerificationOutcome) -> None:
        connection.execute(
            "INSERT INTO bank_verification_submissions VALUES (?, ?, ?, ?, ?)",
            (str(submission_id), challenge_id, method, input_digest, outcome.model_dump_json()),
        )

    def _complete(self, connection, challenge: VerificationChallenge) -> str:
        challenge.challenge_status = "passed"
        self._save(connection, challenge)
        record = VerificationRecord(
            verification_id=str(uuid4()), user_id=challenge.user_id,
            session_id=challenge.session_id, demo_round_id=challenge.demo_round_id,
            scope="session" if challenge.purpose == "basic_identity" else "action",
            operation_id=challenge.operation_id, action_revision=challenge.action_revision,
            methods=challenge.required_methods, verified_at=self.clock(),
            source_challenge_id=challenge.challenge_id,
        )
        connection.execute(
            "INSERT INTO bank_verification_records VALUES (?, ?, ?)",
            (record.verification_id, challenge.challenge_id, record.model_dump_json()),
        )
        return record.verification_id

    def verify_code(self, context: TrustedContext, challenge_id: str,
                    submission_id: UUID, code: str) -> VerificationOutcome:
        digest = self._submission_digest(challenge_id, code)
        with transaction(self.path) as connection:
            challenge = self._load(connection, challenge_id)
            if challenge is None or not self._in_scope(challenge, context):
                raise ValueError("ACCESS_DENIED")
            previous = self._previous_submission(connection, submission_id, challenge_id, "code", digest)
            if previous is not None:
                return previous
            challenge = self._expire(connection, challenge)
            if challenge.challenge_status != "pending" or challenge.code_result != "pending":
                raise ValueError("TASK_TERMINATED")
            if secrets.compare_digest(code, self._code(challenge_id)):
                challenge.code_result = "passed"
                verification_id = self._complete(connection, challenge) if (
                    challenge.face_result in {"passed", "not_required"}
                ) else None
                if verification_id is None:
                    self._save(connection, challenge)
                outcome = VerificationOutcome(
                    kind="verified", challenge=challenge,
                    verification_id=verification_id, reason_code=None,
                )
            else:
                challenge.consecutive_code_failures += 1
                terminal = challenge.purpose == "action_step_up" or challenge.consecutive_code_failures >= 3
                if terminal:
                    challenge.challenge_status = "failed"
                    challenge.code_result = "failed"
                self._save(connection, challenge)
                outcome = VerificationOutcome(
                    kind="rejected", challenge=challenge, verification_id=None,
                    reason_code="VERIFICATION_LIMIT_REACHED" if terminal else "CODE_MISMATCH",
                )
            self._save_submission(connection, submission_id, challenge_id, "code", digest, outcome)
            return outcome

    def start_face(self, context: TrustedContext, challenge_id: str,
                   submission_id: UUID) -> VerificationChallenge:
        with transaction(self.path) as connection:
            challenge = self._load(connection, challenge_id)
            if challenge is None or not self._in_scope(challenge, context):
                raise ValueError("ACCESS_DENIED")
            challenge = self._expire(connection, challenge)
            if challenge.purpose != "action_step_up" or challenge.challenge_status != "pending":
                raise ValueError("TASK_TERMINATED")
            if challenge.face_started_at is None:
                started = self.clock()
                challenge = VerificationChallenge.model_validate(challenge.model_copy(update={
                    "face_started_at": started,
                    "face_expires_at": started + timedelta(minutes=5),
                }).model_dump())
                self._save(connection, challenge)
            return challenge

    def verify_face(self, admin: AdminContext, challenge_id: str,
                    submission_id: UUID, result: Literal["passed", "failed"]) -> VerificationOutcome:
        if result not in {"passed", "failed"}:
            raise ValueError("INVALID_ARGUMENT")
        digest = parameter_digest({"result": result})
        with transaction(self.path) as connection:
            challenge = self._load(connection, challenge_id)
            if (not admin.authorized or challenge is None or
                admin.demo_round_id != challenge.demo_round_id or
                admin.target_user_id != challenge.user_id):
                raise ValueError("ACCESS_DENIED")
            previous = self._previous_submission(connection, submission_id, challenge_id, "face", digest)
            if previous is not None:
                return previous
            challenge = self._expire(connection, challenge)
            if (challenge.purpose != "action_step_up" or challenge.challenge_status != "pending" or
                challenge.face_started_at is None or challenge.face_result != "pending"):
                raise ValueError("TASK_TERMINATED")
            if result == "failed":
                challenge.face_result = "failed"
                challenge.challenge_status = "failed"
                self._save(connection, challenge)
                outcome = VerificationOutcome(
                    kind="rejected", challenge=challenge, verification_id=None,
                    reason_code="VERIFICATION_LIMIT_REACHED",
                )
            else:
                challenge.face_result = "passed"
                verification_id = self._complete(connection, challenge) if challenge.code_result == "passed" else None
                if verification_id is None:
                    self._save(connection, challenge)
                outcome = VerificationOutcome(
                    kind="verified", challenge=challenge,
                    verification_id=verification_id, reason_code=None,
                )
            self._save_submission(connection, submission_id, challenge_id, "face", digest, outcome)
            return outcome

    def get_record(self, context: TrustedContext, verification_id: str) -> VerificationRecord:
        with transaction(self.path) as connection:
            row = connection.execute(
                "SELECT record_json FROM bank_verification_records WHERE verification_id = ?",
                (verification_id,),
            ).fetchone()
            if row is None:
                raise ValueError("ACCESS_DENIED")
            record = VerificationRecord.model_validate_json(row["record_json"])
            if (record.user_id, record.session_id, record.demo_round_id) != (
                context.user_id, context.session_id, context.demo_round_id,
            ):
                raise ValueError("ACCESS_DENIED")
            challenge = self._load(connection, record.source_challenge_id)
            if record.scope == "action" and challenge.task_id != context.task_id:
                raise ValueError("ACCESS_DENIED")
            return record
