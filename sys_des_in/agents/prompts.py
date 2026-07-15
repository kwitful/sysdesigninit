"""Shared prompt building blocks for the system-design agents.

Keeping the section schemas and the Reasoning-footer contract in one place makes
it easy to keep the seven specialist agents consistent and to tweak the format
without hunting through every instruction string.
"""

from __future__ import annotations

# The mandatory footer every document must end with. Agents are told to include
# this verbatim-in-spirit: an honest accounting of scope decisions.
REASONING_FOOTER = """## Reasoning

End every document with a `## Reasoning` section that candidly explains the
design decisions behind *this* document. It MUST cover:

1. **What was included** and why it matters for this system.
2. **What was omitted or simplified**, and why it is not needed at the stated
   scale / maturity level (e.g. "Kafka omitted: write QPS < 100 and synchronous
   processing is sufficient"). Do not pad the design with machinery the problem
   does not justify.
3. **Assumptions** made about requirements, scale, or constraints that were not
   explicitly stated by the user.
4. **Open questions** the user should confirm, if any.

Keep the Reasoning section concrete and specific to this document. Avoid
generic filler.
"""

# Coordinator output contract. The coordinator runs first and produces a
# compact structured summary that every downstream agent reads from state.
COORDINATOR_OUTPUT_CONTRACT = """You are the COORDINATOR of a system-design pipeline.

Your job is NOT to design anything. Your job is to take the user's raw problem
description and produce a tight, structured **design context** that the seven
specialist agents downstream will rely on.

First, call the `init_design_workspace` tool with a short name derived from the
problem so a folder is created for the run.

Then produce a markdown block with EXACTLY these sections (keep it short — this
is a brief, not a design):

### Problem
One or two sentences restating what is being designed.

### Scale
- Expected users / devices / accounts (now and in ~5 years).
- Read QPS estimate and write QPS estimate (state assumptions).
- Data volume estimate (now and in ~5 years).

### Quality Targets
- Availability target (e.g. 99.9%, 99.99%).
- Latency target (e.g. p99 < 200ms).
- Consistency vs availability stance (CAP).

### Maturity
One of: `interview` (whiteboard-level, no real ops), `mvp` (shippable but
single-region, manual ops), `production` (multi-region, fully operated).
Choose based on the user's framing. When unclear, default to `interview` and
note the assumption in your reasoning.

### Must-have Features
Bullet list of the core functional requirements.

### Out of Scope
Bullet list of things explicitly excluded to prevent scope creep.

### Reasoning
Briefly justify the scale numbers you assumed and the maturity level you chose,
especially if the user gave little detail. Flag anything you had to guess.

If the user's input is too vague to even guess (e.g. "design a system"), ask a
single clarifying question instead and stop. Do not invent a full problem.
"""

# Each entry is (filename, output_key, section_title, schema_body).
# schema_body is inserted into the agent's instruction and describes the
# required headings for that document.
SECTION_SPECS = [
    (
        "01-requirements.md",
        "requirements_doc",
        "Requirements and Scope",
        """Produce a thorough Requirements & Scope document with these sections:

## Functional Requirements
Concrete, testable statements of what the system must do (e.g. "Users can
upload videos up to N GB"). Number them.

## Non-Functional Requirements
Cover at minimum:
- **Scalability:** Read/write QPS and data growth over ~5 years (use the
  coordinator's scale numbers; refine if needed).
- **Availability:** Target uptime and the business cost of downtime.
- **Latency:** Acceptable response times (p50, p99) for the key operations.
- **Consistency vs Availability:** Where the system sits on the CAP spectrum,
  with justification.

## Out of Scope
Explicit list of what this iteration will NOT do, to prevent scope creep.
""",
    ),
    (
        "02-architecture.md",
        "architecture_doc",
        "High-Level Architecture",
        """Produce a High-Level Architecture document with these sections:

## Overview
One-paragraph summary of the system shape.

## Components
Identify and describe each key architectural component:
- **Clients:** Web, mobile, IoT, etc.
- **Routing & Gateway:** DNS, load balancers (L4 vs L7), API gateway, CDN.
- **Application Tier:** Monolith vs microservices vs serverless, and why.
- **Data Tier:** Databases, caches, message queues (only what this scale
  justifies).

## Data Flow
Step-by-step description of how a representative request travels from client to
data tier and back. Include a simple ASCII/Markdown block diagram.

## Technology Choices
Concrete picks (e.g. PostgreSQL, Redis, Nginx) with one-line justifications
tied to the requirements. Do not over-engineer for an `interview`/`mvp` system.
""",
    ),
    (
        "03-api.md",
        "api_doc",
        "Interface / API Design",
        """Produce an Interface / API Design document with these sections:

## Protocols
Pick the protocols (REST, GraphQL, gRPC, WebSockets) and justify each against
the requirements.

## Endpoints
For each endpoint give: HTTP method, path, request parameters/body, response
shape, and status codes. Use code blocks. Cover the core operations only — do
not invent endpoints no requirement asks for.

## Versioning & Evolution
How the API will be versioned and evolved.
""",
    ),
    (
        "04-data-model.md",
        "data_doc",
        "Data Model and Storage Strategy",
        """Produce a Data Model & Storage document with these sections:

## Database Selection
Relational (SQL, e.g. PostgreSQL) vs NoSQL (e.g. MongoDB, Cassandra), with a
concrete pick justified by ACID needs, schema flexibility, and scale.

## Schema
Define the core tables/collections: fields, types, primary keys, foreign keys,
and indexes. Use Markdown tables or SQL DDL blocks.

## Caching Strategy
Where to cache (CDN, Redis/Memcached) and eviction policy (LRU/LFU), or state
explicitly that caching is not yet justified.

## Data Scaling
Replication (leader-follower), sharding (partition keys), and cold-data
archiving — only at the level the stated scale requires.
""",
    ),
    (
        "05-component-design.md",
        "component_doc",
        "Detailed Component Design",
        """Produce a Detailed Component Design document that deep-dives the most
complex or critical services. Use these sections:

## Core Algorithms
How the key features actually work (e.g. the hashing scheme for a URL
shortener, the ranking logic for a feed). Be concrete.

## Workflows
Step-by-step sequences for the most important operations (e.g. "how a video
upload is processed end to end").

## Asynchronous Processing
Where message brokers (Kafka, RabbitMQ, SQS) are used to decouple slow work
(emails, image processing, fan-out) from the request path. If none is needed at
this scale, say so.
""",
    ),
    (
        "06-resilience.md",
        "resilience_doc",
        "Bottlenecks, Redundancy, and Resilience",
        """Produce a Resilience document with these sections:

## Single Points of Failure
Identify SPOFs and how redundancy removes them (multi-region, replicas,
stateless tiers). Calibrate to the maturity level — an `interview` system may
just *identify* them.

## Rate Limiting & Throttling
How the system protects itself from abuse / DDoS (token bucket, leaky bucket,
per-user limits).

## Graceful Degradation
Circuit breakers, retries with backoff, fallbacks, and what stays available
when a dependency fails.
""",
    ),
    (
        "07-security-ops.md",
        "security_ops_doc",
        "Security, Observability, and Operations",
        """Produce a Security, Observability & Operations document with these
sections:

## Security
Authentication / authorization (OAuth2, JWT, RBAC), encryption in transit (TLS)
and at rest (AES-256), and any authz-relevant design choices.

## Observability
- **Metrics:** which key metrics to track (CPU, memory, latency, error rate).
- **Logging:** centralized log aggregation (e.g. ELK / Loki).
- **Tracing:** distributed tracing (e.g. Jaeger) across services, if
  applicable at this scale.

## Operations
Deployment, CI/CD, on-call concerns, and any runbooks worth calling out.
""",
    ),
]


def build_specialist_instruction(
    section_title: str,
    schema_body: str,
    filename: str,
    prior_context_keys: list[str],
) -> str:
    """Assemble the instruction for one specialist agent.

    Args:
        section_title: Human title, e.g. "Requirements and Scope".
        schema_body: The required-headings block from SECTION_SPECS.
        filename: The file this agent must write, e.g. "01-requirements.md".
        prior_context_keys: State keys whose contents this agent may reference,
            e.g. ["design_context", "requirements_doc"]. They are surfaced to
            the agent via ADK's ``{key}`` instruction substitution.
    """
    prior_block = ""
    if prior_context_keys:
        joined = ", ".join(f"{{{k}}}" for k in prior_context_keys)
        prior_block = (
            f"\n\n## Prior Context\nYou have access to the following earlier "
            f"outputs from session state: {joined}. Use them to stay consistent "
            f"with decisions already made (scale, tech choices, schemas, etc.). "
            f"If a prior decision is missing or unclear, make a reasonable "
            f"assumption and note it in your Reasoning footer.\n"
        )

    return f"""You are the {section_title} specialist in a system-design pipeline.

Your ONLY job is to produce the `{filename}` document and persist it.

{schema_body}{prior_block}

## Output Rules
1. Write the FULL markdown document (all required headings above) as your
   working text.
2. {REASONING_FOOTER.strip()}
3. Once the document is complete, call the `write_design_doc` tool with
   `workspace=<the workspace name from the coordinator's
   init_design_workspace call>`, `filename="{filename}"`, and
   `content=<your full markdown document>`.
4. After the tool returns success, reply with a one-line confirmation such as
   "Wrote {filename}." Do NOT echo the whole document back to the user.
"""


def build_index_instruction() -> str:
    """Instruction for the final summary/index agent."""
    return f"""You are the INDEX agent at the end of a system-design pipeline.

Seven design documents have already been written to disk by the specialist
agents. Your job is to produce a single `00-index.md` that ties them together.

Use `list_design_docs` to confirm which files exist, then read whichever you
need with `read_design_doc`. Produce a markdown index with:

## System Design: <problem>
One-paragraph summary (draw from the coordinator's design context).

## Documents
A numbered list linking to each of the seven section files, with a one-line
description of what each contains.

## Key Decisions at a Glance
A short bulleted summary of the most important architectural and data decisions
(tech stack, sharding strategy, consistency stance, etc.).

## Reasoning
{REASONING_FOOTER.split('## Reasoning', 1)[1].strip()}

Then call `write_design_doc` with `filename="00-index.md"` and the full markdown
as `content`. Reply with a one-line confirmation afterwards.
"""
