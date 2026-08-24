"""LLMProvider interface and shared message types."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class LLMMessage(BaseModel):
    """A single chat message."""

    role: str  # "system" | "user" | "assistant"
    content: str


class LLMError(Exception):
    """Raised when the LLM backend is unavailable or misconfigured."""


@runtime_checkable
class LLMProvider(Protocol):
    """Provider-agnostic LLM contract used by the intelligence services."""

    async def complete(self, messages: list[LLMMessage], *, temperature: float = 0.2) -> str:
        """Return a completion for the given chat messages."""
        ...

    async def summarize(self, text: str, *, instructions: str | None = None) -> str:
        """Summarize a block of text."""
        ...

    async def classify(self, text: str, labels: list[str]) -> str:
        """Return the best-matching label for the text."""
        ...

    async def extract(self, text: str, what: str) -> list[str]:
        """Extract a list of items (e.g. action items) from the text."""
        ...

    async def generate_reply(self, context: str, instructions: str) -> str:
        """Generate a reply body given conversation context and instructions."""
        ...


class LLMBase:
    """Implements the high-level tasks in terms of :meth:`complete`.

    Concrete providers only need to implement ``complete``. Untrusted content is always
    passed in the user role — never the system role.
    """

    async def complete(self, messages: list[LLMMessage], *, temperature: float = 0.2) -> str:
        raise NotImplementedError

    async def summarize(self, text: str, *, instructions: str | None = None) -> str:
        from .prompts import SUMMARIZE_SYSTEM

        user = text if instructions is None else f"{instructions}\n\n{text}"
        return await self.complete(
            [
                LLMMessage(role="system", content=SUMMARIZE_SYSTEM),
                LLMMessage(role="user", content=user),
            ]
        )

    async def classify(self, text: str, labels: list[str]) -> str:
        from .prompts import CLASSIFY_SYSTEM

        system = f"{CLASSIFY_SYSTEM}\nLabels: {', '.join(labels)}"
        choice = (
            await self.complete(
                [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=text),
                ]
            )
        ).strip()
        return choice if choice in labels else (labels[0] if labels else choice)

    async def extract(self, text: str, what: str) -> list[str]:
        from .prompts import EXTRACT_ACTIONS_SYSTEM

        out = await self.complete(
            [
                LLMMessage(role="system", content=EXTRACT_ACTIONS_SYSTEM),
                LLMMessage(role="user", content=f"Extract {what} from:\n{text}"),
            ]
        )
        if out.strip().upper() == "NONE":
            return []
        return [line[2:].strip() for line in out.splitlines() if line.strip().startswith("- ")]

    async def generate_reply(self, context: str, instructions: str) -> str:
        from .prompts import REPLY_SYSTEM

        return await self.complete(
            [
                LLMMessage(role="system", content=REPLY_SYSTEM),
                LLMMessage(
                    role="user",
                    content=f"Instructions: {instructions}\n\nContext:\n{context}",
                ),
            ]
        )
