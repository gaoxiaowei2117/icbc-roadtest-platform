"""AES（Fernet 封装）加密 ICBC 凭据，主密钥来自 ENCRYPTION_KEY。

Fernet 实例 lazy 构造：只有真正调用 encrypt/decrypt 时才校验密钥，
并把可能的配置错误用清晰的中文报错呈现，避免 import 期神秘崩溃。
"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()


def _build_fernet() -> Fernet:
    if not settings.encryption_key:
        raise ValueError(
            "ENCRYPTION_KEY 未配置：请在 .env 里设置 Fernet 密钥。"
            "生成方式：python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(settings.encryption_key.encode())
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"ENCRYPTION_KEY 格式错误：{e}。"
            "请确认是用 `Fernet.generate_key()` 生成的 32 字节 urlsafe-base64 字符串。"
        ) from e


def encrypt_secret(plaintext: str) -> bytes:
    return _build_fernet().encrypt(plaintext.encode())


def decrypt_secret(ciphertext: bytes) -> str:
    try:
        return _build_fernet().decrypt(ciphertext).decode()
    except InvalidToken as e:
        raise ValueError("凭据解密失败（密钥可能已更换）") from e
