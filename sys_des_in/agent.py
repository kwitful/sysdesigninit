"""ADK entry point.

ADK looks for a module-level ``root_agent`` here. That agent is the
conversational coordinator; the markdown pipeline is invoked via AgentTool
(see :mod:`sys_des_in.agents.orchestrator`).
"""
from .agents import root_agent

__all__ = ["root_agent"]
