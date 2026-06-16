"""邮件发送（smtplib 同步，复用系统 Gmail SMTP）。"""
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

settings = get_settings()


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_user:
        raise ValueError("SMTP 未配置：请在 .env 设置 SMTP_USER/SMTP_PASSWORD")
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
        s.starttls()
        s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


def send_verification_code(to: str, code: str) -> None:
    send_email(
        to,
        "ICBC 抢号平台 — 邮箱验证码",
        f"你的验证码是 {code}，10 分钟内有效。如非本人操作请忽略。",
    )
