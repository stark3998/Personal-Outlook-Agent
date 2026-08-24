"""Golden-set regression scaffold for the LLM post-processing layer.

The default suite is hermetic: a scripted LLM returns canned ``model_output`` strings from
``golden.json`` and we assert that ``LLMBase`` parses them into the expected structures.
This guards the parsing/prompt-contract logic against regressions.

An optional live suite runs the same dataset against the real Foundry provider. It is
skipped unless ``FOUNDRY_EVAL=1`` is set (and Foundry env vars are configured).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from outlook_agent.intelligence.base import LLMBase, LLMMessage

_GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text(encoding="utf-8"))


class _ScriptedLLM(LLMBase):
    """LLMBase whose ``complete`` returns a preset string, exercising real post-processing."""

    def __init__(self, output: str) -> None:
        self._output = output

    async def complete(self, messages: list[LLMMessage], *, temperature: float = 0.2) -> str:
        return self._output


@pytest.mark.parametrize("case", _GOLDEN["extract_action_items"], ids=lambda c: c["name"])
async def test_extract_action_items_golden(case: dict) -> None:
    llm = _ScriptedLLM(case["model_output"])
    assert await llm.extract("some email", "action items") == case["expected"]


@pytest.mark.parametrize("case", _GOLDEN["classify"], ids=lambda c: c["name"])
async def test_classify_golden(case: dict) -> None:
    llm = _ScriptedLLM(case["model_output"])
    assert await llm.classify("some email", case["labels"]) == case["expected"]


@pytest.mark.skipif(
    os.getenv("FOUNDRY_EVAL") != "1",
    reason="Live Foundry eval is opt-in; set FOUNDRY_EVAL=1 with Foundry env configured.",
)
async def test_extract_action_items_live_foundry() -> None:
    from outlook_agent.intelligence.foundry import FoundryLLMProvider

    provider = FoundryLLMProvider()
    items = await provider.extract(
        "Please call Bob tomorrow and send the report by Friday.", "action items"
    )
    assert isinstance(items, list)
