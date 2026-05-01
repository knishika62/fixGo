"""OpenCode Go provider implementation (OpenAI-compatible chat)."""

from typing import Any

from core.anthropic import (
    ReasoningReplayMode,
    build_base_request_body,
)
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.defaults import OPENCODE_GO_DEFAULT_BASE
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport


class OpenCodeGoProvider(OpenAIChatTransport):
    """OpenCode Go provider using OpenAI-compatible chat completions."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OpenCodeGo",
            base_url=config.base_url or OPENCODE_GO_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Build OpenAI-format request body from Anthropic request.

        Uses THINK_TAGS instead of REASONING_CONTENT because Moonshot AI
        (the backend behind OpenCode Go) rejects assistant tool_call
        messages that are missing a separate ``reasoning_content`` field.
        THINK_TAGS embeds reasoning inside the text content, which avoids
        the non-standard ``reasoning_content`` key entirely.

        Additionally, Moonshot requires ``reasoning_content`` on assistant
        messages that carry ``tool_calls`` when thinking is enabled. We
        inject an empty string so the field is present without sending
        actual reasoning text twice.
        """
        try:
            body = build_base_request_body(
                request,
                reasoning_replay=ReasoningReplayMode.THINK_TAGS
                if self._is_thinking_enabled(request, thinking_enabled)
                else ReasoningReplayMode.DISABLED,
            )
        except OpenAIConversionError as exc:
            raise InvalidRequestError(str(exc)) from exc

        # Moonshot AI workaround: ensure every assistant message with
        # tool_calls also has a reasoning_content field when thinking
        # is enabled, otherwise it returns 400.  Empty string may be
        # stripped by the OpenAI client, so use a single space.
        if self._is_thinking_enabled(request, thinking_enabled):
            for msg in body.get("messages", []):
                if (
                    msg.get("role") == "assistant"
                    and "tool_calls" in msg
                    and "reasoning_content" not in msg
                ):
                    msg["reasoning_content"] = " "
        return body
