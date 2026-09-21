from __future__ import annotations

import json

from onchain_agent.agent import Agent, clean_answer
from onchain_agent.config import Settings
from tests.conftest import FakeChat, FakeTools, completion


def make_agent(script, settings: Settings, tools: FakeTools) -> tuple[Agent, FakeChat]:
    chat = FakeChat(script=list(script))
    return Agent(chat, tools, settings), chat


async def test_direct_answer_without_tools(settings: Settings, fake_tools: FakeTools) -> None:
    agent, chat = make_agent(
        [completion(content="Ethereum is a blockchain.")], settings, fake_tools
    )
    result = await agent.run("What is Ethereum?")
    assert result.answer == "Ethereum is a blockchain."
    assert result.iterations == 1
    assert result.tool_calls == []
    assert result.budget_exhausted is False
    assert result.usage.total_tokens == 120
    # tools were offered to the model even though it did not use them
    assert chat.requests[0]["tools"] is not None
    assert {t["function"]["name"] for t in chat.requests[0]["tools"]} == {
        "get_eth_balance",
        "get_gas_price",
    }


async def test_single_tool_round_trip(settings: Settings, fake_tools: FakeTools) -> None:
    script = [
        completion(tool_calls=[("call_1", "get_eth_balance", {"address": "vitalik.eth"})]),
        completion(
            content="vitalik.eth holds 6.7126 ETH.", prompt_tokens=300, completion_tokens=30
        ),
    ]
    agent, chat = make_agent(script, settings, fake_tools)
    result = await agent.run("Balance of vitalik.eth?")

    assert result.answer == "vitalik.eth holds 6.7126 ETH."
    assert result.iterations == 2
    assert fake_tools.calls == [("get_eth_balance", {"address": "vitalik.eth"})]
    assert result.tool_calls[0].name == "get_eth_balance"
    assert result.tool_calls[0].is_error is False
    assert result.usage.prompt_tokens == 400
    assert result.usage.completion_tokens == 50

    # second request carries the assistant tool_call and the tool result, in order
    second = chat.requests[1]["messages"]
    assert second[-2]["role"] == "assistant"
    assert second[-2]["tool_calls"][0]["id"] == "call_1"
    assert second[-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": second[-1]["content"],
    }
    # tool result was truncated to max_tool_result_chars (50) before going back
    assert "[truncated" in second[-1]["content"]


async def test_budget_exhausted_forces_final_answer(
    settings: Settings, fake_tools: FakeTools
) -> None:
    looping = completion(tool_calls=[("c", "get_gas_price", {})])
    script = [looping, looping, looping, completion(content="Gas is about 0.72 gwei.")]
    agent, chat = make_agent(script, settings, fake_tools)
    result = await agent.run("Gas?")

    assert result.budget_exhausted is True
    assert result.iterations == settings.max_tool_iterations + 1
    assert len(fake_tools.calls) == settings.max_tool_iterations
    assert result.answer == "Gas is about 0.72 gwei."
    final_request = chat.requests[-1]
    assert final_request["tools"] is None
    assert "budget exhausted" in final_request["messages"][-1]["content"].lower()


async def test_think_blocks_are_stripped(settings: Settings, fake_tools: FakeTools) -> None:
    agent, _ = make_agent(
        [completion(content="<think>reasoning...\nmore</think>\n\nFinal answer.")],
        settings,
        fake_tools,
    )
    result = await agent.run("q")
    assert result.answer == "Final answer."
    assert clean_answer(None) == ""


async def test_tool_error_is_fed_back_not_raised(settings: Settings, fake_tools: FakeTools) -> None:
    fake_tools.raise_on.add("get_eth_balance")
    script = [
        completion(tool_calls=[("c1", "get_eth_balance", {"address": "x"})]),
        completion(content="I could not fetch the balance."),
    ]
    agent, chat = make_agent(script, settings, fake_tools)
    result = await agent.run("q")
    assert result.tool_calls[0].is_error is True
    assert "Tool call failed" in chat.requests[1]["messages"][-1]["content"]
    assert result.answer == "I could not fetch the balance."


async def test_malformed_arguments_are_reported_to_model(
    settings: Settings, fake_tools: FakeTools
) -> None:
    script = [
        completion(tool_calls=[("c1", "get_eth_balance", "{not json")]),
        completion(content="done"),
    ]
    agent, chat = make_agent(script, settings, fake_tools)
    result = await agent.run("q")
    assert fake_tools.calls == []  # never reached the tool
    assert result.tool_calls[0].is_error is True
    assert "Invalid tool arguments" in chat.requests[1]["messages"][-1]["content"]


async def test_cost_uses_price_table(fake_tools: FakeTools) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, model_prices_json=json.dumps({"claude-default": [3.0, 15.0]})
    )
    agent, _ = make_agent(
        [completion(content="ok", prompt_tokens=1_000_000, completion_tokens=100_000)],
        settings,
        fake_tools,
    )
    paid = await agent.run("q", model="claude-default")
    assert paid.estimated_cost_usd == 3.0 + 1.5
    free = await make_agent([completion(content="ok")], settings, fake_tools)[0].run("q")
    assert free.model == "local-default"
    assert free.estimated_cost_usd == 0.0
