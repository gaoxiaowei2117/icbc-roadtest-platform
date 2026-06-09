"""ICBC 凭据的非对称封装加密（libsodium SealedBox：X25519 + XSalsa20-Poly1305）。

设计（兑现 architecture.md A1）：
  - 后端只持【公钥】SECRET_PUBLIC_KEY，只能加密、**无法解密**。
  - 密文存库；解密只发生在本地 worker（持私钥 SECRET_PRIVATE_KEY）。
  - 即便 VPS 整机沦陷，攻击者拿到的也只是无法解密的密文。

SealedBox 是匿名加密：发送方无需自己的密钥，用接收方公钥加密，
只有持对应私钥者能解。这正好契合"云端加密、本地解密"的信任边界。
"""
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox

from app.core.config import get_settings

settings = get_settings()

_GEN_HINT = (
    "生成密钥对：python -c \""
    "from nacl.public import PrivateKey; from nacl.encoding import Base64Encoder; "
    "sk=PrivateKey.generate(); "
    "print('SECRET_PRIVATE_KEY=', sk.encode(Base64Encoder).decode()); "
    "print('SECRET_PUBLIC_KEY=', sk.public_key.encode(Base64Encoder).decode())\""
)


def _build_box() -> SealedBox:
    if not settings.secret_public_key:
        raise ValueError(f"SECRET_PUBLIC_KEY 未配置：请在 .env 里设置 base64 公钥。{_GEN_HINT}")
    try:
        pk = PublicKey(settings.secret_public_key.encode(), encoder=Base64Encoder)
    except Exception as e:  # noqa: BLE001 — 任何解析失败都归一为配置错误
        raise ValueError(f"SECRET_PUBLIC_KEY 格式错误：{e}。{_GEN_HINT}") from e
    return SealedBox(pk)


def encrypt_secret(plaintext: str) -> bytes:
    """用公钥加密，返回密文 bytes（存入 secret.ciphertext）。后端无解密能力。"""
    return _build_box().encrypt(plaintext.encode())
