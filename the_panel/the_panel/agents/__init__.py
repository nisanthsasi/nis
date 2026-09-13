"""Agents: render → call → validate → one repair retry → persist.

Each agent is a thin, schema-bound wrapper over one prompt template. Orchestration lives
in :mod:`the_panel.orchestrator`; agents never call each other.
"""
from .base import AgentContext, AgentResult, BaseAgent, ValidationRejected

__all__ = ["AgentContext", "AgentResult", "BaseAgent", "ValidationRejected"]
