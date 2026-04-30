"""Plan offer decision."""

from dataclasses import dataclass


@dataclass
class PlanInfo:
    """Plan info."""
    pass


def decide_plan_offer() -> PlanInfo | None:
    """Decide plan offer."""
    return None


def plan_offer_cta() -> str:
    """Plan offer CTA."""
    return ""


def plan_title() -> str:
    """Plan title."""
    return ""


def resolve_api_key_for_plan() -> str | None:
    """Resolve API key for plan."""
    return None
