# sysdesigninit

An AI-assisted **system design** assistant built on Google's
[Agent Development Kit (ADK)](https://adk.dev/).

Give it a problem ("Design a URL shortener for a startup", "Design a
Netflix-like video platform") and it runs a **multi-agent pipeline** that
produces seven detailed markdown design documents — one per canonical
system-design section — plus an index. Every document ends with a candid
**Reasoning** footer explaining what was included, what was omitted or
simplified, and why.

## Why a pipeline, not one big prompt

One model asked to "write everything" tends to be vague, inconsistent, and
either over- or under-engineered. Splitting the work keeps each section deep,
lets us enforce the Reasoning footer, and mirrors how real design actually
happens: clarify → sketch → detail → harden.

## The agent graph

```
root_agent (SequentialAgent: system_design_pipeline)
│
1. design_coordinator        ── design_context (clarify scope, scale, maturity)
│
2. requirements_agent        ── 01-requirements.md
│
3. architecture_agent        ── 02-architecture.md
│
4. api_and_data (ParallelAgent)
      ├─ api_agent           ── 03-api.md
      └─ data_agent          ── 04-data-model.md
│
5. component_agent           ── 05-component-design.md
│
6. hardening (ParallelAgent)
      ├─ resilience_agent    ── 06-resilience.md
      └─ security_agent      ── 07-security-ops.md
│
7. index_agent               ── 00-index.md
```

- **SequentialAgent** runs steps in order, passing the same session state
  forward so each agent can read earlier decisions.
- **ParallelAgent** fans out where work is independent (API + data model;
  resilience + security/ops).
- Each specialist has an `output_key` so its full markdown lands in shared
  state, and downstream agents reference those keys via `{key}` substitution.
- Every specialist writes its file to disk via the `write_design_doc` tool.

## The seven documents

1. **Requirements and Scope** — functional + non-functional requirements,
   CAP stance, out-of-scope.
2. **High-Level Architecture** — clients, routing/gateway, app tier, data tier,
   data flow, tech picks.
3. **Interface / API Design** — protocols, endpoints, versioning.
4. **Data Model and Storage** — DB selection, schema, caching, scaling.
5. **Detailed Component Design** — core algorithms, workflows, async
   processing.
6. **Bottlenecks, Redundancy, Resilience** — SPOFs, rate limiting, graceful
   degradation.
7. **Security, Observability, Operations** — auth, encryption, metrics,
   logging, tracing, ops.

Each ends with a `## Reasoning` section: what was included, what was
omitted/simplified and why (e.g. "Kafka omitted: write QPS < 100 and
synchronous processing is sufficient"), assumptions, and open questions.

## Project layout

```
sys_des_in/                # agent package (ADK requires a valid Python identifier)
├── agent.py              # ADK entry point (exposes root_agent)
├── runner.py             # optional CLI runner
├── __init__.py
├── .env                  # GOOGLE_API_KEY=...
├── adk-documentation.txt # local ADK docs (reference)
├── agents/
│   ├── __init__.py
│   ├── prompts.py        # shared schemas + Reasoning footer contract
│   └── orchestrator.py   # builds the SequentialAgent root + specialists
├── tools/
│   ├── __init__.py
│   └── file_tools.py     # init_design_workspace / write / read / list
└── design_outputs/       # generated markdown lives here (per workspace)
```

> Note: the agent folder is named `sys_des_in` (underscores), not
> `sys-des-in`. ADK only loads agent folders whose names are valid Python
> identifiers (`^[a-zA-Z0-9_]+$`), so dashes are not allowed.

## Setup

1. Create a virtual environment and install ADK:

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

2. Put a Gemini API key in `sys_des_in/.env` (already created):

   ```text
   GOOGLE_GENAI_USE_ENTERPRISE=0
   GOOGLE_API_KEY=your_key_from_https://aistudio.google.com/app/apikey
   ```

## Run

### Option A — ADK web UI (recommended for exploring)

From the project root (the folder *containing* `sys_des_in`):

```bash
adk web
```

Pick `sys_des_in` in the agent dropdown, then send a message like
`Design a URL shortener for a startup`. The pipeline runs end to end and writes
the seven files to `sys_des_in/design_outputs/<workspace>/`.

### Option B — CLI runner

From the project root:

```bash
python -m sys_des_in.runner "Design a URL shortener for a startup"
```

### Option C — ADK API server

```bash
adk api_server
```

## Output

For a problem like "URL shortener for a startup", you'll get:

```
sys_des_in/design_outputs/url-shortener-for-a-startup/
├── 00-index.md
├── 01-requirements.md
├── 02-architecture.md
├── 03-api.md
├── 04-data-model.md
├── 05-component-design.md
├── 06-resilience.md
└── 07-security-ops.md
```

## Notes on calibration

The coordinator picks a **maturity level** — `interview`, `mvp`, or
`production` — from the user's framing, and every specialist calibrates its
depth to that level. An `interview`-level URL shortener won't get Kafka and
multi-region replication; a `production`-level video platform will. The
Reasoning footers make those scope decisions explicit and auditable.

## Next ideas

- A `LoopAgent` review pass that checks cross-document consistency and rewrites
  conflicting sections.
- Human-in-the-loop confirmation at the coordinator step before spending tokens
  on seven docs.
- A "generate only sections X–Y" mode for partial runs.
