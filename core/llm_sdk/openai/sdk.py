"""OpenAI GPT SDK implementation using curl_cffi and httpx"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from ...llm_sdk.context_length_manager import context_length_manager
from ..base.sdk import (
    BaseLLMSDK,
    GenerationConfig,
    GenerationResponse,
    Message,
    ToolCall,
)
from ..http_client import HTTPClient

logger = logging.getLogger(__name__)

class OpenAISDK(BaseLLMSDK):
    """OpenAI GPT SDK implementation using curl_cffi and httpx"""

    def __init__(self, api_key: str, base_url: str | None = None):
        super().__init__(api_key, base_url or "https://api.openai.com/v1")
        self.sdk_mode = "messages"
        self._http_client: HTTPClient | None = None

    @property
    def client(self) -> HTTPClient:
        """Lazy load the custom HTTP client"""
        if self._http_client is None:
            base_url = self.base_url or "https://api.openai.com/v1"
            self._http_client = HTTPClient(base_url, self.api_key)
        return self._http_client

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        """Generate response using OpenAI API via curl_cffi"""
        try:
            openai_messages = self.convert_messages_to_dict(messages)
            token_limits = context_length_manager.get_token_limits(config.model)
            max_tokens = config.max_tokens or (token_limits.max_output_tokens if token_limits else 4096)

            payload = {
                "model": config.model,
                "messages": openai_messages,
                "temperature": config.temperature,
                "max_tokens": max_tokens,
                "top_p": config.top_p or 1.0,
                "frequency_penalty": config.frequency_penalty or 0.0,
                "presence_penalty": config.presence_penalty or 0.0,
                "stop": config.stop_sequences,
                "stream": stream
            }

            if stream:
                return self._stream_response(payload)
            else:
                response_data = await self.client.post("chat/completions", payload, self._get_headers())

                return GenerationResponse(
                    content=response_data["choices"][0]["message"]["content"] or "",
                    model=response_data["model"],
                    finish_reason=response_data["choices"][0]["finish_reason"],
                    usage={
                        "input_tokens": response_data["usage"]["prompt_tokens"],
                        "output_tokens": response_data["usage"]["completion_tokens"],
                        "total_tokens": response_data["usage"]["total_tokens"],
                    },
                )

        except Exception as e:
            logger.error(f"OpenAI generation failed: {str(e)}")
            raise RuntimeError(f"OpenAI generation failed: {str(e)}") from e

    async def _stream_response(self, payload: dict[str, Any]) -> AsyncGenerator:
        """Stream response from OpenAI API using curl_cffi and manual SSE parsing"""
        try:
            async for line in self.client.stream("chat/completions", payload, self._get_headers()):
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                            yield chunk["choices"][0]["delta"]["content"]
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.debug(f"Failed to parse stream chunk: {e}")
                        continue
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {str(e)}")
            raise RuntimeError(f"OpenAI streaming failed: {str(e)}") from e

    async def _stream_response_with_tools(self, payload: dict[str, Any]) -> AsyncGenerator:
        """Stream response from OpenAI API with tool calling support"""
        try:
            content_buffer = ""
            tool_calls = []

            async for line in self.client.stream("chat/completions", payload, self._get_headers()):
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        if not chunk.get("choices"):
                            continue

                        delta = chunk["choices"][0].get("delta", {})

                        # Stream text content
                        if delta.get("content"):
                            text_chunk = delta["content"]
                            content_buffer += text_chunk
                            yield {"type": "text", "content": text_chunk}

                        # Handle tool calls in streaming
                        if delta.get("tool_calls"):
                            for tc_delta in delta["tool_calls"]:
                                if tc_delta.get("index") is not None:
                                    index = tc_delta["index"]
                                    # Ensure tool_calls list has enough elements
                                    while len(tool_calls) <= index:
                                        tool_calls.append({"id": "", "name": "", "arguments": ""})

                                    if tc_delta.get("id"):
                                        tool_calls[index]["id"] = tc_delta["id"]

                                    if tc_delta.get("function"):
                                        func = tc_delta["function"]
                                        if func.get("name"):
                                            tool_calls[index]["name"] = func["name"]
                                        if func.get("arguments"):
                                            tool_calls[index]["arguments"] += func["arguments"]

                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.debug(f"Failed to parse stream chunk with tools: {e}")
                        continue

            # Yield final tool calls if any
            if tool_calls:
                yield {"type": "tool_calls", "tool_calls": tool_calls}

        except Exception as e:
            logger.error(f"OpenAI streaming with tools failed: {str(e)}")
            raise RuntimeError(f"OpenAI streaming with tools failed: {str(e)}") from e

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        """Generate response with tool calling using curl_cffi"""
        try:
            openai_messages = self.convert_messages_to_dict(messages)
            token_limits = context_length_manager.get_token_limits(config.model)
            max_tokens = config.max_tokens or (token_limits.max_output_tokens if token_limits else 4096)

            payload = {
                "model": config.model,
                "messages": openai_messages,
                "tools": tools,
                "temperature": config.temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }

            logger.debug(f"Sending request to {self.base_url}/chat/completions with model {config.model}")

            if stream:
                return self._stream_response_with_tools(payload)
            else:
                response_data = await self.client.post("chat/completions", payload, self._get_headers())
                logger.debug(f"Response data: {response_data}")

                if not response_data:
                    raise ValueError("No response data received from API")

                if "choices" not in response_data or not response_data["choices"]:
                    raise ValueError(f"Response missing 'choices': {response_data}")

                message = response_data["choices"][0]["message"]
                tool_calls = []

                if "tool_calls" in message and message["tool_calls"]:
                    for tc in message["tool_calls"]:
                        tool_calls.append(
                            ToolCall(
                                id=tc["id"],
                                name=tc["function"]["name"],
                                arguments=tc["function"]["arguments"],
                            )
                        )

                return GenerationResponse(
                    content=message.get("content") or "",
                    model=response_data.get("model", config.model),
                    finish_reason=response_data["choices"][0].get("finish_reason", "unknown"),
                    tool_calls=tool_calls if tool_calls else None,
                    usage={
                        "input_tokens": response_data.get("usage", {}).get("prompt_tokens", 0),
                        "output_tokens": response_data.get("usage", {}).get("completion_tokens", 0),
                        "total_tokens": response_data.get("usage", {}).get("total_tokens", 0),
                    },
                )

        except Exception as e:
            logger.error(f"OpenAI tool generation failed: {str(e)}")
            raise RuntimeError(f"OpenAI tool generation failed: {str(e)}") from e

    def get_available_models(self) -> list[str]:
        """Get available OpenAI models."""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]

    def convert_messages_to_dict(self, messages: list[Message]) -> list[dict]:
        """Convert Message objects to dictionaries"""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                **(msg.metadata or {})
            }
            for msg in messages
        ]
