"""邮件发送（smtplib 同步，复用系统 Gmail SMTP）。

接口里不要直接调用：用 BackgroundTasks 在响应发出后再发，见 app/api/auth.py。
"""
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

settings = get_settings()

# Connect / read timeout. Without it a slow Gmail could hold a worker thread indefinitely.
SMTP_TIMEOUT_SECONDS = 15


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_user:
        raise ValueError("SMTP 未配置：请在 .env 设置 SMTP_USER/SMTP_PASSWORD")
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as s:
        s.starttls()
        s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


def send_verification_code(to: str, code: str, site: str = "booking") -> None:
    if site == "routes":
        # Users who signed up on the route-pack site (roadtestgo.com/) never
        # saw the booking service, so don't brand the email with it.
        send_email(
            to,
            "路考练习路线 · roadtestgo — 邮箱验证码 / Verification code",
            f"你的验证码是 {code}，10 分钟内有效。如非本人操作请忽略。\n\n"
            f"Your verification code is {code}. It is valid for 10 minutes. "
            "If you did not request it, please ignore this email.\n\n"
            "roadtestgo.com — 独立开发的小工具，与 ICBC 无任何关联。"
            " An independent tool, not affiliated with ICBC.",
        )
        return
    send_email(
        to,
        "ICBC 抢号平台 — 邮箱验证码",
        f"你的验证码是 {code}，10 分钟内有效。如非本人操作请忽略。",
    )
