"""Agents package for Meta Script — lightweight stubs for frontend/backend agents.
These are small, deterministic implementations intended as placeholders for the
real agent systems described in the spec. Import modules directly (e.g.
`from metascript.agents import frontend_agent`).
"""
from . import frontend_agent, backend_agent
__all__ = ["frontend_agent", "backend_agent"]
