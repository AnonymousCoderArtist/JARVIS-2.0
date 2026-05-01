from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jarvis import __version__
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

from core.config.settings import Settings
from interface.textual_ui.widgets.banner.petit_chat import PetitChat
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.agent_loop import SkillManagerAdapter


def _pluralize(count: int, singular: str) -> str:
    return f"{count} {singular}{'s' if count != 1 else ''}"


@dataclass
class BannerState:
    active_model: str = ""
    skills_count: int = 0
    connectors_count: int = 0
    plan_description: str = ""


class Banner(Static):
    state = reactive(BannerState(), init=False)

    def __init__(
        self,
        config: Settings,
        skill_manager: SkillManagerAdapter,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.can_focus = False
        self._initial_state = self._build_state(
            config=config,
            skill_manager=skill_manager,
            connectors_count=0,
            plan_description="",
            model=model,
        )
        self._animated = True

    def compose(self) -> ComposeResult:
        with Horizontal(id="banner-container"):
            yield PetitChat(animate=self._animated)

            with Vertical(id="banner-info"):
                with Horizontal(classes="banner-line"):
                    yield NoMarkupStatic("JARVIS Agent", id="banner-brand")
                    yield NoMarkupStatic(" ", classes="banner-spacer")
                    yield NoMarkupStatic(f"v{__version__} · ", classes="banner-meta")
                    yield NoMarkupStatic("", id="banner-model")
                with Horizontal(classes="banner-line"):
                    yield NoMarkupStatic("", id="banner-meta-counts")
                with Horizontal(classes="banner-line"):
                    yield NoMarkupStatic("Made by @OEvortex", id="banner-attribution")

    def on_mount(self) -> None:
        self.state = self._initial_state

    def watch_state(self) -> None:
        if not self.is_attached:
            return
        self.query_one("#banner-model", NoMarkupStatic).update(self.state.active_model)
        self.query_one("#banner-meta-counts", NoMarkupStatic).update(
            self._format_meta_counts()
        )

    def freeze_animation(self) -> None:
        if self._animated:
            self.query_one(PetitChat).freeze_animation()

    def set_state(
        self,
        config: Settings,
        skill_manager: SkillManagerAdapter,
        mcp_registry: Any = None,
        connectors_count: int = 0,
        plan_description: str = "",
        model: str | None = None,
    ) -> None:
        self.state = self._build_state(
            config, skill_manager, connectors_count, plan_description, model
        )

    @staticmethod
    def _build_state(
        config: Settings,
        skill_manager: SkillManagerAdapter,
        connectors_count: int = 0,
        plan_description: str = "",
        model: str | None = None,
    ) -> BannerState:
        # Use provided model or try to get from config
        if model:
            model_name = model
        else:
            model_name = getattr(config, "model", "gpt-4o")
            if not isinstance(model_name, str):
                model_name = config.get("model", "selected", {}).get("id", "gpt-4o")

        return BannerState(
            active_model=model_name,  # Keep full model name as requested
            skills_count=skill_manager.custom_skills_count,
            connectors_count=connectors_count,
            plan_description=plan_description,
        )

    def _format_meta_counts(self) -> str:
        parts = [_pluralize(self.state.skills_count, "skill")]
        parts.append(_pluralize(self.state.connectors_count, "connector"))
        if self.state.plan_description:
            parts.append(self.state.plan_description)
        return " · ".join(parts)
