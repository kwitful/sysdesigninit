"""System-design agentic assistant package.

ADK discovers the root agent via ``from . import agent`` (see ``agent.py``).
The actual pipeline is built in :mod:`sys_des_in.agents.orchestrator`.
"""
from . import agent  # noqa: F401  (side-effect: exposes root_agent to ADK)
