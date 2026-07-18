# sysdesigninit

An AI-assisted **system design** assistant built on Google's
[Agent Development Kit (ADK)](https://adk.dev/).

Describe a product ("Design a URL shortener for a startup", "Design a
Netflix-like video platform"). A **conversational coordinator** clarifies scope
across turns, saves a structured brief, then runs a **multi-agent pipeline**
that writes **twelve markdown files** — core design sections plus a problem
brief, decisions log, capacity math, specificity review, and index.

The goal is designs that stay **anchored to your problem**, not generic
template filler. Every document ends with a `## Reasoning` footer (what was
included, omitted/simplified, and why).

**Model providers:** Gemini (default) or **OpenRouter** (and other LiteLLM
providers) via ADK's official `LiteLlm` integration.

## How it works

1. **Clarify** — The coordinator asks short questions (one per turn) until it
   knows the product, scale, maturity (`interview` / `mvp` / `production`),
   constraints, and critical flows.
2. **Brief** — It saves `design_context` to session state (Problem, Critical
   Flows, Scale, Constraints, Must-haves, Out of Scope, …) and creates a
   workspace folder.
3. **Pipeline** — It invokes `run_design_pipeline` via ADK `AgentTool`. Ten
   stages write and link the markdown files (some stages run in parallel).
4. **Review** — A critic agent scores specificity and flags generic or
   contradictory sections before the index is written.

## Architecture (ADK-aligned)

```
root_agent (LlmAgent: design_coordinator)     ← talks to the user
  tools:
    - init_design_workspace   → state["workspace"]
    - save_design_context     → state["design_context"]
    - AgentTool(run_design_pipeline)
            │
            ▼
run_design_pipeline (SequentialAgent)         ← only after brief is saved
  1. problem_brief           → 00-problem-brief.md (+ Focus Map)
  2. requirements          → 01-requirements.md
  3. architecture          → 02-architecture.md
  4. api_and_data (ParallelAgent)
        ├─ api             → 03-api.md
        └─ data            → 04-data-model.md
  5. component             → 05-component-design.md
  6. hardening (ParallelAgent)
        ├─ resilience      → 06-resilience.md
        └─ security/ops    → 07-security-ops.md
  7. decisions_log         → 08-decisions-log.md
  8. capacity              → 09-capacity-estimates.md
  9. review                → 00-review.md
 10. index                 → 00-index.md
```

- **Clarification before generation** — the pipeline does not run until the
  coordinator has saved workspace + design context.
- **Session state handoff** — `ToolContext` tools write `workspace` and
  `design_context`; specialists read them via `{key}` substitution and
  `output_key`.
- **Anti-generic rules** — each writer must tie decisions to Critical Flows,
  include concrete examples, name rejected alternatives, and reuse the brief's
  numbers.

## Generated documents

| File | Role |
|------|------|
| `00-problem-brief.md` | Anchor: critical flows, constraints, maturity, **Focus Map** (what each section must emphasize) |
| `01-requirements.md` | Functional + non-functional requirements, out of scope |
| `02-architecture.md` | Components, data flow on the hardest path, tech choices |
| `03-api.md` | Protocols, endpoints with realistic examples |
| `04-data-model.md` | Schema, caching, scaling for this product's access patterns |
| `05-component-design.md` | Deep dive on 1–2 hardest services only |
| `06-resilience.md` | SPOFs, rate limits, graceful degradation |
| `07-security-ops.md` | Security, observability, operations (calibrated to maturity) |
| `08-decisions-log.md` | Consolidated decisions + alternatives considered |
| `09-capacity-estimates.md` | Back-of-envelope QPS, storage, bottleneck math |
| `00-review.md` | Specificity scores, generic passages, contradictions |
| `00-index.md` | Table of contents and key decisions at a glance |

All files are written under `sys_des_in/design_outputs/<workspace>/`. Only
whitelisted filenames are allowed (enforced in `tools/file_tools.py`).

## Models (Gemini or OpenRouter)

Configured in `sys_des_in/.env` (copy from `.env.example`). The factory is in
`sys_des_in/models.py` and uses ADK's `LiteLlm` for non-Gemini providers.

### Gemini (default)

```text
LLM_PROVIDER=gemini
LLM_MODEL=gemini-flash-latest
GOOGLE_GENAI_USE_ENTERPRISE=0
GOOGLE_API_KEY=your_key
```

Get a key from [Google AI Studio](https://aistudio.google.com/app/apikey).

### OpenRouter

```text
LLM_PROVIDER=openrouter
LLM_MODEL=openrouter/openai/gpt-4o-mini
OPENROUTER_API_KEY=sk-or-v1-...
```

Any [OpenRouter model](https://openrouter.ai/models) works. Use the LiteLLM id
`openrouter/<provider>/<model>`. The `openrouter/` prefix is added automatically
if omitted.

### Other LiteLLM providers

```text
LLM_PROVIDER=litellm
LLM_MODEL=anthropic/claude-3-haiku-20240307
ANTHROPIC_API_KEY=...
```

On Windows, `PYTHONUTF8=1` is set automatically (per ADK LiteLLM guidance).

## Project layout

```
sysdesigninit/                 # repo root (this README)
├── requirements.txt
├── LICENSE
├── app/                       # FastAPI + vanilla TS/CSS web UI
│   ├── main.py                # HTTP API + SSE + static mount
│   ├── sessions.py            # in-memory sessions + background ADK turns
│   ├── agent_bridge.py        # wraps ADK Runner
│   ├── docs_service.py        # safe list/read/zip over design_outputs
│   ├── chat_store.py          # chat.json / meta.json sidecars
│   ├── brief_parse.py         # design_context → brief fields
│   ├── markdown_render.py     # markdown → sanitized HTML + TOC
│   ├── static/                # index.html, css/, compiled js/
│   └── web/                   # TypeScript sources (tsc → static/js)
└── sys_des_in/                # ADK agent package (valid Python identifier)
    ├── agent.py               # ADK entry point (root_agent)
    ├── runner.py              # multi-turn CLI (safe input loop)
    ├── models.py              # Gemini / OpenRouter / LiteLLM factory
    ├── .env.example
    ├── .env                   # secrets (gitignored)
    ├── agents/
    │   ├── prompts.py         # schemas, anti-generic rules, coordinator contract
    │   └── orchestrator.py    # coordinator + AgentTool pipeline
    ├── tools/
    │   ├── file_tools.py      # write / read / list (filename whitelist)
    │   └── state_tools.py     # workspace + save_design_context
    └── design_outputs/        # generated markdown per run
```

> The agent folder must be named `sys_des_in` (underscores). ADK only loads
> agent directories whose names are valid Python identifiers (`^[a-zA-Z0-9_]+$`).

## Setup

```bash
cd path/to/sysdesigninit          # folder that contains sys_des_in/
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy sys_des_in\.env.example sys_des_in\.env    # Windows
# cp sys_des_in/.env.example sys_des_in/.env    # macOS / Linux
```

Edit `sys_des_in/.env` with your API key(s).

## Run

All commands below assume your shell is in the **repo root** (the directory
that contains `sys_des_in/` and `app/`).

### Option A — Web UI (recommended)

Vanilla TypeScript + CSS frontend served by FastAPI. Chat with the coordinator,
watch the pipeline checklist, and read generated markdown in the browser.

Requires [Node.js](https://nodejs.org/) only to compile TypeScript (`tsc`);
there are no frontend runtime libraries.

```bash
# compile UI (from repo root)
npx -p typescript tsc -p app/web

# start local server (bind to localhost)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). API keys stay in
`sys_des_in/.env` (never exposed to the browser).

**Web UI (v2 clarity):**

- Journey rail: **Clarify → Generate → Review**, plus **History**
- One status line that explains what to do next; single system banner for
  errors / cancel / overwrite / read-only browse
- Staged panes: chat during clarify; document reader during generate/review;
  past designs only in History (not under the file list)
- Guided review actions: problem brief, specificity review, full packet index
- Humanized section labels; **Start over**; Cancel during generation
- Live progress via SSE (poll fallback); chat.json persistence; zip download
- Mobile tabs: Chat | Docs | History

### Option B — ADK web UI

```bash
adk web
```

Select **`sys_des_in`**, then chat with the coordinator. When it has enough
detail it runs the pipeline and writes files to `sys_des_in/design_outputs/`.

### Option C — Multi-turn CLI

```bash
python -m sys_des_in.runner
python -m sys_des_in.runner "Design a URL shortener for a startup, interview-level"
```

- Answer at the `You>` prompt (input is read only after each turn finishes).
- Quit with `quit`, `exit`, or `q`.

### Option D — ADK built-in CLI

```bash
adk run sys_des_in
```

### Option E — ADK API server

```bash
adk api_server
```

## Example output tree

```
sys_des_in/design_outputs/url-shortener-for-a-startup/
├── .problem.txt
├── chat.json                 # web UI chat transcript (not agent-written)
├── meta.json                 # optional completion metadata from web UI
├── 00-problem-brief.md
├── 00-index.md
├── 00-review.md
├── 01-requirements.md
├── 02-architecture.md
├── 03-api.md
├── 04-data-model.md
├── 05-component-design.md
├── 06-resilience.md
├── 07-security-ops.md
├── 08-decisions-log.md
└── 09-capacity-estimates.md
```

After a run, start with **`00-problem-brief.md`** (did it understand your
problem?) and **`00-review.md`** (what's still generic?).

## Tips for better results

- Be specific in your opening message: product, scale, maturity, and what you
  worry about (e.g. hot keys, latency, cost).
- Use `interview` vs `mvp` vs `production` — prompts calibrate depth to that.
- For OpenRouter, prefer models with reliable **tool calling**; very cheap
  models may skip `write_design_doc`.
- A full pipeline is ~10 LLM stages (some parallel) — expect several minutes
  and non-trivial token use per run.

## Notes

- Do not commit `sys_des_in/.env`. Rotate keys if they leak.
- Maturity and Reasoning footers make scope explicit; they do not guarantee
  perfection — use `00-review.md` as a sanity check.
