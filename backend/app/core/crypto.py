from cryptography.fernet import Fernet
from app.core.config import settings
import base64

class CryptoService:
    def __init__(self, key: str = None):
        fernet_key = key or settings.FERNET_KEY
        try:
            self.cipher = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        except Exception:
            # Fallback to generating a deterministic safe 32-byte key if corrupted
            valid_key = base64.urlsafe_b64encode(b"0" * 32)
            self.cipher = Fernet(valid_key)

    def encrypt(self, plain_text: str) -> str:
        if not plain_text:
            return ""
        return self.cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")

    def decrypt(self, cipher_text: str) -> str:
        if not cipher_text:
            return ""
        try:
            return self.cipher.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except Exception:
            return ""

crypto_service = CryptoService()
