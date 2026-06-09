"""加密凭据的数据库操作。后端只加密、**不解密**（解密在本地 worker 端）。"""
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret
from app.models.secret import Secret
from app.models.user import User


def upsert(db: Session, user: User, icbc_username: str, icbc_password: str) -> Secret:
    payload = f"{icbc_username}\n{icbc_password}"
    ciphertext = encrypt_secret(payload)
    if user.secret is None:
        secret = Secret(user_id=user.id, ciphertext=ciphertext)
        db.add(secret)
    else:
        user.secret.ciphertext = ciphertext
        secret = user.secret
    db.commit()
    db.refresh(secret)
    return secret
