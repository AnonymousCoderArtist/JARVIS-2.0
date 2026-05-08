"""Learning manager - OpenJarvis Spec-Level Distillation Pipeline (M1 -> M2 -> M3)"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .trace_analyzer import TraceAnalyzer


@dataclass
class LearningConfig:
    """Configuration for the OpenJarvis learning system"""
    enabled: bool = True
    trace_dir: str = str(Path.home() / ".jarvis" / "traces")
    dataset_dir: str = str(Path.home() / ".jarvis" / "datasets")
    min_traces_for_distillation: int = 50
    enable_dspy_optimization: bool = True

class LearningManager:
    """Manages the OpenJarvis M1->M2->M3 Learning Loop"""

    def __init__(self, config: LearningConfig | None = None):
        self.config = config or LearningConfig()
        self.trace_analyzer = TraceAnalyzer(sessions_dir=self.config.trace_dir)
        self._running = False

        # Ensure directories exist
        Path(self.config.trace_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.dataset_dir).mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start the continuous learning loop"""
        self._running = True
        await self._run_learning_cycle()

    async def log_trace_m1(self, session_data: dict[str, Any]) -> None:
        """M1 Stage: Log high-quality traces from the teacher model (e.g., GPT-4)"""
        if not self.config.enabled:
            return

        trace_file = Path(self.config.trace_dir) / f"trace_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(trace_file, 'a') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "trajectory": session_data,
                "reward": session_data.get("success", False)
            }, f)
            f.write('\n')

    async def _run_learning_cycle(self) -> None:
        """Execute the M1 -> M2 -> M3 pipeline"""
        # 1. Analyze traces to see if we have enough high-quality data
        metrics = await self.trace_analyzer.analyze_sessions()

        if metrics.total_interactions < self.config.min_traces_for_distillation:
            print(f"Not enough traces for distillation ({metrics.total_interactions}/{self.config.min_traces_for_distillation})")
            return

        # 2. DSPy Optimization: Optimize tool usage policies based on traces
        if self.config.enable_dspy_optimization:
            await self._run_dspy_optimization()

        # 3. M2 Stage: Generate instruction-tuning dataset from M1 traces
        dataset_path = await self._generate_m2_dataset()

        # 4. M3 Stage: Trigger local distillation/fine-tuning (placeholder for local trainer)
        await self._trigger_m3_distillation(dataset_path)

    async def _run_dspy_optimization(self) -> None:
        """Apply DSPy-style teleprompter to optimize tool-use policies"""
        # In a full OpenJarvis implementation, this hooks into DSPy to refine the system prompt
        # based on past successful vs failed tool traces.
        print("Running DSPy trace optimization...")
        patterns = await self.trace_analyzer.extract_successful_tool_patterns()

        # Save optimized policies
        policy_path = Path(self.config.dataset_dir) / "optimized_policy.json"
        with open(policy_path, 'w') as f:
            json.dump({"optimized_patterns": patterns}, f, indent=2)

    async def _generate_m2_dataset(self) -> Path:
        """M2 Stage: Convert raw traces into an instruction-tuning dataset"""
        print("Generating M2 Instruction Dataset...")
        dataset_path = Path(self.config.dataset_dir) / "m2_instructions.jsonl"

        # Filter for successful traces only
        successful_traces = await self.trace_analyzer.get_successful_traces()

        with open(dataset_path, 'w') as f:
            for trace in successful_traces:
                instruction_data = {
                    "instruction": trace.get("user_input", ""),
                    "output": trace.get("agent_response", ""),
                    "system": "You are a local-first Personal AI."
                }
                json.dump(instruction_data, f)
                f.write('\n')

        return dataset_path

    async def _trigger_m3_distillation(self, dataset_path: Path) -> None:
        """M3 Stage: Trigger local model fine-tuning (distillation)"""
        # This would interface with local llama.cpp or MLX for LoRA fine-tuning
        print(f"M3 Distillation triggered using dataset: {dataset_path}")
        # MLX/llama.cpp training loop integration goes here
        pass

    @property
    def is_enabled(self) -> bool:
        return self.config.enabled and self._running

    async def load_preferences(self) -> dict[str, Any]:
        """Load learned preferences from disk."""
        pref_file = Path(self.config.dataset_dir) / "preferences.json"
        if pref_file.exists():
            with open(pref_file) as f:
                return json.load(f)
        return {"preferred_output_format": "code_with_explanation", "preferred_tools": []}

    async def save_preferences(self, preferences: dict[str, Any]) -> None:
        """Save learned preferences to disk."""
        pref_file = Path(self.config.dataset_dir) / "preferences.json"
        pref_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pref_file, 'w') as f:
            json.dump(preferences, f, indent=2)
