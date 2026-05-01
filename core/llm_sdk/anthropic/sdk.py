"""Anthropic Claude SDK implementation using curl_cffi and httpx"""

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

class AnthropicSDK(BaseLLMSDK):
    """Anthropic Claude SDK implementation using curl_cffi and httpx"""

    def __init__(self, api_key: str, base_url: str | None = None):
        super().__init__(api_key, base_url or "https://api.anthropic.com/v1")
        self.sdk_mode = "messages"
        self._http_client: HTTPClient | None = None

    @property
    def client(self) -> HTTPClient:
        """Lazy load the custom HTTP client"""
        if self._http_client is None:
            base_url = self.base_url or "https://api.anthropic.com/v1"
            self._http_client = HTTPClient(base_url, self.api_key)
        return self._http_client

    def _get_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        """Generate response using Anthropic API via curl_cffi"""
        try:
            system_prompt = ""
            anthropic_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_prompt = msg.content
                else:
                    anthropic_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })

            token_limits = context_length_manager.get_token_limits(config.model)
            max_tokens = config.max_tokens or token_limits.max_output_tokens

            payload = {
                "model": config.model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": config.temperature,
                "top_p": config.top_p or 1.0,
                "stop_sequences": config.stop_sequences,
                "stream": stream
            }
            if system_prompt:
                payload["system"] = system_prompt

            if stream:
                return self._stream_response(payload)
            else:
                response_data = await self.client.post("messages", payload, self._get_headers())

                content = response_data["content"]
                result_content = ""
                reasoning_content = ""
                
                for block in content:
                    if block["type"] == "text":
                        result_content += block["text"]
                    elif block["type"] == "thinking":
                        reasoning_content += block.get("thinking", "")
                
                response = GenerationResponse(
                    content=result_content,
                    model=response_data["model"],
                    finish_reason=response_data["stop_reason"],
                    usage={
                        "input_tokens": response_data["usage"]["input_tokens"],
                        "output_tokens": response_data["usage"]["output_tokens"],
                    },
                )
                
                # Add reasoning content if present
                if reasoning_content:
                    response.reasoning_content = reasoning_content
                
                return response

        except Exception as e:
            logger.error(f"Anthropic generation failed: {str(e)}")
            raise RuntimeError(f"Anthropic generation failed: {str(e)}") from e

    async def _stream_response(self, payload: dict[str, Any]) -> AsyncGenerator:
        """Stream response from Anthropic API using curl_cffi and manual SSE parsing"""
        try:
            async for line in self.client.stream("messages", payload, self._get_headers()):
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("type") == "content_block_delta" and chunk.get("delta"):
                            if chunk["delta"].get("type") == "text_delta":
                                yield {"type": "text", "content": chunk["delta"]["text"]}
                            elif chunk["delta"].get("type") == "thinking_delta":
                                # Extended thinking (reasoning) content
                                yield {"type": "reasoning", "content": chunk["delta"].get("thinking", "")}
                        elif chunk.get("type") == "message_stop":
                            break
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"Failed to parse stream chunk: {e}")
                        continue
        except Exception as e:
            logger.error(f"Anthropic streaming failed: {str(e)}")
            raise RuntimeError(f"Anthropic streaming failed: {str(e)}") from e

    async def _stream_response_with_tools(self, payload: dict[str, Any]) -> AsyncGenerator:
        """Stream response from Anthropic API with tool calling support"""
        try:
            content_buffer = ""
            tool_calls = []
            current_tool_call = None

            async for line in self.client.stream("messages", payload, self._get_headers()):
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    try:
                        chunk = json.loads(data_str)

                        if chunk.get("type") == "content_block_start":
                            content_block = chunk.get("content_block", {})
                            if content_block.get("type") == "text":
                                pass  # Starting text block
                            elif content_block.get("type") == "tool_use":
                                current_tool_call = {
                                    "id": content_block.get("id", ""),
                                    "name": content_block.get("name", ""),
                                    "arguments": ""
                                }

                        elif chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text_chunk = delta.get("text", "")
                                content_buffer += text_chunk
                                yield {"type": "text", "content": text_chunk}
                            elif delta.get("type") == "thinking_delta":
                                # Extended thinking (reasoning) content
                                yield {"type": "reasoning", "content": delta.get("thinking", "")}
                            elif delta.get("type") == "input_json_delta":
                                if current_tool_call:
                                    current_tool_call["arguments"] += delta.get("partial_json", "")

                        elif chunk.get("type") == "content_block_stop":
                            if current_tool_call:
                                tool_call = ToolCall(
                                    id=current_tool_call["id"],
                                    name=current_tool_call["name"],
                                    arguments=current_tool_call["arguments"],
                                )
                                tool_calls.append(tool_call)
                                yield {"type": "tool_call", "tool_call": tool_call}
                                current_tool_call = None

                        elif chunk.get("type") == "message_stop":
                            break

                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"Failed to parse stream chunk with tools: {e}")
                        continue

        except Exception as e:
            logger.error(f"Anthropic streaming with tools failed: {str(e)}")
            raise RuntimeError(f"Anthropic streaming with tools failed: {str(e)}") from e

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        """Generate response with tool calling using curl_cffi"""
        try:
            system_prompt = ""
            anthropic_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_prompt = msg.content
                else:
                    anthropic_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })

            anthropic_tools = [
                {
                    "name": tool["function"]["name"],
                    "description": tool["function"].get("description", ""),
                    "input_schema": tool["function"]["parameters"],
                }
                for tool in tools
            ]

            token_limits = context_length_manager.get_token_limits(config.model)
            max_tokens = config.max_tokens or token_limits.max_output_tokens

            payload = {
                "model": config.model,
                "messages": anthropic_messages,
                "tools": anthropic_tools,
                "max_tokens": max_tokens,
                "temperature": config.temperature,
                "stream": stream
            }
            if system_prompt:
                payload["system"] = system_prompt

            if stream:
                return self._stream_response_with_tools(payload)
            else:
                response_data = await self.client.post("messages", payload, self._get_headers())

                content = response_data["content"]
                result_content = ""
                reasoning_content = ""
                tool_calls = []

                for block in content:
                    if block["type"] == "text":
                        result_content += block["text"]
                    elif block["type"] == "thinking":
                        reasoning_content += block.get("thinking", "")
                    elif block["type"] == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=block["id"],
                                name=block["name"],
                                arguments=json.dumps(block["input"]),
                            )
                        )

                response = GenerationResponse(
                    content=result_content,
                    model=response_data["model"],
                    finish_reason=response_data["stop_reason"],
                    tool_calls=tool_calls if tool_calls else None,
                    usage={
                        "input_tokens": response_data["usage"]["input_tokens"],
                        "output_tokens": response_data["usage"]["output_tokens"],
                    },
                )
                
                # Add reasoning content if present
                if reasoning_content:
                    response.reasoning_content = reasoning_content
                
                return response

        except Exception as e:
            logger.error(f"Anthropic tool generation failed: {str(e)}")
            raise RuntimeError(f"Anthropic tool generation failed: {str(e)}") from e

    def get_available_models(self) -> list[str]:
        """Get available Anthropic models using httpx as requested"""
        # Note: Anthropic doesn't have a public models endpoint like OpenAI.
        # However, for consistency we try or return the known list.
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
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
