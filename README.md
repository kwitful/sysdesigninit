# sysdesigninit

An AI-assisted **system design** assistant built on Google's
[Agent Development Kit (ADK)](https://adk.dev/).

Give it a problem ("Design a URL shortener for a startup", "Design a
Netflix-like video platform"). A **conversational coordinator** clarifies
scope across turns, then invokes a **document pipeline** that writes seven
detailed markdown design docs plus an index. Every document ends with a candid
**Reasoning** footer (what was included, omitted/simplified, and why).

**Model providers:** Gemini (default) or **OpenRouter** (and other LiteLLM
providers) via ADK's official `LiteLlm` integration.

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
  2. requirements_agent      → 01-requirements.md
  3. architecture_agent      → 02-architecture.md
  4. api_and_data (ParallelAgent)
        ├─ api_agent         → 03-api.md
        └─ data_agent        → 04-data-model.md
  5. component_agent         → 05-component-design.md
  6. hardening (ParallelAgent)
        ├─ resilience_agent  → 06-resilience.md
        └─ security_agent    → 07-security-ops.md
  7. decisions_log           → 08-decisions-log.md
  8. capacity                → 09-capacity-estimates.md
  9. review                  → 00-review.md (specificity critique)
 10. index                   → 00-index.md
```

Specialists share **anti-generic rules** (concrete examples, rejected
alternatives, tie to Critical Flows) and read the problem brief Focus Map.

## Models (Gemini or OpenRouter)

Configured in `sys_des_in/.env` (see `.env.example`). The factory lives in
`sys_des_in/models.py` and uses ADK's `LiteLlm` for non-Gemini providers.

### Gemini (default)

```text
LLM_PROVIDER=gemini
LLM_MODEL=gemini-flash-latest
GOOGLE_GENAI_USE_ENTERPRISE=0
GOOGLE_API_KEY=your_key
```

### OpenRouter (main alternate path)

```text
LLM_PROVIDER=openrouter
LLM_MODEL=openrouter/openai/gpt-4o-mini
OPENROUTER_API_KEY=sk-or-v1-...
```

Any [OpenRouter model](https://openrouter.ai/models) works; the LiteLLM id is
`openrouter/<provider>/<model>`. If you omit the `openrouter/` prefix, it is
added automatically.

### Other LiteLLM providers

```text
LLM_PROVIDER=litellm
LLM_MODEL=anthropic/claude-3-haiku-20240307
ANTHROPIC_API_KEY=...
```

On Windows, `PYTHONUTF8=1` is set automatically (ADK LiteLLM guidance).

## The seven documents

1. **Requirements and Scope**
2. **High-Level Architecture**
3. **Interface / API Design**
4. **Data Model and Storage**
5. **Detailed Component Design**
6. **Bottlenecks, Redundancy, Resilience**
7. **Security, Observability, Operations**

Each ends with `## Reasoning`. Plus `00-index.md`.

## Project layout

```
sys_des_in/
├── agent.py              # ADK entry point (root_agent)
├── runner.py             # multi-turn CLI (safe input loop)
├── models.py             # Gemini / OpenRouter / LiteLLM factory
├── .env.example
├── .env                  # secrets (gitignored)
├── agents/
│   ├── prompts.py
│   └── orchestrator.py   # coordinator + AgentTool pipeline
├── tools/
│   ├── file_tools.py     # write / read / list (filename whitelist)
│   └── state_tools.py    # init workspace + save_design_context
└── design_outputs/
```

## Setup

```bash
cd path/to/sysdesigninit   # folder that contains sys_des_in/
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy sys_des_in\.env.example sys_des_in\.env   # then edit keys
```

## Run

### Option A — ADK web UI

```bash
adk web
```

Pick `sys_des_in`, chat with the coordinator. When it has enough detail it
runs the pipeline and writes files under `sys_des_in/design_outputs/`.

### Option B — Multi-turn CLI (this project's runner)

```bash
python -m sys_des_in.runner
# or with an opening message:
python -m sys_des_in.runner "Design a URL shortener for a startup"
```

Type answers at the `You>` prompt (visible, after each turn fully finishes).
Quit with `quit` / `exit` / `q`.

### Option C — ADK built-in CLI

```bash
adk run sys_des_in
```

### Option D — API server

```bash
adk api_server
```

## Output

```
sys_des_in/design_outputs/<workspace>/
├── 00-problem-brief.md    # anchor + Focus Map per section
├── 00-index.md
├── 00-review.md           # specificity critique
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

## Notes

- Maturity (`interview` / `mvp` / `production`) calibrates how heavy the design
  is; Reasoning footers make omissions explicit.
- Prefer models with solid tool-calling for OpenRouter (cheap models may skip
  `write_design_doc`).
- Do not commit `.env`. Rotate keys if they leak.
