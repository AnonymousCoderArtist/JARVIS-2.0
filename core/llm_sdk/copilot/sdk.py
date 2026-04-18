"""GitHub Copilot SDK adapter."""

from __future__ import annotations

import asyncio
import importlib
import json
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from ..base.sdk import BaseLLMSDK, GenerationConfig, GenerationResponse, Message, ToolCall


class CopilotSDK(BaseLLMSDK):
    """Adapter around github/copilot-sdk's session API."""

    FALLBACK_MODELS = ["gpt-5", "claude-sonnet-4.5", "gpt-4.1"]

    def __init__(self, github_token: str | None = None, base_url: str | None = None):
        super().__init__(api_key=github_token or "", base_url=base_url)
        self.github_token = github_token or None
        self._cwd = str(Path.cwd())

    @property
    def client(self):  # type: ignore[override]
        return None

    def validate_api_key(self) -> bool:
        return True

    def get_available_models(self) -> list[str]:
        return list(self.FALLBACK_MODELS)

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"cwd": self._cwd}
        if self.github_token:
            kwargs["github_token"] = self.github_token
        else:
            kwargs["use_logged_in_user"] = True
        return kwargs

    def _build_prompt(self, messages: list[Message], config: GenerationConfig, tools: list[dict[str, Any]] | None = None) -> str:
        parts: list[str] = []
        for message in messages:
            content = message.content or ""
            if message.role == "system":
                parts.append(f"SYSTEM:\n{content}")
            elif message.role == "user":
                parts.append(f"USER:\n{content}")
            elif message.role == "assistant":
                parts.append(f"ASSISTANT:\n{content}")
            else:
                parts.append(f"{message.role.upper()}:\n{content}")

        if tools:
            tool_lines = []
            for tool in tools:
                function = tool.get("function", {})
                tool_lines.append(
                    f"- {function.get('name', 'tool')}: {function.get('description', '')}\n"
                    f"  schema: {json.dumps(function.get('parameters', {}), ensure_ascii=False)}"
                )
            parts.append("AVAILABLE TOOLS:\n" + "\n".join(tool_lines))
            parts.append(
                "If a tool is needed, return JSON only with keys content and tool_calls. "
                "tool_calls must be a list of objects shaped like OpenAI function calls."
            )

        parts.append(f"MODEL: {config.model}")
        return "\n\n".join(parts)

    def _strip_code_fence(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else text.strip()

    def _response_text(self, response: Any) -> str:
        data = getattr(response, "data", response)
        content = getattr(data, "content", None)
        if isinstance(content, str):
            return content
        if content is not None:
            return str(content)
        text = getattr(data, "text", None)
        if isinstance(text, str):
            return text
        return str(data) if data is not None else ""

    def _parse_tool_calls(self, payload: dict[str, Any]) -> list[ToolCall]:
        tool_calls: list[ToolCall] = []
        for index, item in enumerate(payload.get("tool_calls", []) or []):
            function = item.get("function", {}) if isinstance(item, dict) else {}
            arguments = function.get("arguments", {})
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, ensure_ascii=False)
            tool_calls.append(
                ToolCall(
                    id=str(item.get("id") or f"copilot-tool-{index}"),
                    name=str(function.get("name", "")),
                    arguments=arguments,
                )
            )
        return tool_calls

    def _build_response(self, text: str, config: GenerationConfig) -> GenerationResponse:
        cleaned = self._strip_code_fence(text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return GenerationResponse(
                content=cleaned,
                model=config.model,
                finish_reason="stop",
                metadata={"provider": "copilot"},
            )

        content = str(payload.get("content", ""))
        tool_calls = self._parse_tool_calls(payload)
        return GenerationResponse(
            content=content,
            model=config.model,
            finish_reason="stop",
            tool_calls=tool_calls or None,
            metadata={"provider": "copilot"},
        )

    async def _send(self, messages: list[Message], config: GenerationConfig, tools: list[dict[str, Any]] | None = None) -> str:
        copilot_module = importlib.import_module("copilot")
        session_module = importlib.import_module("copilot.session")
        CopilotClient = getattr(copilot_module, "CopilotClient")
        PermissionHandler = getattr(session_module, "PermissionHandler")

        prompt = self._build_prompt(messages, config, tools)
        async with CopilotClient(**self._client_kwargs()) as client:
            session = await client.create_session(
                model=config.model,
                on_permission_request=PermissionHandler.approve_all,
            )
            response = await session.send_and_wait(prompt)
            return self._response_text(response)

    async def _stream(self, messages: list[Message], config: GenerationConfig, tools: list[dict[str, Any]] | None = None) -> AsyncGenerator[str, None]:
        copilot_module = importlib.import_module("copilot")
        events_module = importlib.import_module("copilot.generated.session_events")
        session_module = importlib.import_module("copilot.session")
        CopilotClient = getattr(copilot_module, "CopilotClient")
        AssistantMessageDeltaData = getattr(events_module, "AssistantMessageDeltaData")
        SessionIdleData = getattr(events_module, "SessionIdleData")
        PermissionHandler = getattr(session_module, "PermissionHandler")

        prompt = self._build_prompt(messages, config, tools)
        queue: asyncio.Queue[str] = asyncio.Queue()
        done = asyncio.Event()

        async with CopilotClient(**self._client_kwargs()) as client:
            session = await client.create_session(
                model=config.model,
                streaming=True,
                on_permission_request=PermissionHandler.approve_all,
            )

            def on_event(event: Any) -> None:
                data = getattr(event, "data", event)
                if isinstance(data, AssistantMessageDeltaData):
                    delta = getattr(data, "content", None) or getattr(data, "delta", None) or ""
                    if delta:
                        queue.put_nowait(str(delta))
                elif isinstance(data, SessionIdleData):
                    done.set()

            session.on(on_event)
            await session.send(prompt)

            while not done.is_set() or not queue.empty():
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    if done.is_set():
                        break

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> Any:
        if stream:
            return self._stream(messages, config)
        text = await self._send(messages, config)
        return self._build_response(text, config)

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        config: GenerationConfig,
        stream: bool = False,
    ) -> Any:
        if stream:
            return self._stream(messages, config, tools)
        text = await self._send(messages, config, tools)
        return self._build_response(text, config)

