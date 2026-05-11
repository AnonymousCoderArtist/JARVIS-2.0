"""Tests for MCP resources, prompts, and metadata cache integration."""

import json
import tempfile
from pathlib import Path

import pytest

from core.tools.mcp_capabilities import (
    MCPPromptArgument,
    MCPPromptSpec,
    MCPResourceSpec,
)
from core.tools.mcp_metadata_cache import (
    MCPMetadataCache,
    PromptMetadata,
    ResourceMetadata,
    ServerMetadata,
    ToolMetadata,
)


class TestResourceMetadata:
    """Tests for ResourceMetadata data model."""

    def test_create(self):
        rm = ResourceMetadata(
            uri="file:///data.json",
            name="data",
            description="Data file",
            mime_type="application/json",
            server_name="test",
        )
        assert rm.uri == "file:///data.json"
        assert rm.name == "data"
        assert rm.mime_type == "application/json"

    def test_to_dict_and_from_dict(self):
        rm = ResourceMetadata(
            uri="file:///data.csv",
            name="csv_data",
            description="CSV data",
            mime_type="text/csv",
            server_name="analytics",
        )
        d = rm.to_dict()
        rm2 = ResourceMetadata.from_dict(d)
        assert rm2.uri == rm.uri
        assert rm2.name == rm.name
        assert rm2.mime_type == rm.mime_type
        assert rm2.server_name == rm.server_name

    def test_from_dict_missing_fields(self):
        rm = ResourceMetadata.from_dict({"uri": "file:///x"})
        assert rm.uri == "file:///x"
        assert rm.name == ""
        assert rm.mime_type == ""


class TestPromptMetadata:
    """Tests for PromptMetadata data model."""

    def test_create(self):
        pm = PromptMetadata(
            name="review",
            description="Code review prompt",
            arguments=[{"name": "code", "required": True}],
            server_name="reviewer",
        )
        assert pm.name == "review"
        assert len(pm.arguments) == 1

    def test_to_dict_and_from_dict(self):
        pm = PromptMetadata(
            name="summarize",
            description="Summarize text",
            arguments=[
                {"name": "text", "description": "Text to summarize", "required": True},
                {"name": "length", "description": "Max length", "required": False},
            ],
            server_name="writer",
        )
        d = pm.to_dict()
        pm2 = PromptMetadata.from_dict(d)
        assert pm2.name == pm.name
        assert len(pm2.arguments) == 2
        assert pm2.arguments[0]["name"] == "text"


class TestMCPMetadataCacheResources:
    """Tests for MCPMetadataCache resource operations."""

    def _make_cache(self, tmp_path: Path) -> MCPMetadataCache:
        return MCPMetadataCache(cache_path=tmp_path / "test-cache.json")

    def _make_server_with_resources(
        self, cache: MCPMetadataCache, name: str = "test"
    ) -> None:
        tools = [ToolMetadata(name=f"mcp_{name}_tool1", original_name="tool1", description="T1", input_schema={}, server_name=name)]
        resources = [
            ResourceMetadata(uri="file:///data.json", name="data", description="Data", mime_type="application/json", server_name=name),
            ResourceMetadata(uri="file:///config.yaml", name="config", description="Config", mime_type="text/yaml", server_name=name),
        ]
        cache.update_server(name, tools, {"command": "test"}, resources=resources)

    def test_list_server_resources(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_resources(cache, "srv1")
        resources = cache.list_server_resources("srv1")
        assert len(resources) == 2
        assert resources[0].uri == "file:///data.json"

    def test_list_all_resources(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_resources(cache, "srv1")
        self._make_server_with_resources(cache, "srv2")
        all_resources = cache.list_all_resources()
        assert len(all_resources) == 4

    def test_get_resource(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_resources(cache, "srv1")
        rm = cache.get_resource("srv1", "file:///data.json")
        assert rm is not None
        assert rm.name == "data"

    def test_get_resource_not_found(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_resources(cache, "srv1")
        rm = cache.get_resource("srv1", "file:///nonexistent")
        assert rm is None

    def test_search_resources(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_resources(cache, "srv1")
        results = cache.search_resources("data")
        assert len(results) == 1
        assert results[0].name == "data"

    def test_search_resources_regex(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_resources(cache, "srv1")
        results = cache.search_resources(r"\.yaml$", regex=True)
        assert len(results) == 1
        assert results[0].name == "config"

    def test_total_resources(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_resources(cache, "srv1")
        assert cache.total_resources == 2

    def test_resources_persist_across_loads(self, tmp_path: Path):
        cache_path = tmp_path / "persist-cache.json"
        cache1 = MCPMetadataCache(cache_path=cache_path)
        self._make_server_with_resources(cache1, "srv1")

        # Load again from disk
        cache2 = MCPMetadataCache(cache_path=cache_path)
        resources = cache2.list_server_resources("srv1")
        assert len(resources) == 2


class TestMCPMetadataCachePrompts:
    """Tests for MCPMetadataCache prompt operations."""

    def _make_cache(self, tmp_path: Path) -> MCPMetadataCache:
        return MCPMetadataCache(cache_path=tmp_path / "test-cache.json")

    def _make_server_with_prompts(
        self, cache: MCPMetadataCache, name: str = "test"
    ) -> None:
        tools = [ToolMetadata(name=f"mcp_{name}_tool1", original_name="tool1", description="T1", input_schema={}, server_name=name)]
        prompts = [
            PromptMetadata(name="review", description="Review code", arguments=[{"name": "code", "required": True}], server_name=name),
            PromptMetadata(name="summarize", description="Summarize", arguments=[], server_name=name),
        ]
        cache.update_server(name, tools, {"command": "test"}, prompts=prompts)

    def test_list_server_prompts(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_prompts(cache, "srv1")
        prompts = cache.list_server_prompts("srv1")
        assert len(prompts) == 2
        assert prompts[0].name == "review"

    def test_list_all_prompts(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_prompts(cache, "srv1")
        self._make_server_with_prompts(cache, "srv2")
        all_prompts = cache.list_all_prompts()
        assert len(all_prompts) == 4

    def test_get_prompt(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_prompts(cache, "srv1")
        pm = cache.get_prompt("srv1", "review")
        assert pm is not None
        assert pm.name == "review"
        assert len(pm.arguments) == 1

    def test_get_prompt_not_found(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_prompts(cache, "srv1")
        pm = cache.get_prompt("srv1", "nonexistent")
        assert pm is None

    def test_search_prompts(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_prompts(cache, "srv1")
        results = cache.search_prompts("review")
        assert len(results) == 1
        assert results[0].name == "review"

    def test_total_prompts(self, tmp_path: Path):
        cache = self._make_cache(tmp_path)
        self._make_server_with_prompts(cache, "srv1")
        assert cache.total_prompts == 2

    def test_prompts_persist_across_loads(self, tmp_path: Path):
        cache_path = tmp_path / "persist-cache.json"
        cache1 = MCPMetadataCache(cache_path=cache_path)
        self._make_server_with_prompts(cache1, "srv1")

        cache2 = MCPMetadataCache(cache_path=cache_path)
        prompts = cache2.list_server_prompts("srv1")
        assert len(prompts) == 2


class TestMCPMetadataCacheCombined:
    """Tests for MCPMetadataCache with tools + resources + prompts together."""

    def test_update_server_with_all(self, tmp_path: Path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [ToolMetadata(name="mcp_s_tool", original_name="tool", description="T", input_schema={}, server_name="s")]
        resources = [ResourceMetadata(uri="file:///r", name="r", description="", mime_type="", server_name="s")]
        prompts = [PromptMetadata(name="p", description="", arguments=[], server_name="s")]
        cache.update_server("s", tools, {"command": "test"}, resources=resources, prompts=prompts)

        smeta = cache.get_server("s")
        assert smeta is not None
        assert len(smeta.tools) == 1
        assert len(smeta.resources) == 1
        assert len(smeta.prompts) == 1
        assert cache.total_tools == 1
        assert cache.total_resources == 1
        assert cache.total_prompts == 1

    def test_update_preserves_resources_when_not_provided(self, tmp_path: Path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [ToolMetadata(name="mcp_s_tool", original_name="tool", description="T", input_schema={}, server_name="s")]
        resources = [ResourceMetadata(uri="file:///r", name="r", description="", mime_type="", server_name="s")]
        prompts = [PromptMetadata(name="p", description="", arguments=[], server_name="s")]

        # First update with resources and prompts
        cache.update_server("s", tools, {"command": "test"}, resources=resources, prompts=prompts)

        # Second update with only tools — resources/prompts should be preserved
        cache.update_server("s", tools, {"command": "test"})
        smeta = cache.get_server("s")
        assert len(smeta.resources) == 1
        assert len(smeta.prompts) == 1

    def test_server_metadata_serialization_roundtrip(self, tmp_path: Path):
        cache_path = tmp_path / "roundtrip-cache.json"
        cache1 = MCPMetadataCache(cache_path=cache_path)

        tools = [ToolMetadata(name="mcp_s_t", original_name="t", description="T", input_schema={"type": "object"}, server_name="s")]
        resources = [ResourceMetadata(uri="file:///data", name="data", description="D", mime_type="text/plain", server_name="s")]
        prompts = [PromptMetadata(name="p", description="P", arguments=[{"name": "x", "required": True}], server_name="s")]

        cache1.update_server("s", tools, {"command": "test"}, resources=resources, prompts=prompts)

        # Reload from disk
        cache2 = MCPMetadataCache(cache_path=cache_path)
        smeta = cache2.get_server("s")
        assert smeta is not None
        assert len(smeta.tools) == 1
        assert len(smeta.resources) == 1
        assert len(smeta.prompts) == 1
        assert smeta.resources[0].uri == "file:///data"
        assert smeta.prompts[0].arguments[0]["name"] == "x"
