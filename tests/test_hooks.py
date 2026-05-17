"""Tests for the hook system — registration, execution, blocking, modification, injection."""

import pytest

from jarvis.core.events.hooks import HookContext, HookRegistry, HookResult, HookStage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry():
    """Fresh HookRegistry for each test."""
    return HookRegistry()


@pytest.fixture
def ctx():
    """Default HookContext."""
    return HookContext()


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_decorator(self, registry):
        @registry.register(HookStage.BEFORE_TOOL_CALL)
        async def handler(ctx):
            return HookResult(proceed=True)

        assert registry.total_handlers == 1
        assert "handler" in registry.get_handlers()[HookStage.BEFORE_TOOL_CALL.value]

    def test_register_direct(self, registry):
        async def handler(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, handler)
        assert registry.total_handlers == 1

    def test_register_duplicate_ignored(self, registry):
        async def handler(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, handler)
        registry.register(HookStage.BEFORE_TOOL_CALL, handler)
        assert registry.total_handlers == 1

    def test_unregister(self, registry):
        async def handler(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, handler)
        registry.unregister(HookStage.BEFORE_TOOL_CALL, handler)
        assert registry.total_handlers == 0

    def test_clear(self, registry):
        async def h1(ctx):
            return HookResult(proceed=True)

        async def h2(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, h1)
        registry.register(HookStage.AFTER_TOOL_CALL, h2)
        assert registry.total_handlers == 2

        registry.clear()
        assert registry.total_handlers == 0


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------

class TestExecution:
    @pytest.mark.asyncio
    async def test_no_handlers_returns_proceed(self, registry, ctx):
        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        assert result.proceed is True
        assert result.block is False

    @pytest.mark.asyncio
    async def test_sync_handler(self, registry, ctx):
        def handler(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, handler)
        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        assert result.proceed is True

    @pytest.mark.asyncio
    async def test_async_handler(self, registry, ctx):
        async def handler(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, handler)
        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        assert result.proceed is True

    @pytest.mark.asyncio
    async def test_handler_exception_logged_continues(self, registry, ctx):
        call_order = []

        async def bad_handler(ctx):
            call_order.append("bad")
            raise ValueError("boom")

        async def good_handler(ctx):
            call_order.append("good")
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, bad_handler)
        registry.register(HookStage.BEFORE_TOOL_CALL, good_handler)

        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        assert result.proceed is True
        assert call_order == ["bad", "good"]


# ---------------------------------------------------------------------------
# Blocking tests
# ---------------------------------------------------------------------------

class TestBlocking:
    @pytest.mark.asyncio
    async def test_block_stops_execution(self, registry, ctx):
        call_order = []

        async def blocker(ctx):
            call_order.append("blocker")
            return HookResult(block=True, reason="blocked")

        async def never_called(ctx):
            call_order.append("never")
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, blocker)
        registry.register(HookStage.BEFORE_TOOL_CALL, never_called)

        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        assert result.block is True
        assert result.reason == "blocked"
        assert call_order == ["blocker"]

    @pytest.mark.asyncio
    async def test_block_short_circuits(self, registry, ctx):
        async def first(ctx):
            return HookResult(proceed=True)

        async def second(ctx):
            return HookResult(block=True, reason="stop")

        async def third(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, first)
        registry.register(HookStage.BEFORE_TOOL_CALL, second)
        registry.register(HookStage.BEFORE_TOOL_CALL, third)

        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        assert result.block is True
        assert result.reason == "stop"


# ---------------------------------------------------------------------------
# Modification tests
# ---------------------------------------------------------------------------

class TestModification:
    @pytest.mark.asyncio
    async def test_modify_args(self, registry, ctx):
        async def modifier(ctx):
            return HookResult(proceed=True, modify={"extra": "value"})

        registry.register(HookStage.BEFORE_TOOL_CALL, modifier)
        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        assert result.modify == {"extra": "value"}

    @pytest.mark.asyncio
    async def test_multiple_modifiers_accumulate(self, registry, ctx):
        async def mod1(ctx):
            return HookResult(proceed=True, modify={"a": 1})

        async def mod2(ctx):
            return HookResult(proceed=True, modify={"b": 2})

        registry.register(HookStage.BEFORE_TOOL_CALL, mod1)
        registry.register(HookStage.BEFORE_TOOL_CALL, mod2)

        result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
        # Last modifier's modify wins (current behavior)
        assert result.modify == {"b": 2}


# ---------------------------------------------------------------------------
# Injection tests
# ---------------------------------------------------------------------------

class TestInjection:
    @pytest.mark.asyncio
    async def test_inject_content(self, registry, ctx):
        async def injector(ctx):
            return HookResult(proceed=True, inject="extra content")

        registry.register(HookStage.AFTER_TOOL_CALL, injector)
        result = await registry.run(HookStage.AFTER_TOOL_CALL, ctx)
        assert result.inject == "extra content"

    @pytest.mark.asyncio
    async def test_last_inject_wins(self, registry, ctx):
        async def inj1(ctx):
            return HookResult(proceed=True, inject="first")

        async def inj2(ctx):
            return HookResult(proceed=True, inject="second")

        registry.register(HookStage.AFTER_TOOL_CALL, inj1)
        registry.register(HookStage.AFTER_TOOL_CALL, inj2)

        result = await registry.run(HookStage.AFTER_TOOL_CALL, ctx)
        assert result.inject == "second"


# ---------------------------------------------------------------------------
# Introspection tests
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_get_handlers_all(self, registry):
        async def h1(ctx):
            return HookResult(proceed=True)

        async def h2(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, h1)
        registry.register(HookStage.AFTER_TOOL_CALL, h2)

        handlers = registry.get_handlers()
        assert "before_tool_call" in handlers
        assert "after_tool_call" in handlers
        assert "h1" in handlers["before_tool_call"]
        assert "h2" in handlers["after_tool_call"]

    def test_get_handlers_filtered(self, registry):
        async def h1(ctx):
            return HookResult(proceed=True)

        async def h2(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, h1)
        registry.register(HookStage.AFTER_TOOL_CALL, h2)

        handlers = registry.get_handlers(HookStage.BEFORE_TOOL_CALL)
        assert "before_tool_call" in handlers
        assert "after_tool_call" not in handlers

    def test_total_handlers(self, registry):
        async def h1(ctx):
            return HookResult(proceed=True)

        async def h2(ctx):
            return HookResult(proceed=True)

        async def h3(ctx):
            return HookResult(proceed=True)

        registry.register(HookStage.BEFORE_TOOL_CALL, h1)
        registry.register(HookStage.BEFORE_TOOL_CALL, h2)
        registry.register(HookStage.AFTER_TOOL_CALL, h3)

        assert registry.total_handlers == 3
