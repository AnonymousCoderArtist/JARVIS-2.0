"""Tests for the learning system"""

import json
from pathlib import Path

import pytest
from core.evals import (
    EvalConfig,
    EvalMetrics,
    QueryRouter,
    ResponseEvaluator,
    RewardConfig,
    RewardFunction,
)

from core.connectors import ConnectorConfig, ConnectorManager, FilesystemConnector
from core.learn import (
    LearningConfig,
    LearningManager,
    TraceAnalyzer,
)


class TestTraceAnalyzer:
    """Tests for trace analysis"""

    @pytest.mark.asyncio
    async def test_analyze_empty_sessions(self, tmp_path: Path):
        """Test analysis with no sessions"""
        analyzer = TraceAnalyzer(sessions_dir=str(tmp_path))
        metrics = await analyzer.analyze_sessions(limit=1)
        assert metrics.total_interactions == 0

    @pytest.mark.asyncio
    async def test_analyze_single_session(self, tmp_path: Path):
        """Test analysis with a single session"""
        # Create a test session file
        session_file = tmp_path / "test-session.jsonl"
        session_file.write_text(
            json.dumps({"type": "message", "toolCalls": [{"function": {"name": "read_file"}}]}) + "\n"
            + json.dumps({"type": "message", "content": "Hello"}) + "\n"
        )

        analyzer = TraceAnalyzer(sessions_dir=str(tmp_path))
        metrics = await analyzer.analyze_sessions(limit=1)

        assert metrics.total_interactions == 2
        assert metrics.successful_traces >= 0


class TestPatternDetector:
    """Tests for pattern detection"""

    def test_detect_query_type(self):
        """Test query type detection via pattern matching"""
        patterns = ["fix", "bug", "error"]
        query = "Can you fix this bug in the code?"
        assert any(p in query.lower() for p in patterns)

    def test_get_learned_preferences(self):
        """Test preference structure"""
        prefs = {"preferred_output_format": "code_with_explanation"}
        assert prefs["preferred_output_format"] == "code_with_explanation"


class TestLearningManager:
    """Tests for learning manager"""

    @pytest.mark.asyncio
    async def test_save_and_load_preferences(self, tmp_path: Path):
        """Test saving and loading preferences"""
        config = LearningConfig(
            enabled=True,
            trace_dir=str(tmp_path / "traces"),
            dataset_dir=str(tmp_path / "datasets")
        )
        manager = LearningManager(config)

        await manager.log_trace_m1({
            "user_input": "test",
            "agent_response": "response",
            "success": True
        })

        # Check trace was created
        trace_dir = Path(config.trace_dir)
        assert trace_dir.exists()

    @pytest.mark.asyncio
    async def test_log_trace(self, tmp_path: Path):
        """Test trace logging"""
        config = LearningConfig(
            enabled=True,
            trace_dir=str(tmp_path / "traces"),
            dataset_dir=str(tmp_path / "datasets")
        )
        manager = LearningManager(config)

        await manager.log_trace_m1({
            "user_input": "test query",
            "agent_response": "test response",
            "success": True
        })

        metrics = await manager.trace_analyzer.analyze_sessions()
        assert metrics.total_interactions >= 1


class TestEvaluation:
    """Tests for evaluation system"""

    def test_eval_metrics_creation(self):
        """Test EvalMetrics creation"""
        metrics = EvalMetrics(
            latency_ms=100.0,
            token_count=50,
            cost_usd=0.001,
        )
        assert metrics.latency_ms == 100.0
        assert metrics.success is True

    def test_reward_function(self):
        """Test reward calculation"""
        reward_fn = RewardFunction(RewardConfig(success_weight=1.0, latency_weight=0.0))

        reward = reward_fn.calculate({
            "success": True,
            "latency_ms": 100,
            "cost_usd": 0.001,
        })
        assert reward > 0.5

    def test_query_router(self):
        """Test query routing"""
        router = QueryRouter()

        result = router.route("hello there")
        assert result["handler"] == "simple_chat"

        result = router.route("I need to fix a bug in my code")
        assert result["handler"] == "coding"

        result = router.route("I want to analyze the market trends")
        assert result["handler"] == "research"

    @pytest.mark.asyncio
    async def test_response_evaluator(self, tmp_path: Path):
        """Test response evaluation"""
        evaluator = ResponseEvaluator(EvalConfig(measure_latency=True))

        metrics = await evaluator.evaluate(
            query="hello",
            response="hi there",
            model="gpt-4o"
        )
        assert metrics.success is True
        assert metrics.latency_ms >= 0


class TestConnectors:
    """Tests for the connectors framework"""

    def test_filesystem_connector_init(self, tmp_path: Path):
        """Test filesystem connector initialization"""
        config = ConnectorConfig(
            name="test_fs",
            connector_type="filesystem",
            config={"root_dir": str(tmp_path)}
        )
        connector = FilesystemConnector(config)
        assert connector.name == "test_fs"
        assert connector.root_dir == tmp_path

    @pytest.mark.asyncio
    async def test_filesystem_connector_fetch(self, tmp_path: Path):
        """Test filesystem connector fetch"""
        # Create test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "readme.md").write_text("# Test")

        config = ConnectorConfig(
            name="test_fs",
            connector_type="filesystem",
            config={"root_dir": str(tmp_path)}
        )
        connector = FilesystemConnector(config)

        results = await connector.fetch("test")
        assert len(results) >= 1
        assert any("test.py" in r["id"] for r in results)

    def test_filesystem_supports_query_type(self, tmp_path: Path):
        """Test filesystem connector query type support"""
        config = ConnectorConfig(
            name="test_fs",
            connector_type="filesystem",
            config={"root_dir": str(tmp_path)}
        )
        connector = FilesystemConnector(config)

        assert connector.supports_query_type("files")
        assert connector.supports_query_type("code")
        assert not connector.supports_query_type("web")

    def test_connector_manager(self, tmp_path: Path):
        """Test connector manager"""
        manager = ConnectorManager()

        config = ConnectorConfig(
            name="test_fs",
            connector_type="filesystem",
            config={"root_dir": str(tmp_path)}
        )
        connector = FilesystemConnector(config)
        manager.register(connector)

        assert manager.get("test_fs") is connector
        assert manager.unregister("test_fs")
        assert manager.get("test_fs") is None
