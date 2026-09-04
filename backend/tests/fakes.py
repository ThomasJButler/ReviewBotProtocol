"""Test doubles. RecordingChatModel is a BaseChatModel that records every
message list it is asked to generate from and returns a fixed response."""

from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class RecordingChatModel(BaseChatModel):
    response: str = '{"findings": [], "summary": "Nothing to report."}'
    responses: Optional[List[str]] = None  # when set, answers are taken from this list in order (last one repeats)
    calls: List[List[BaseMessage]] = Field(default_factory=list)
    bound_kwargs: List[dict] = Field(default_factory=list)
    fail_with: Optional[str] = None

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.calls.append(list(messages))
        self.bound_kwargs.append(dict(kwargs))
        if self.fail_with:
            raise RuntimeError(self.fail_with)
        content = self.response
        if self.responses:
            content = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        msg = AIMessage(content=content,
                        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120})
        return ChatResult(generations=[ChatGeneration(message=msg)])

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
