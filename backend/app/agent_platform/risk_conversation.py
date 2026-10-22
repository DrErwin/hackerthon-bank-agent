"""Task-bound sanitized follow-up evidence; never an authorization record."""

from app.audit.journal import redact
from app.storage.database import connect, transaction


class RiskConversation:
    def __init__(self, path):
        self.path = path
        with transaction(path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS risk_conversation (
                user_id TEXT NOT NULL, demo_round_id TEXT NOT NULL,
                task_id TEXT NOT NULL, session_id TEXT NOT NULL,
                request_id TEXT NOT NULL, text TEXT NOT NULL,
                PRIMARY KEY (user_id, demo_round_id, task_id, request_id))""")

    def append(self, trusted, task_id, request_id, text):
        with transaction(self.path) as connection:
            connection.execute("INSERT OR IGNORE INTO risk_conversation VALUES (?, ?, ?, ?, ?, ?)",
                (trusted.user_id, trusted.demo_round_id, task_id, trusted.session_id,
                 str(request_id), str(redact(text, free_text=True))))

    def texts(self, task):
        connection = connect(self.path)
        try:
            # Prior session evidence survives recovery of this same owned task.
            return [row["text"] for row in connection.execute(
                "SELECT text FROM risk_conversation WHERE user_id=? AND demo_round_id=? AND task_id=? ORDER BY rowid",
                (task.user_id, task.demo_round_id, task.task_id))]
        finally:
            connection.close()
