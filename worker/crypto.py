"""worker 端解密 ICBC 凭据。

持私钥 SECRET_PRIVATE_KEY，用 SealedBox 解开云端下发的密文。
这是整个系统中**唯一**能还原 ICBC 凭据明文的地方（兑现 architecture.md A1）。
"""
import base64

from nacl.encoding import Base64Encoder
from nacl.public import PrivateKey, SealedBox

from config import settings


def decrypt_secret(keyword_ciphertext_b64: str) -> str:
    """解密 claim 下发的 keyword 密文，返回明文 keyword。"""
    if not settings.secret_private_key:
        raise ValueError("SECRET_PRIVATE_KEY 未配置：worker 无法解密凭据")
    sk = PrivateKey(settings.secret_private_key.encode(), encoder=Base64Encoder)
    box = SealedBox(sk)
    return box.decrypt(base64.b64decode(keyword_ciphertext_b64)).decode()
