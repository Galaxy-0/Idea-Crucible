# Idea-Crucible

Concise, testable scaffolding for evaluating startup ideas via a redline-first, falsification-oriented workflow.

## Deliverables
- Repo scaffold with configs, schemas, CLI skeleton
- Seed “redline” rule set (10 items) and rule files
- One-page report template and sample run

## Proposed Scaffold
- `agent/` CLI and core
  - `agent/main.py` — commands: `intake` | `evaluate` | `report`
  - `agent/schemas.py` — Pydantic models: `Rule`, `Idea`, `Evidence`, `Verdict`
  - `agent/engine.py` — rule matching + arbiter stub
- `config/`
- (removed) `config/modes.yaml` — legacy
- (removed) `config/weights.yaml` — legacy
  - `config/rules/core/*.yaml` — redlines by category
- `ideas/` — example idea YAML
- `reports/` — generated verdicts
- `templates/report.md` — one-page report template

## Data Schemas (concise)
- Rule: `id`, `scope`, `condition` (expr), `severity`, `rationale`, `sources[]`, `owner`, `version`, `sunset`, `decision`, `keywords[]`, `next_steps[]`
- Idea: `intent`, `user`, `scenario`, `triggers`, `alts`, `assumptions[]`, `risks[]`
- Evidence: `type` (primary|secondary|tertiary), `provenance`, `weight`, `sample_size`, `excerpts[]`, `timestamp`
- Verdict: `decision` (deny|caution|go), `reasons[]`, `conf_level`, `redlines[]`, `next_steps[]`

## Initial 10 Redlines (V1)
1) Technical/physical impossibility or unproven prerequisite science within horizon → deny
2) Unit cost lower bound > customer value upper bound (no plausible path in 18–36m) → deny
3) Essential data legally inaccessible or platform-prohibited; no compliant substitute → deny
4) Regulatory hard block or licensing lead time > runway; no staged path → deny
5) Single platform dependency with kill-switch risk and no mitigation → caution/deny
6) Distribution structurally impossible to initial 1k targets (not “expensive”—“unreachable”) → deny
7) Two-sided network effects with no single-sided stand-alone value → deny
8) No plausible moat source within target market (data/process embed/network/scale) → caution
9) Ethical/safety red flag (systemic harm, abuse vector) beyond mitigation → deny
10) Time-to-proof > runway with no intermediate value gates (no RAT path) → deny

Each rule carries: condition, severity, rationale, sources, and outputs “deny/caution/continue” with next-step experiments when “caution”.

## Flow (MVP)
- intake: normalize an idea YAML from a short description
- evaluate: load rules, run conditions, compute decision + confidence
- report: render one-page verdict with citations and next steps

## Quickstart (LLM required for evaluation)
- Python 3.10+
 - Install uv: https://docs.astral.sh/uv/
 - Create venv: `uv venv` (or `uv venv -p 3.11`)
 - Install dependencies: `uv sync`
 - Configure `config/model.yaml`:
   - `base_url`: e.g., https://api.openai.com/v1
   - `api_key`: your API key
- Run: `uv run python -m agent.main ...`

Commands
- Intake: `uv run python -m agent.main intake --desc "Two-sided marketplace needing unproven AGI to work" --out ideas/demo-idea.yaml`
- Evaluate (LLM): `uv run python -m agent.main evaluate --idea ideas/demo-idea.yaml --model-cfg config/model.yaml`
- Report: `uv run python -m agent.main report --idea ideas/demo-idea.yaml`

Optional: None in minimal build (OpenAI client is included by default)

## Files of Interest
  (modes/weights removed; LLM-based evaluation only)
- `config/rules/core/`: 10 redline rules (YAML)
- `templates/report.md`: one-page report template
- `ideas/demo-idea.yaml`: example input idea
- `reports/sample.md`: sample report output

## LLM Integration
- Configure provider/model in `config/model.yaml` (default: OpenAI gpt-4o-mini, env `OPENAI_API_KEY`).
- Modes: `llm-only` (default)
- Prompt: the client builds a JSON-format request directly.
