"""AES（Fernet 封装）加密 ICBC 凭据，主密钥来自 ENCRYPTION_KEY。"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()
_fernet = Fernet(settings.encryption_key.encode())


def encrypt_secret(plaintext: str) -> bytes:
    return _fernet.encrypt(plaintext.encode())


def decrypt_secret(ciphertext: bytes) -> str:
    try:
        return _fernet.decrypt(ciphertext).decode()
    except InvalidToken as e:
        raise ValueError("凭据解密失败（密钥可能已更换）") from e
