# Persona Simulation Platform — Research Report & Build Plan

**Prepared:** August 21, 2026
**Goal:** A locally-run platform that spins up 1–100 LLM persona agents, feeds them uploaded materials (documents, decks, transcripts, images), runs them individually and in assigned groups under user-defined interaction instructions, collects responses in user-specified formats, and analyzes results at the individual, group, and population level — with a later path to hosted/remote deployment.

---

## 1. Executive Summary

- **Nobody sells exactly this.** The synthetic-audience market is booming (Simile raised $200M at a $2B valuation in July 2026; Qualtrics, NielsenIQ, Ipsos, Kantar, and YouGov all ship synthetic-panel features), but no product combines *local/private deployment + arbitrary long-document ingestion + both individual and group interaction + full transcript access + your own analysis layer*. That combination is a genuine gap.
- **No single open-source project delivers the full stack either**, but the pieces are well-proven: Microsoft **TinyTroupe** (personas + focus-group simulation + results extraction), Expected Parrot **EDSL** (survey DSL + structured results + analysis), DeepMind **Concordia**'s Game Master pattern (programmable moderator for group sessions), and Stanford's **genagents** (interview-transcript-grounded personas with 85% fidelity to real individuals' survey answers).
- **Recommended build:** don't adopt a heavyweight agent framework. Phase 1 (individual reactions) is an embarrassingly parallel fan-out — raw Anthropic Python SDK + asyncio. Phase 2 (group discussion) is a small explicit state machine. Claude's platform features line up unusually well: Files API (upload materials once), prompt caching (0.1× price on shared material, and cache reads don't count against rate limits), structured outputs (guaranteed-valid responses in your assigned formats), Batch API (50% off, stacks with caching), and native PDF/vision ingestion.
- **Economics are a non-issue at this scale.** A well-engineered 100-persona run (each reading ~50k tokens of material, plus a 3-round group-discussion phase) costs roughly **$2–3 on Haiku 4.5 or $4–6 on Sonnet** with caching and batching. Naive implementations cost 5–10× more — caching is mandatory, not optional.
- **Validity is the real design problem, not plumbing.** The 2025–26 literature is consistent: aggregate/directional results replicate human data reasonably well (85–90% of human test–retest reliability in the best setups); individual-level prediction is poor; ungrounded demographic personas homogenize, stereotype, and sycophantically converge in groups. The platform should bake in the known mitigations (material-grounded personas, independent-first "Delphi" sequencing, structured disagreement, free-text elicitation with derived ratings, dissent-preserving aggregation).
- **Suggested path:** a 1–2 week Phase 0 spike (CLI, 10 personas, one document, structured outputs) to validate the pipeline, then build the FastAPI + React app in five phases, reaching a complete local v1 in roughly 6–8 weeks of focused work.

---

## 2. Landscape: Who Has Built Something Like This

### 2.1 Academic / open-source

| Project | What it is | Scale | Doc grounding | Group mechanics | License / status |
|---|---|---|---|---|---|
| **Stanford Generative Agents** (Smallville, 2023) | Founding work: 25 agents in a simulated town; memory/reflection/planning | 25 | No | Emergent, spatial | Apache 2.0; frozen research artifact |
| **Stanford genagents** (2024) | Personas grounded in 2-hour interview transcripts of 1,052 real people; 85% normalized accuracy replicating their GSS survey answers | 1,000+ | **Yes — transcripts** | No | MIT; research code, low maturity |
| **Microsoft TinyTroupe** (v0.7, 2026) | Persona library (`TinyPerson`/`TinyWorld`): focus groups, ad tests, brainstorming; document grounding; results extraction; statistical validation vs. real data | Tens | **Yes** | Yes — shared worlds, broadcast stimuli | MIT; active but "experimental, API unstable" |
| **DeepMind Concordia** (v2) | Generative agent-based modeling with a **Game Master** agent that narrates/adjudicates — a programmable moderator | ~4–10 | Environment-level | **Strong** (GM pattern) | Apache 2.0; active |
| **Expected Parrot EDSL** | Python DSL for AI survey research: typed questions, skip logic, persona agents, parallel runs, structured `Results` objects with built-in analysis and provenance | 1000s of agent×question jobs | Yes — attach docs as scenarios | No (stateless respondents) | MIT; active YC-backed company |
| **AgentSociety 2** (Tsinghua) | Full experiment platform: 10k+ citizens, surveys/interviews/interventions, web UI, replay | 10k+ | No | Social networks | Apache 2.0 w/ commercial carve-outs |
| **OASIS** (CAMEL-AI) | Social-media simulation to 1M agents; group chats; "interview" action for querying agents mid-sim; SQLite/Postgres persistence | Up to 1M | Profile JSON | Feed-shaped + group chat | Apache 2.0; very active |
| **SocioVerse** (Fudan, 2025) | 10M real-user profile pool; survey/interview scenario engines; validated on election and economic-survey replication | Population | Partial | Survey-shaped | Academic |
| **SOTOPIA** (CMU) | Goal-driven social interaction between personas + **SOTOPIA-Eval** multi-dimensional scoring of interaction quality | Dyads/small groups | No | Yes | MIT; active |
| **AgentTorch / LPM** (MIT) | "LLM archetypes": few LLM calls steering millions of numeric agents — the cost-control pattern for scaling past 100 | Millions | No | Mechanistic | MIT; active |

Also notable: **Persona Hub** (Tencent — 200k+ released persona seeds), **Habermas Machine** (DeepMind, *Science* 2024 — AI consensus mediation that beat human mediators), and a long tail of tiny OSS tools in exactly this niche (synthetic focus groups from sales-call transcripts, etc.) — all early-stage, none dominant. **The space between "toolkit" and "enterprise SaaS" is open.**

### 2.2 Commercial

**Enterprise population simulation ($50k–$250k+/yr, demo-gated):**
- **Simile** (simile.ai) — Joon Sung Park's commercialization of the Stanford work; $300M raised, $2B valuation; interview-grounded personas; Gallup partnership; CVS, Telstra, Wealthfront.
- **Aaru** — multi-agent prediction engine (~$1B valuation, Accenture partnership); predicted the 2024 election with ~5,000 agents.
- **Evidenza** — B2B synthetic customers (BlackRock, Microsoft, Nestlé); profitable, no VC; claims 88% accuracy across 100+ head-to-heads.
- **Electric Twin** — UK; survey-grounded synthetic audiences for message testing; claims 96% match, LSE-validated.

**Content/messaging-reaction specialists (closest to your use case):**
- **Artificial Societies** (societies.io) — simulates how content lands with a *networked* audience of 300–5,000 interconnected personas (influence propagation, pre/post-exposure measurement). Started as a LinkedIn-post simulator; now enterprise comms.
- **Viewpoints.ai** — pivoted to **AI jury simulation**: upload pleadings, transcripts, exhibits, video; 12-person demographically matched juries *deliberate* (persuasion, holdouts); outputs verdict distributions, ranked decision drivers, A/B comparison of case versions. Architecturally, the closest thing to "groups of personas deliberating over uploaded materials."
- **Yabble → YouGov Virtual Audiences** — upload creative, personas identify what drives appeal; grounded in YouGov panel data (~$800/mo tier).

**Self-serve tier ($29–$800/mo):** Synthetic Users (pay-per-interview $2–60, RAG grounding on your transcripts, public API), Ask Rally (~$100/mo, n=5,000 studies, persona cloning from interviews), Minds ($29/mo, documents → reusable audiences), SYMAR/OpinioAI (€99/mo synthetic focus groups), SimSurveys ($1,000/study), Native AI (digital twins from review data), Delve AI (persona generation from analytics).

**Incumbents:** Qualtrics **Edge Audiences** (synthetic panels on 25 years of response data), NielsenIQ **BASES AI Screener**, Ipsos Persona Bots, Kantar synthetic boosting, Toluna HarmonAIze (1M+ personas from its 79M-member panel). Cautionary tale: **Roundtable.ai**, one of the first synthetic-respondent startups, pivoted entirely to survey *fraud detection*.

### 2.3 The gap you'd fill

Feature patterns across the market: document upload is table stakes, but almost nobody handles **long multi-document materials** well (except Viewpoints, litigation-only); **true group interaction is rare** (most tools run personas independently and aggregate); self-serve + API is an underserved combination; and every enterprise product is closed and cloud-only. A local, private, transcript-transparent platform with real group mechanics competes with the $100–800/mo tier on cost almost immediately (~$2–6/run in API fees).

---

## 3. What the Science Says (Design Constraints)

**Evidence for:**
- Interview-grounded personas replicate real individuals' survey answers at **85% of the accuracy with which people replicate their own answers two weeks later** (Park et al. 2024), and grounding *reduces* accuracy gaps across demographic groups vs. demographic-prompt personas.
- **Semantic Similarity Rating (SSR)** — elicit free text, then map to Likert scales via embeddings — achieves ~90% of human test–retest reliability across 57 real product surveys, with realistic response distributions. Direct "rate 1–5" elicitation suffers mode collapse.
- Aggregate-level distributions replicate far better than individual-level predictions across all studies (Twin-2K-500 benchmark and others).

**Evidence against (each maps to a platform guardrail):**

| Failure mode | Finding | Guardrail to build |
|---|---|---|
| Homogenization / "persona collapse" | Simulated populations under-cover human archetypes; low variance; over-coherent respondents | Ground personas in real material (transcripts, interviews); measure within-group variance per run |
| Stereotype amplification | High "persona fidelity" often = caricature (effect sizes 3× human); partisan/racial polarization inflated ~7× | Persona cards from evidence, not just demographics; per-subgroup fidelity reporting |
| Sycophantic convergence | Groups drift to bland unanimity; one agreeable agent infects the group; first speaker anchors outcomes | Independent-first (Delphi) sequencing; structured "where I disagree and why" fields; rotate speaking order; cap at 2–3 rounds; never force consensus |
| Mode collapse on scales | Direct numeric ratings cluster unrealistically | SSR: free text first, derive ratings |
| Prompt instability | Results swing with wording and model version | Version and log every prompt/model/config; provenance on every run |
| Analytic flexibility | Simulated pipelines can produce almost any result | Locked, reproducible run configs; report dissent and distributions, not just means |

**Standards context:** AAPOR's 2026 guidance insists on the term synthetic *responses* (estimation, not sampling) and warns ungrounded respondents "resemble plausible survey data while failing to reflect true distributions." The consensus position — and the honest positioning for this platform — is **augmentation**: piloting, pretesting, hypothesis generation, and message stress-testing, not replacement of human research.

---

## 4. Recommended Architecture

### 4.1 Core decision: thin orchestration, no heavyweight framework

Frameworks evaluated: Claude Agent SDK (a coding-agent harness — wrong shape and cost profile for persona fan-out), OpenAI Agents SDK (handoff-shaped), LangGraph (good graph orchestration, `Send()` fan-out), CrewAI (task automation dressed as roles), AG2/AutoGen (best off-the-shelf GroupChat but framework lock-in), CAMEL/OASIS (research-grade), Letta (persistent stateful agents — overkill unless personas must evolve across studies), LlamaIndex (use its ingestion pieces only).

**Verdict:** the simulation has two distinct execution shapes, and neither needs a framework:
- **Individual phase = pure fan-out.** Async Anthropic SDK + `asyncio.TaskGroup` + `Semaphore(20–50)`, or the Batch API for large runs. Embarrassingly parallel.
- **Group phase = small state machine.** Explicit control of speaking order, transcript state, and round limits — hand-rolled (or LangGraph if you want checkpointing for free). Borrow *patterns* from TinyTroupe (persona schema, results extractor), Concordia (Game Master as programmable moderator), and EDSL (typed question/results model) without adopting their code.

### 4.2 Claude platform features that carry the load

| Feature | Role in the platform |
|---|---|
| **Files API** | Upload each material once; reference by `file_id` in all 100 calls |
| **Prompt caching** | Shared materials + shared instructions in a cached prefix (0.1× read price); persona card + format spec after the breakpoint. Also a *throughput* feature: cache reads don't count against input-token rate limits, which is what makes 100 concurrent 50k-token calls feasible on a standard tier |
| **Structured outputs** (`json_schema`) | Guaranteed-valid responses in the user's assigned format — Likert + sentiment + free-text fields, zero parse failures; works in batches |
| **Batch API** | 50% off input *and* output; stacks with caching (use the 1-hour cache); ideal for the individual-reaction fan-out; wrong for interactive group rounds |
| **Native PDF/vision** | PDFs processed as text + page images (charts and figures are "seen"); images native; PPTX converted first (MarkItDown for text, or LibreOffice-render slides → images when the *design* matters) |
| **Model tiering** | Haiku 4.5 for individual reactions at scale; Sonnet for group deliberation and analysis; Opus/top-tier only for the final cross-population synthesis |

**No RAG in v1.** With materials ≲100–200k tokens per run, fixed for the run, and every persona reacting to the whole thing, context-stuffing + caching beats retrieval on both quality and simplicity. Add a local vector store (sqlite-vec, then pgvector) later only for cross-run search over accumulated responses.

### 4.3 Application stack (local-first → web later)

- **Backend:** Python + FastAPI + async Anthropic SDK. Runs are rows in a `runs`/`jobs` table so they're resumable; progress streamed to the UI via SSE. No Celery/Redis locally.
- **Frontend:** React (Vite) SPA — this app is UI-heavy (persona roster, group assignment, material library, live run progress, transcript viewers, analysis dashboards), which rules out Streamlit beyond a week-1 spike.
- **Database:** SQLite (WAL mode) via SQLModel/SQLAlchemy — the Postgres migration at web-deployment time is a connection-string change.
- **Packaging:** single process (FastAPI serves the built React bundle) for the simplest local install; `docker compose up` as the portable option; web deployment later = same containers on Fly/Railway + Postgres + object storage for uploads.

### 4.4 Data model (core entities)

`Persona` (name, persona card, grounding sources, tags) · `Material` (file, type, processed/cached representation) · `Group` (persona membership, optional moderator config) · `Protocol` (interaction instructions: phases, rounds, speaking order, moderator probes) · `ResponseFormat` (user-defined JSON schema / question set) · `Run` (protocol + personas/groups + materials + model config, immutable once started) · `Response` / `Turn` (every individual answer and group utterance, fully persisted) · `Analysis` (computed aggregates + LLM synthesis reports).

### 4.5 Run pipeline

1. **Ingest:** normalize materials (PDF native; PPTX → markdown and/or slide images; transcripts cleaned); upload via Files API; warm the cache.
2. **Phase 1 — independent reactions (always first):** every persona reacts alone, in the assigned format, before seeing anyone else. This is the Delphi baseline and the anchor for measuring opinion shift.
3. **Phase 2 — group interaction (optional):** groups of ~3–8; moderator agent poses the instructions; round-robin with rotated order; each turn structured to include explicit agreement/disagreement fields; 2–3 rounds max; personas re-anchored to their cards each round.
4. **Phase 3 — post-discussion re-survey (optional):** same format as Phase 1 → individual-level shift measurement.
5. **Analysis:** deterministic stats first (distributions, within/between-group variance, shift metrics, per-subgroup breakdowns — pandas/scipy), then LLM synthesis (theme extraction per group and population, dissent report, quote-mined verbatims), with every claim linked back to stored transcripts.

### 4.6 Cost (arithmetic at current pricing: Haiku 4.5 $1/$5 per MTok, Sonnet $2/$10)

Assumptions: 100 personas × 50k tokens of shared material + 1.5k persona-specific input, 1.5k output each; group phase = 20 groups × 5 personas × 3 rounds = 300 turns at ~7.5k in / 0.4k out.

| Configuration | Haiku 4.5 | Sonnet |
|---|---|---|
| Individual phase, naive (no cache, no batch) | $5.90 | $11.80 |
| Individual phase, cache + batch | **$0.75** | **$1.50** |
| Group phase, with conversation-prefix caching | ~$1.30 | ~$2.60 |
| **Full run, well-engineered** | **≈ $2–3** | **≈ $4–6** |

Warning case: re-sending the full 50k material uncached in every group turn costs $17–34 for the discussion phase alone. Caching discipline is the single biggest cost lever.

---

## 5. Phased Build Plan

**Phase 0 — Validation spike (1–2 weeks).** CLI script, no UI: 10 personas from YAML cards, one PDF, Phase-1 fan-out with prompt caching and structured outputs, one 5-persona group discussion, JSON results. *Exit test: does the output feel insight-bearing? Do personas stay distinct?* This is where you discover prompt-design issues cheaply.

**Phase 1 — Core engine (1–2 weeks).** FastAPI service + SQLite schema; material ingestion pipeline (PDF/PPTX/transcript/image); persona CRUD; run executor with resumability, retries, and cost tracking; Batch API path for runs ≥ ~25 personas.

**Phase 2 — Web UI (1–2 weeks).** React app: material library, persona roster (create manually, generate from a spec, or ground from an uploaded transcript), group assignment (drag personas into groups), protocol builder (instructions, phases, rounds), response-format designer (build the JSON schema visually), live run dashboard (SSE progress per agent), transcript browser.

**Phase 3 — Group deliberation (1 week).** Moderator agent, round-robin with rotation, structured-disagreement turn schema, Phase-3 re-survey, anti-sycophancy checks (flag runs where within-group variance collapses).

**Phase 4 — Analysis (1–2 weeks).** Stats layer (distributions, variance, shift, subgroup breakdowns), LLM synthesis reports at individual/group/population levels, run comparison (same materials, different populations — the "A/B the memo" workflow), CSV/JSON export.

**Phase 5 — Hardening & deployment path (ongoing).** Docker Compose; auth; SQLite→Postgres migration scripts; object storage for uploads; deploy to a small cloud host when ready for remote use.

**Total to a complete local v1: roughly 6–8 weeks of focused effort.** The spike (Phase 0) is de-risked to days.

---

## 6. Risks

1. **Validity over-trust** — outputs look authoritative. Mitigate in the product: label results as synthetic estimation, always show distributions + dissent, keep transcripts one click away.
2. **Persona quality ceiling** — demographic-only personas are the documented weak point. Prioritize the transcript/document-grounded persona path early; it's also your differentiator.
3. **Group-dynamics artifacts** — convergence artifacts can masquerade as "consensus findings." The Delphi sequencing + shift metrics make the artifact itself measurable.
4. **API cost surprises** — enforce caching in the executor (fail loudly if a run would exceed a configurable budget); show projected cost before each run.
5. **Scope creep** — the market map shows a dozen adjacent products. The wedge is: *your materials, your personas, groups that actually deliberate, full transparency, runs for dollars.* Ship that before anything else.

---

## 7. Suggested Next Steps

1. **Approve the architecture direction** (thin orchestration on the Anthropic SDK; FastAPI + React + SQLite; no RAG in v1) — or flag constraints (e.g., must be TypeScript, must support local models via Ollama, multi-provider).
2. **Pick the first real use case** — the actual materials and population you'd run first (e.g., a report + 25 personas in 5 groups). Phase 0 should be built against it, not a toy.
3. **Decide persona sourcing for v1:** hand-authored cards, LLM-generated from a population spec, grounded from transcripts/interviews you have, or all three (recommended order: cards → generated → grounded).
4. **Run Phase 0** on that use case; review transcripts together and tune persona/moderator prompts before investing in UI.
5. **Then Phases 1–4** as above.

Open questions worth deciding early: single-user or multi-user from day one; whether personas persist and accumulate memory across studies (Letta-style) or reset per run (recommended for v1); how much of the analysis should be deterministic stats vs. LLM synthesis by default.

---

*Sources: full research digests with URLs available in the session record — key references include Park et al. 2024 (arXiv:2411.10109), TinyTroupe (github.com/microsoft/tinytroupe), Concordia (github.com/google-deepmind/concordia), EDSL (docs.expectedparrot.com), OASIS (github.com/camel-ai/oasis), SSR (arXiv:2510.08338), AAPOR Responsible AI Integration in Survey Research (2026), Anthropic platform docs (pricing, batch, prompt caching, structured outputs), and 2026 market coverage of Simile, Aaru, Evidenza, Artificial Societies, Viewpoints, Qualtrics Edge, and NIQ BASES.*
