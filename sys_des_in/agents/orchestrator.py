"""Definition of every agent in the system-design pipeline.

The pipeline is a single ``SequentialAgent`` (the ``root_agent``) whose
sub-agents are a mix of ``LlmAgent`` specialists and two ``ParallelAgent``
groups:

    1. coordinator            (LlmAgent)        -> design_context
    2. requirements_agent     (LlmAgent)        -> 01-requirements.md
    3. architecture_agent     (LlmAgent)        -> 02-architecture.md
    4. api_and_data           (ParallelAgent)
         - api_agent                              -> 03-api.md
         - data_agent                              -> 04-data-model.md
    5. component_agent        (LlmAgent)        -> 05-component-design.md
    6. hardening              (ParallelAgent)
         - resilience_agent                        -> 06-resilience.md
         - security_agent                          -> 07-security-ops.md
    7. index_agent            (LlmAgent)        -> 00-index.md

Each specialist agent has an ``output_key`` so its full markdown lands in shared
session state, and downstream agents reference those keys via ``{key}``
substitution in their instructions. Every specialist also has the file tools
available so it can persist its document to disk.
"""

from __future__ import annotations

import re

from google.adk.agents import (
    Agent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.tools.function_tool import FunctionTool

from ..tools import (
    init_design_workspace,
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

# All agents share the same model. `gemini-flash-latest` is an alias that
# always points to the current Flash model (per ADK quickstart docs). Fast and
# cheap enough for the orchestrator; specialists do the heavy lifting.
_MODEL = "gemini-flash-latest"

# The file tools every specialist gets. ADK wraps plain functions into
# FunctionTool instances automatically when passed via the `tools` list, but we
# wrap explicitly for clarity and to keep type checkers happy.
_FILE_TOOLS = [
    FunctionTool(func=init_design_workspace),
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
    instruction = build_specialist_instruction(
        section_title=title,
        schema_body=schema_body,
        filename=filename,
        prior_context_keys=prior_keys,
    )
    return Agent(
        name=_sanitize_name(title),
        model=_MODEL,
        description=f"Writes the {title} markdown document for a system design.",
        instruction=instruction,
        tools=_FILE_TOOLS,
        output_key=output_key,
    )


# --- Coordinator -----------------------------------------------------------
coordinator_agent = Agent(
    name="design_coordinator",
    model=_MODEL,
    description=(
        "Runs first. Clarifies scope, scale, and maturity, creates the "
        "workspace, and emits a compact design context for the specialists."
    ),
    instruction=COORDINATOR_OUTPUT_CONTRACT,
    tools=[FunctionTool(func=init_design_workspace)],
    output_key="design_context",
)

# --- Specialists (built in pipeline order) ---------------------------------
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

# --- Parallel groups -------------------------------------------------------
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

# --- Final index agent -----------------------------------------------------
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

# --- Root orchestrator -----------------------------------------------------
# A SequentialAgent runs its sub_agents in order, passing the same invocation
# context (and thus the same session state) through the chain. The two
# ParallelAgent groups fan out where the work is independent.
root_agent = SequentialAgent(
    name="system_design_pipeline",
    sub_agents=[
        coordinator_agent,
        requirements_agent,
        architecture_agent,
        api_and_data,
        component_agent,
        hardening,
        index_agent,
    ],
)
