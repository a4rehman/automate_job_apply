from app.core.logging_config import logger


class SessionManager:
    """
    Manages user login sessions for job platforms.

    Users must log in manually through the browser UI.
    This module only tracks session state — it never intercepts
    or stores platform credentials.
    """

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def register_session(self, platform: str, status: str = "logged_in"):
        self._sessions[platform.lower()] = {"status": status}
        logger.info(f"Session registered for {platform}: {status}")

    def is_logged_in(self, platform: str) -> bool:
        session = self._sessions.get(platform.lower())
        return session is not None and session.get("status") == "logged_in"

    def clear_session(self, platform: str):
        self._sessions.pop(platform.lower(), None)
        logger.info(f"Session cleared for {platform}")

    def list_sessions(self) -> dict[str, dict]:
        return dict(self._sessions)


session_manager = SessionManager()
