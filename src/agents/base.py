"""Shared construction logic for the CrewAI agents.

Agent roles, goals and backstories live in ``config/config.yaml`` under the
``agents`` key. This module turns those definitions into CrewAI ``Agent``
objects, falling back to the built-in defaults when the config is absent and
degrading gracefully when CrewAI itself cannot be constructed (for example when
no LLM credentials are available).
"""

import logging

from src.config import get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only by the import environment
    from crewai import Agent
except ImportError:  # pragma: no cover
    Agent = None
    logger.debug("crewai not installed - agents will run without a CrewAI persona")


def build_agent(config_key: str, role: str, goal: str, backstory: str):
    """Build the CrewAI persona for an agent, or None when unavailable.

    The persona carries the role/goal/backstory used for LLM-backed reasoning.
    Every agent in this project also works without it, so a failure here is
    logged and never fatal.
    """
    settings = get_settings()
    agent_cfg = settings.section("agents", config_key)

    role = agent_cfg.get("role", role)
    goal = agent_cfg.get("goal", goal)
    backstory = agent_cfg.get("backstory", backstory)
    verbose = bool(agent_cfg.get("verbose", False))

    if Agent is None:
        return None

    try:
        return Agent(role=role, goal=goal, backstory=backstory, verbose=verbose)
    except Exception as exc:
        logger.warning("Could not construct CrewAI agent '%s': %s", config_key, exc)
        return None
