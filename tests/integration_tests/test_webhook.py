"""Integration tests: Teams webhook → LangGraph agent."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    with patch("agent.server._adapter.process_activity", new_callable=AsyncMock):
        from agent.server import app
        with TestClient(app) as c:
            yield c


def make_activity(text: str = "Hello") -> dict:
    return {
        "type": "message",
        "id": "test-id",
        "timestamp": "2026-05-01T00:00:00.000Z",
        "channelId": "msteams",
        "from": {"id": "user-1", "name": "Test User"},
        "conversation": {"id": "conv-1"},
        "recipient": {"id": "bot-1"},
        "text": text,
        "serviceUrl": "https://smba.trafficmanager.net/",
    }


def test_health_returns_profile(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["profile"] in ("local", "server")


def test_messages_wrong_content_type(client):
    resp = client.post(
        "/api/messages",
        content="hello",
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 415


def test_messages_valid_activity(client):
    payload = make_activity("What time is it?")
    resp = client.post(
        "/api/messages",
        content=json.dumps(payload),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
