"""Agent package: conversational coordinator (root) + document pipeline."""
from .orchestrator import design_pipeline, root_agent

__all__ = ["root_agent", "design_pipeline"]
