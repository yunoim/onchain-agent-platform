from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from onchain_agent.agent import Agent
from onchain_agent.config import Settings
from onchain_agent.main import create_app
from tests.conftest import FakeChat, FakeTools, completion


@pytest.fixture
def client(settings: Settings, fake_tools: FakeTools) -> TestClient:
    chat = FakeChat(
        script=[
            completion(tool_calls=[("c1", "get_eth_balance", {"address": "vitalik.eth"})]),
            completion(content="6.7126 ETH at block 26026395."),
        ]
    )
    app = create_app(settings, agent=Agent(chat, fake_tools, settings))
    with TestClient(app) as c:
        yield c


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_tools_lists_mcp_tools(client: TestClient) -> None:
    names = {t["name"] for t in client.get("/tools").json()}
    assert names == {"get_eth_balance", "get_gas_price"}


def test_ask_returns_answer_and_trace(client: TestClient) -> None:
    r = client.post("/ask", json={"question": "Balance of vitalik.eth?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "6.7126 ETH at block 26026395."
    assert body["model"] == "local-default"
    assert body["iterations"] == 2
    assert body["tool_calls"][0]["name"] == "get_eth_balance"
    assert body["usage"]["total_tokens"] == 240
    assert body["estimated_cost_usd"] == 0.0


def test_ask_validates_input(client: TestClient) -> None:
    assert client.post("/ask", json={"question": "hi"}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422


def test_metrics_exposes_agent_counters(client: TestClient) -> None:
    client.post("/ask", json={"question": "Balance of vitalik.eth?"})
    text = client.get("/metrics").text
    assert "onchain_agent_requests_total" in text
    assert "onchain_agent_llm_tokens_total" in text
    assert 'onchain_agent_tool_calls_total{status="ok",tool="get_eth_balance"}' in text
