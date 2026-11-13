import httpx
import pytest

from app.api import deps_api
from app.core.config_core import get_settings
from app.main import app
from app.services import notify_services
from tests.test_email_verification import link_token, register


@pytest.fixture
def mail(client):
    sent = []

    async def capture(msg):
        sent.append(msg)

    app.dependency_overrides[deps_api.get_mailer] = lambda: capture
    yield sent
    app.dependency_overrides.pop(deps_api.get_mailer, None)


async def test_notify_posts_the_message_to_the_configured_url(monkeypatch):
    monkeypatch.setattr(get_settings(), "NOTIFY_URL", "https://ntfy.example/topic")
    seen = []

    def handler(request):
        seen.append((str(request.url), request.content.decode()))
        return httpx.Response(200)

    await notify_services.notify("hello", transport=httpx.MockTransport(handler))
    assert seen == [("https://ntfy.example/topic", "hello")]


async def test_notify_is_off_without_a_url_and_never_raises(monkeypatch):
    monkeypatch.setattr(get_settings(), "NOTIFY_URL", "")
    await notify_services.notify("ignored", transport=httpx.MockTransport(lambda r: 1 / 0))
    monkeypatch.setattr(get_settings(), "NOTIFY_URL", "https://ntfy.example/topic")

    def down(request):
        raise httpx.ConnectError("down")

    await notify_services.notify("lost", transport=httpx.MockTransport(down))


async def test_confirming_an_account_sends_one_notification(client, mail, monkeypatch):
    sent = []

    async def capture(message, transport=None):
        sent.append(message)

    monkeypatch.setattr("app.api.routes.verify_routes.notify", capture)
    await register(client)
    token = link_token(mail[0])
    await client.post("/auth/verify", json={"token": token})
    await client.post("/auth/verify", json={"token": token})
    assert len(sent) == 1 and "confirmed accounts so far" in sent[0]
