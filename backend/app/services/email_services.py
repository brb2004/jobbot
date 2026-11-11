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
    msg["Subject"] = "Reset your JobMatch password"
    msg.set_content(
        "Someone asked to reset the password for this JobMatch account.\n\n"
        f"Set a new password here. The link works once, for 30 minutes:\n{link}\n\n"
        "If this wasn't you, ignore this email. Your password hasn't changed.\n")
    return msg


def verify_email(from_addr: str, to: str, link: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = "Confirm your email for JobMatch"
    msg.set_content(
        "Confirm this address to get your top job matches every week:\n"
        f"{link}\n\n"
        "The link works for 7 days. If you didn't sign up for JobMatch, ignore this email "
        "and nothing will be sent to you.\n")
    return msg


def account_exists_email(from_addr: str, to: str, app_url: str) -> EmailMessage:
    """Sent instead of an error when someone signs up with a registered address: the sign-up page
    answers the same either way, so it can't be used to check who has an account."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = "You already have a JobMatch account"
    msg.set_content(
        "Someone tried to sign up for JobMatch with this address, but it already has an account.\n\n"
        f"Log in here:\n{app_url}\n\n"
        "Forgot your password? Use \"Forgot password\" on that page to get a reset link.\n"
        "If this wasn't you, ignore this email. Nothing about your account has changed.\n")
    return msg


def feedback_email(from_addr: str, to: str, ref: str, kind: str) -> EmailMessage:
    """Doesn't quote the report back: the form can't be used to send arbitrary text from our address."""
    what = {"bug": "bug report", "idea": "feature idea"}.get(kind, "feedback")
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = f"We got your {what} (#{ref})"
    msg.set_content(
        f"Thanks for the {what}. It's in our queue as #{ref}.\n\n"
        "We read every report. If we need more details, we'll reply to this email.\n\n"
        "JobMatch\n")
    return msg
