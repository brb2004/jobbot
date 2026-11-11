import asyncio
from email.message import EmailMessage

from app.services import email_services
from app.services.email_services import smtp_transport


class FakeSMTP:
    sent: list[EmailMessage] = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def _msg(**headers) -> EmailMessage:
    m = EmailMessage()
    m["From"] = "JobMatch <hello@mail.example.com>"
    m["To"] = "a@example.com"
    for k, v in headers.items():
        m[k.replace("_", "-")] = v
    m.set_content("hi")
    return m


def test_reply_to_added_when_configured(monkeypatch):
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    asyncio.run(smtp_transport("h", 587, "u", "p", reply_to="support@example.com")(_msg()))
    assert FakeSMTP.sent[0]["Reply-To"] == "support@example.com"


def test_no_reply_to_by_default(monkeypatch):
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    asyncio.run(smtp_transport("h", 587, "u", "p")(_msg()))
    assert "Reply-To" not in FakeSMTP.sent[0]


def test_existing_reply_to_kept(monkeypatch):
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    asyncio.run(smtp_transport("h", 587, "u", "p", reply_to="support@example.com")(_msg(Reply_To="x@example.com")))
    assert FakeSMTP.sent[0].get_all("Reply-To") == ["x@example.com"]
