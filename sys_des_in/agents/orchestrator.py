"""Definition of every agent in the system-design assistant.

Architecture (ADK-aligned):

* ``root_agent`` is a conversational ``LlmAgent`` (the coordinator). It
  clarifies with the user across turns, then invokes the document pipeline
  via ``AgentTool`` — never while still waiting for answers.
* ``design_pipeline`` is a ``SequentialAgent`` of specialists (+ two
  ``ParallelAgent`` groups) that writes the eight markdown files.

Session state handoff (via ToolContext tools):

* ``workspace`` — set by ``init_design_workspace``
* ``design_context`` — set by ``save_design_context``

Models come from ``sys_des_in.models.get_model()`` (Gemini by default, or
OpenRouter / LiteLLM via ADK's ``LiteLlm`` wrapper).
"""

from __future__ import annotations

import re

from google.adk.agents import (
    Agent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.tools import agent_tool
from google.adk.tools.function_tool import FunctionTool

from ..models import get_model
from ..tools import (
    init_design_workspace,
    save_design_context,
    write_design_doc,
    read_design_doc,
    list_design_docs,
)
from .prompts import (
    COORDINATOR_OUTPUT_CONTRACT,
    SECTION_SPECS,
    build_specialist_instruction,
    build_index_instruction,
)

# Resolve once at import time so every agent shares the same configured model.
_MODEL = get_model()

_FILE_TOOLS = [
    FunctionTool(func=write_design_doc),
    FunctionTool(func=read_design_doc),
    FunctionTool(func=list_design_docs),
]


def _sanitize_name(title: str) -> str:
    """Turn a section title into a valid Python-identifier agent name."""
    name = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()
    return f"{name}_agent"


def _build_specialist(spec_index: int, prior_keys: list[str]) -> Agent:
    """Construct one specialist LlmAgent from SECTION_SPECS."""
    filename, output_key, title, schema_body = SECTION_SPECS[spec_index]
    # Always surface workspace so write_design_doc gets a concrete name.
    keys = list(dict.fromkeys(["workspace", *prior_keys]))
    instruction = build_specialist_instruction(
        section_title=title,
        schema_body=schema_body,
        filename=filename,
        prior_context_keys=keys,
    )
    return Agent(
        name=_sanitize_name(title),
        model=_MODEL,
        description=f"Writes the {title} markdown document for a system design.",
        instruction=instruction,
        tools=_FILE_TOOLS,
        output_key=output_key,
    )


# --- Specialists (pipeline order) ------------------------------------------
requirements_agent = _build_specialist(0, prior_keys=["design_context"])

architecture_agent = _build_specialist(
    1, prior_keys=["design_context", "requirements_doc"]
)

api_agent = _build_specialist(
    2, prior_keys=["design_context", "requirements_doc", "architecture_doc"]
)
data_agent = _build_specialist(
    3, prior_keys=["design_context", "requirements_doc", "architecture_doc"]
)

component_agent = _build_specialist(
    4,
    prior_keys=[
        "design_context",
        "requirements_doc",
        "architecture_doc",
        "api_doc",
        "data_doc",
    ],
)

resilience_agent = _build_specialist(
    5,
    prior_keys=[
        "design_context",
        "requirements_doc",
        "architecture_doc",
        "component_doc",
    ],
)
security_agent = _build_specialist(
    6,
    prior_keys=[
        "design_context",
        "requirements_doc",
        "architecture_doc",
        "component_doc",
    ],
)

api_and_data = ParallelAgent(
    name="api_and_data_parallel",
    sub_agents=[api_agent, data_agent],
    description="Writes the API and data-model documents in parallel.",
)

hardening = ParallelAgent(
    name="hardening_parallel",
    sub_agents=[resilience_agent, security_agent],
    description="Writes the resilience and security/ops documents in parallel.",
)

index_agent = Agent(
    name="index_agent",
    model=_MODEL,
    description=(
        "Runs last. Reads the seven section files and writes a 00-index.md "
        "that ties the whole design together."
    ),
    instruction=build_index_instruction(),
    tools=_FILE_TOOLS,
    output_key="index_doc",
)

# Document pipeline only — no conversational coordinator inside.
# Invoked by the root coordinator through AgentTool after the brief is saved.
design_pipeline = SequentialAgent(
    name="run_design_pipeline",
    description=(
        "Generate all system-design markdown documents (requirements, "
        "architecture, API, data model, component design, resilience, "
        "security/ops, and index). Call ONLY after init_design_workspace and "
        "save_design_context have succeeded. Reads design_context and "
        "workspace from session state; takes no useful arguments."
    ),
    sub_agents=[
        requirements_agent,
        architecture_agent,
        api_and_data,
        component_agent,
        hardening,
        index_agent,
    ],
)

_pipeline_tool = agent_tool.AgentTool(agent=design_pipeline)

# --- Root: conversational coordinator --------------------------------------
root_agent = Agent(
    name="design_coordinator",
    model=_MODEL,
    description=(
        "System-design assistant. Clarifies scope with the user, then runs "
        "the document pipeline to write detailed markdown design docs."
    ),
    instruction=COORDINATOR_OUTPUT_CONTRACT,
    tools=[
        FunctionTool(func=init_design_workspace),
        FunctionTool(func=save_design_context),
        _pipeline_tool,
    ],
)
