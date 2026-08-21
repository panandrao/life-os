# Persona Lab — Phase 0

A command-line spike of the persona simulation platform: run up to ~100 LLM
persona agents against uploaded materials, individually and in groups, collect
responses in a format you define, and get basic analysis. See
`../docs/persona-platform/research-and-plan.md` for the full research report
and roadmap this implements.

## What it does

1. **Individual reactions (always first).** Every persona privately reviews the
   materials and answers in your JSON schema — run in parallel with prompt
   caching, so the shared materials are paid for once and read at 0.1× price by
   every other persona.
2. **Group discussion (optional).** Personas are assigned to groups (explicitly
   or auto-chunked). Each group runs N round-robin rounds with rotated speaking
   order, an optional scripted moderator, and a structured turn format that
   requires explicit agreements/disagreements — the anti-sycophancy design from
   the research report. Groups run concurrently; turns within a group are
   sequential.
3. **Re-survey (optional).** After discussion, each participant answers the
   original questions again, so opinion shift is measurable per persona.
4. **Analysis.** Deterministic stats (no LLM): numeric field means/stdev at
   population, category (faculty vs staff), department, and group level;
   categorical counts; discussion dynamics (position shifts, explicit
   disagreement counts); pre/post shift; homogenization warnings; cost report.

## Setup

```bash
cd persona-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# Inspect the persona bank (45 fictional UMW-style faculty/staff included)
python -m personalab validate personas/umw
python -m personalab validate personas/umw --card fac-phi-01

# Plan a run without spending anything
python -m personalab run examples/run-umw-demo.yaml --dry-run

# Execute (the demo: 15 personas, 3 groups × 5, 2 rounds, re-survey)
python -m personalab run examples/run-umw-demo.yaml

# Re-run analysis on a finished run
python -m personalab analyze runs/<timestamp>/run.json
```

Outputs land in `runs/<timestamp>/`: `run.json` (full raw record — every
response and every discussion turn), `analysis.json`, and `analysis.md`.

## Run configs

Everything is one YAML file — see `examples/run-umw-demo.yaml` for a fully
commented example. Key blocks: `personas` (file/dir, include/exclude/sample),
`materials` (PDF, .md/.txt, images; PPTX must be exported to PDF first),
`instructions`, `response_format.schema` (any JSON schema — enforced via
forced tool use), `groups` (size or explicit `assignments`, rounds, moderator
prompt), `resurvey`, and model/concurrency settings.

## Persona format

Persona banks are YAML files (a list, or a `personas:` list) — see
`personas/umw/*.yaml`. Core fields: `id`, `name`, `role`, `department`,
`category`, plus `age`, `education`, `background`, `personality`, `values`,
`viewpoints`, `quirks`. **Any extra fields you add are automatically rendered
onto the persona card**, so richer personas need no code changes.

The included bank is 45 **fictional** personas modeled on the role mix at a
public liberal-arts university (30 faculty across Education, Philosophy,
Classics, Communication, Computer Science, Music, Chemistry, Historic
Preservation, English, Biology, Psychology, History, Math, Business; 15 staff
across the library, IT, digital learning, registrar, admissions, student
affairs, advising, career services, accessibility, facilities, communications,
financial aid, athletics, HR). Any resemblance to real individuals is
coincidental.

## Cost expectations

The demo run (15 personas, ~2.5k-token material, 3 groups × 5 × 2 rounds +
re-survey) costs on the order of **$0.50–1.50**. A 100-persona run over ~50k
tokens of material with a 3-round group phase is roughly **$2–6** with the
caching this engine applies automatically. A cost estimate is printed after
every run (`cost` block in `run.json`).

## Phase 0 boundaries (deliberate)

CLI only, no UI; personas reset per run (no cross-study memory); no Batch API
path yet (worth adding at ~50+ personas); no LLM population-synthesis report
(group summaries only); PPTX via PDF export. All of these are Phase 1+ items
in the roadmap.
