"""Built-in agent modules"""

from .jarvis_help_agent import JARVIS_HELP_AGENT, GetJarvisHelpPrompt, JarvisHelpAgent
from .rubber_duck_agent import RUBBER_DUCK_AGENT, GetRubberDuckPrompt, RubberDuckAgent
from .statusline_setup_agent import STATUSLINE_SETUP_AGENT, GetStatuslineSetupPrompt
from .verification_agent import VERIFICATION_AGENT, GetVerificationPrompt, VerificationAgent

__all__ = [
    "JarvisHelpAgent",
    "GetJarvisHelpPrompt",
    "JARVIS_HELP_AGENT",
    "RubberDuckAgent",
    "GetRubberDuckPrompt",
    "RUBBER_DUCK_AGENT",
    "GetStatuslineSetupPrompt",
    "STATUSLINE_SETUP_AGENT",
    "VerificationAgent",
    "GetVerificationPrompt",
    "VERIFICATION_AGENT",
]
