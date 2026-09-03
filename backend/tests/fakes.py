"""Test doubles that must survive the LangChain 0.3 to 1.x migration.

RecordingChatModel is a BaseChatModel that records every message list it is
asked to generate from and returns a fixed response. The prompt text it saw is
the thing under test: if the diff is not in there, the review is blind."""

from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class RecordingChatModel(BaseChatModel):
    response: str = "[]"
    calls: List[List[BaseMessage]] = Field(default_factory=list)

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.calls.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    @property
    def seen_text(self) -> str:
        parts = []
        for call in self.calls:
            for m in call:
                parts.append(m.content if isinstance(m.content, str) else str(m.content))
        return "\n".join(parts)
