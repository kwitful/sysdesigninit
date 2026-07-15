"""ADK entry point.

ADK looks for a module-level ``root_agent`` here. The real pipeline
(coordinator + seven specialists + two parallel groups + index agent) is
constructed in :mod:`sys_des_in.agents.orchestrator`.
"""
from .agents import root_agent

__all__ = ["root_agent"]
