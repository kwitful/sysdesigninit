"""Definition of every agent in the system-design assistant.

Pipeline order (``design_pipeline`` SequentialAgent):

1. problem_brief        → 00-problem-brief.md
2. requirements         → 01-requirements.md
3. architecture         → 02-architecture.md
4. api_and_data         → 03-api.md, 04-data-model.md (parallel)
5. component            → 05-component-design.md
6. hardening            → 06-resilience.md, 07-security-ops.md (parallel)
7. decisions_log        → 08-decisions-log.md
8. capacity             → 09-capacity-estimates.md
9. review               → 00-review.md
10. index               → 00-index.md
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
    EXTRA_SPECS,
    SECTION_SPECS,
    build_specialist_instruction,
    build_index_instruction,
)

_MODEL = get_model()

_FILE_TOOLS = [
    FunctionTool(func=write_design_doc),
    FunctionTool(func=read_design_doc),
    FunctionTool(func=list_design_docs),
]


def _sanitize_name(title: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()
    return f"{name}_agent"


def _build_from_spec(
    filename: str,
    output_key: str,
    title: str,
    schema_body: str,
    prior_keys: list[str],
    *,
    include_focus_hint: bool = True,
) -> Agent:
    keys = list(dict.fromkeys(["workspace", "design_context", *prior_keys]))
    instruction = build_specialist_instruction(
        section_title=title,
        schema_body=schema_body,
        filename=filename,
        prior_context_keys=keys,
        include_focus_hint=include_focus_hint,
    )
    return Agent(
        name=_sanitize_name(title),
        model=_MODEL,
        description=f"Writes {filename} for a system design.",
        instruction=instruction,
        tools=_FILE_TOOLS,
        output_key=output_key,
    )


def _build_section(spec_index: int, prior_keys: list[str]) -> Agent:
    filename, output_key, title, schema_body = SECTION_SPECS[spec_index]
    return _build_from_spec(filename, output_key, title, schema_body, prior_keys)


def _build_extra(spec_index: int, prior_keys: list[str], **kwargs) -> Agent:
    filename, output_key, title, schema_body = EXTRA_SPECS[spec_index]
    return _build_from_spec(
        filename, output_key, title, schema_body, prior_keys, **kwargs
    )


# --- Pipeline agents -------------------------------------------------------
_BASE_PRIOR = ["problem_brief_doc"]

problem_brief_agent = _build_extra(
    0,
    prior_keys=[],
    include_focus_hint=False,
)

requirements_agent = _build_section(0, prior_keys=_BASE_PRIOR)

architecture_agent = _build_section(
    1, prior_keys=[*_BASE_PRIOR, "requirements_doc"]
)

api_agent = _build_section(
    2, prior_keys=[*_BASE_PRIOR, "requirements_doc", "architecture_doc"]
)
data_agent = _build_section(
    3, prior_keys=[*_BASE_PRIOR, "requirements_doc", "architecture_doc"]
)

component_agent = _build_section(
    4,
    prior_keys=[
        *_BASE_PRIOR,
        "requirements_doc",
        "architecture_doc",
        "api_doc",
        "data_doc",
    ],
)

resilience_agent = _build_section(
    5,
    prior_keys=[
        *_BASE_PRIOR,
        "requirements_doc",
        "architecture_doc",
        "component_doc",
    ],
)
security_agent = _build_section(
    6,
    prior_keys=[
        *_BASE_PRIOR,
        "requirements_doc",
        "architecture_doc",
        "component_doc",
    ],
)

decisions_agent = _build_extra(
    1,
    prior_keys=[
        *_BASE_PRIOR,
        "requirements_doc",
        "architecture_doc",
        "api_doc",
        "data_doc",
        "component_doc",
        "resilience_doc",
        "security_ops_doc",
    ],
)

capacity_agent = _build_extra(
    2,
    prior_keys=[
        *_BASE_PRIOR,
        "requirements_doc",
        "decisions_doc",
    ],
)

api_and_data = ParallelAgent(
    name="api_and_data_parallel",
    sub_agents=[api_agent, data_agent],
    description="Writes API and data-model documents in parallel.",
)

hardening = ParallelAgent(
    name="hardening_parallel",
    sub_agents=[resilience_agent, security_agent],
    description="Writes resilience and security/ops documents in parallel.",
)

index_agent = Agent(
    name="index_agent",
    model=_MODEL,
    description="Writes 00-index.md linking all design documents.",
    instruction=build_index_instruction(),
    tools=_FILE_TOOLS,
    output_key="index_doc",
)

review_agent = _build_extra(
    3,
    prior_keys=[
        *_BASE_PRIOR,
        "requirements_doc",
        "architecture_doc",
        "decisions_doc",
        "capacity_doc",
        "index_doc",
    ],
    include_focus_hint=False,
)

design_pipeline = SequentialAgent(
    name="run_design_pipeline",
    description=(
        "Generate all system-design markdown documents. Call ONLY after "
        "init_design_workspace and save_design_context succeed."
    ),
    sub_agents=[
        problem_brief_agent,
        requirements_agent,
        architecture_agent,
        api_and_data,
        component_agent,
        hardening,
        decisions_agent,
        capacity_agent,
        review_agent,
        index_agent,
    ],
)

_pipeline_tool = agent_tool.AgentTool(agent=design_pipeline)

root_agent = Agent(
    name="design_coordinator",
    model=_MODEL,
    description=(
        "System-design assistant. Clarifies scope, then runs the document "
        "pipeline."
    ),
    instruction=COORDINATOR_OUTPUT_CONTRACT,
    tools=[
        FunctionTool(func=init_design_workspace),
        FunctionTool(func=save_design_context),
        _pipeline_tool,
    ],
)
