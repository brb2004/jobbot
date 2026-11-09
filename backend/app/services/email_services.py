import asyncio
import smtplib
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import User

SUBJECT = "Your top job matches this week"


class EmailSender:
    """Same shape send_weekly expects: send(user_id, body). Looks up the address, hands off to a transport."""

    def __init__(self, s: AsyncSession, from_addr: str, transport):
        self.s = s
        self.from_addr = from_addr
        self.transport = transport

    async def send(self, user_id: UUID, body: str) -> None:
        user = await self.s.get(User, user_id)
        if user is None:
            return
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = user.email
        msg["Subject"] = SUBJECT
        msg.set_content(body)
        await self.transport(msg)


def smtp_transport(host: str, port: int, username: str, password: str):
    """Real transport: STARTTLS + login. smtplib blocks, so it runs in a thread."""
    async def send(msg: EmailMessage) -> None:
        def _send():
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(username, password)
                smtp.send_message(msg)
        await asyncio.to_thread(_send)
    return send


def reset_email(from_addr: str, to: str, link: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = "Reset your JobBot password"
    msg.set_content(
        "Someone asked to reset the password for this JobBot account.\n\n"
        f"Set a new password here. The link works once, for 30 minutes:\n{link}\n\n"
        "If this wasn't you, ignore this email. Your password hasn't changed.\n")
    return msg
