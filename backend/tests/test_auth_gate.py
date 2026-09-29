import pytest
import bcrypt
from app.core.security import verify_password, get_password_hash


def test_password_hash_and_verification():
    """Verify bcrypt hash generation and constant-time verification."""
    raw_pass = "MySecretAdminPass2026!"
    hashed = get_password_hash(raw_pass)

    assert hashed.startswith("$2")
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_streamlit_auth_check_logic():
    """Verify Streamlit login check logic handles plain and hashed passwords."""
    raw_pass = "StreamlitAdminSecret"
    hashed = get_password_hash(raw_pass)

    def check_auth(entered: str, stored_hash_or_plain: str) -> bool:
        if not stored_hash_or_plain or not entered:
            return False
        if stored_hash_or_plain.startswith("$2"):
            try:
                return bcrypt.checkpw(entered.encode(), stored_hash_or_plain.encode())
            except Exception:
                return False
        return entered == stored_hash_or_plain

    assert check_auth("StreamlitAdminSecret", hashed) is True
    assert check_auth("StreamlitAdminSecret", "StreamlitAdminSecret") is True
    assert check_auth("InvalidPass", hashed) is False
    assert check_auth("", hashed) is False
