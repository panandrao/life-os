# Persona Card Specification

**Prepared:** August 21, 2026
**Applies to:** Persona Lab Phase 0+ (`persona-lab/`), and forward to the v1 platform
**Companion to:** `research-and-plan.md` (research report and build plan)

This document specifies what a persona card is, what fields it contains, how
each field should be written, how cards are stored and rendered, and which
fields are reserved for future phases. The 45-persona UMW bank
(`persona-lab/personas/umw/`) is the reference implementation of the Standard
tier.

---

## 1. What a persona card is

A persona card is the **complete identity a sub-agent receives** — the only
thing that separates one agent from the other 99 in a run. At execution time
the card is rendered to markdown and injected into the prompt *after* the
cached shared materials, so the card is also the only per-persona token cost.

Three consequences drive the whole design:

1. **The card is a prompt, not a database record.** Every field must earn its
   tokens by changing how the agent responds. Fields that don't shift behavior
   (an office number, a hire date) are dead weight.
2. **Specificity is the variance engine.** The central failure mode of persona
   simulation — documented across the 2025–26 literature — is homogenization:
   agents collapsing into the same reasonable, agreeable voice. Demographic
   labels alone ("a 45-year-old professor") *cause* this, and worse, they make
   the model fill the gaps with stereotype. Concrete, idiosyncratic detail
   (a specific grievance, a professional scar, a pet metric) is what holds
   personas apart across rounds of group discussion.
3. **Stances must come with reasons.** A card that says only "skeptical of
   technology" produces a cartoon. A card that says *why* — what this person
   has seen, lost, or is responsible for — produces a position that can be
   argued with, defended, and genuinely moved, which is what makes group
   simulation informative.

## 2. The three tiers

Cards come in three tiers. Higher tiers strictly extend lower ones — same
format, more fields — so any card is importable at any time and can be
upgraded in place.

| Tier | Name | When to use | Evidence base |
|---|---|---|---|
| 1 | **Minimal** | Quick throwaway populations, smoke tests | Weakest — expect stereotype fill-in |
| 2 | **Standard** | Hand-authored or LLM-generated populations (the UMW bank) | Good variance if authored per §4 |
| 3 | **Grounded** | Personas built from real source material (interviews, transcripts, writing samples, survey answers) | Strongest — interview-grounded agents hit 85% of individuals' own test–retest accuracy (Park et al. 2024) and reduce demographic bias |

**Tier 3 is the destination.** The platform's differentiator is grounding
personas in materials you actually have — a persona derived from a real
interview transcript beats any authored card for fidelity. Phase 0 supports
Tier 3 structurally (extra fields auto-render, §5); a dedicated
transcript-to-card pipeline is Phase 2+ work.

## 3. Field specification

### 3.1 Identity block (required — Tier 1)

| Field | Type | Rules |
|---|---|---|
| `id` | string | Unique across the bank; stable forever (analysis joins on it); pattern `<cat>-<dept>-<nn>` recommended, e.g. `fac-che-03`, `stf-lib-01` |
| `name` | string | Full display name as used in group transcripts. Fictional unless the persona is a consented real-person twin |
| `role` | string | Job title plus load-bearing qualifiers ("Senior Lecturer", "and Department Chair", "Visiting"). Rank and contract status change what a person can safely say — include them |
| `department` | string | Organizational unit, spelled consistently across the bank — analysis groups by exact string |
| `category` | string | Population segment for aggregate analysis: `faculty`, `staff`, `student`, `alumni`, `external`... One word, consistent across the bank |

### 3.2 Standard block (Tier 2 — all optional, all recommended)

| Field | Type | What it does in the prompt |
|---|---|---|
| `pronouns` | string | Include when known; omission defaults the engine to they/them in summaries |
| `age` | integer | Life-stage anchor; combine with `years_at_institution` to imply career arc |
| `years_at_institution` | integer | Institutional memory and loyalty; a 26-year veteran and a year-one hire read the same memo differently |
| `education` | string | Credentials *and their story* — "ABD, left when his first child was born" does more work than a degree list |
| `background` | multiline | 2–4 sentences of career narrative: how they got here, what they own, what marked them. This is where professional scars live ("watched three waves of ed-tech sweep through K-12") |
| `personality` | map | Free-form keys, each one line. Convention: `temperament`, `communication_style`, `decision_style`. `communication_style` matters most in group phases — it is what keeps ten voices distinguishable in a transcript |
| `values` | list of strings | 3–4 items, ranked, *specific to this person* ("Measurement integrity — knowing how you know"), never generic virtues ("honesty", "excellence") |
| `viewpoints` | multiline | 3–5 sentences: current stances **with reasons**, live worries, and — critically — at least one internal tension (§4.3). This field does the most work in any simulation about a contested topic |
| `quirks` | string | 1–2 concrete behavioral tics ("keeps a spreadsheet of every promise made to the department, with dates"). Disproportionately effective at preventing voice collapse; also makes transcripts auditable at a glance |

### 3.3 Grounded block (Tier 3 — reserved, forward-compatible)

These fields are defined now so Tier 3 cards written today import cleanly;
engine-side special handling arrives in later phases. Until then they render
onto the card like any extra field.

| Field | Type | Purpose |
|---|---|---|
| `grounding` | map | Source evidence: `sources` (list of `{type, path/ref, date}` — interview, transcript, survey, writing_sample), `excerpts` (verbatim quotes from the person, the highest-value content on a Tier 3 card), `stated_positions` (positions taken in the source material, with citations back to it) |
| `speech_style` | multiline | Observed (not authored) voice description, ideally with verbatim phrases the person actually uses |
| `stances` | list | Structured positions: `{topic, position, strength: 1-5, basis}` — enables pre-registered stance tracking across a run instead of inferring shift from free text |
| `relationships` | list | `{persona_id, relation, valence}` — who they know in the population; activates when group assembly becomes network-aware |
| `provenance` | map | Card metadata, excluded from the rendered prompt in future engine versions: `created` (date), `method` (authored / generated / grounded), `author`, `version`, `consent` (for real-person twins: documented consent reference — required, no exceptions) |

### 3.4 Extensibility rule

**Any field not listed above is legal.** The engine preserves unknown fields
and renders them as titled card sections (`model_extra` in
`personalab/models.py`). This is deliberate: richer personas must never
require code changes. The only reserved namespace is §3.3; use anything else
freely (`teaching_load`, `committee_history`, `media_diet`...), knowing it
will appear on the card verbatim.

## 4. Authoring guidelines

### 4.1 Write the person, not the demographic

Every dimension where the card is silent gets filled by the model's priors —
which is where stereotyping enters. The fix is not more demographic labels;
it is more *particulars*. "58-year-old education professor" invites a
stereotype; "former elementary principal who watched three waves of
technology sweep through K-12 with little to show" is a specific person whose
skepticism has a shape and therefore has conditions under which it bends.

### 4.2 Give every stance a source

Format viewpoints as *position ← because ← experience*. Positions without
provenance make agents either immovable (nothing to argue against) or
instantly persuadable (nothing anchoring them). Positions with provenance
produce realistic deliberation: an interlocutor who addresses the underlying
experience can actually move the persona, and the transcript shows why.

### 4.3 Build in one internal tension

Real people are ambivalent where their interests cross. The single highest-
value authoring move is giving each persona at least one live contradiction:
the admissions counselor whose best applicant-insight (essays) is being eroded
by the same tools that help applicants like his younger self; the
accessibility coordinator for whom AI is both an unreviewed-procurement problem
and an assistive-technology right. Tension is what makes individual responses
non-obvious and group discussions worth reading. A persona with no tension is
a position paper, not a person.

### 4.4 Differentiate along many axes at once

A bank's value is its *joint* diversity. The UMW bank varies discipline,
rank, contract security (tenured / pre-tenure / lecturer / visiting /
classified staff), age and career stage, institutional tenure, technology
disposition (enthusiast → pragmatist → skeptic → threatened), what each
person is responsible for, and communication style. Check the bank as a
whole: if any two cards could swap `viewpoints` without anyone noticing,
one of them isn't done. Deliberately include perspectives that will be
uncomfortable in group discussion — a bank that agrees is a bank that
tells you nothing.

### 4.5 Length budget

Target **250–500 rendered tokens** (roughly 1,200–2,300 characters) for
Standard-tier cards; the UMW bank averages ~1,700 characters. Below ~150
tokens, stereotype fill-in dominates. Above ~700, returns diminish and
per-persona cost rises across every call — remember the card is re-sent on
every group-discussion turn. Tier 3 cards may run to ~1,000 tokens when
carrying verbatim excerpts; that is the one justified overage.

### 4.6 What to avoid

- **Virtue lists** — values shared by everyone differentiate no one.
- **Uniform positivity** — real populations contain the burned-out, the
  bitter, and the checked-out; banks without them over-predict enthusiasm.
- **Trait bundles that just re-encode a demographic** — if the persona's
  entire viewpoint is derivable from their age and field, the card adds
  stereotype, not signal.
- **Stances phrased as conclusions the author wants** — cards written to
  produce a desired simulation result will produce it; that's leading the
  witness, and the run's findings will be worthless.
- **Real names or identifying details of actual people** without documented
  consent (`provenance.consent`) — this is a hard rule, not a style point.

## 5. Storage format and mechanics

- **YAML files**, one list per file, either top-level or under a `personas:`
  key. A bank is a directory; the loader reads every `*.yaml`/`*.yml`,
  enforces globally unique `id`s, and supports `include` / `exclude` /
  seeded `sample` selection at run time.
- **Multiline prose uses YAML block scalars** (`|`) — background, viewpoints,
  quirks read and diff cleanly.
- **Render order is fixed** by `Persona.card()`: identity → background →
  personality → values → viewpoints → quirks → extra fields. Identity first
  anchors the role; viewpoints late sit closest to the task instructions,
  where they most influence the response.
- **Validation:** `python -m personalab validate personas/umw` (bank-level
  counts + duplicate detection); `--card <id>` renders any single card for
  eyeballing. A machine-readable schema ships at
  `persona-lab/personas/persona.schema.json` for external editors and
  importers.
- **One person = one card.** Variants of a persona (for A/B-ing card designs)
  get distinct ids (`fac-che-03__v2`) and never coexist with the original in
  a run's population unless the run is explicitly about comparing them.

## 6. Reference example (Standard tier)

```yaml
- id: stf-its-01
  name: Brian Callahan
  category: staff
  role: Senior Systems Administrator
  department: Information Technology Services
  age: 39
  years_at_institution: 11
  education: B.S. in Information Systems, Old Dominion University; security certifications
  background: |
    Keeps identity management, storage, and half the campus's aging servers
    running. On call more weekends than not. Has watched departments buy
    software with grant money and then hand IT the integration, security
    review, and eternal maintenance.
  personality:
    temperament: Guarded, precise, dark humor of the perpetually on-call
    communication_style: Risk-and-requirements bullet points; allergic to vague asks
    decision_style: Least privilege, defense in depth, and who maintains this in year three?
  values:
    - Security and privacy of student data above convenience
    - Saying no early beats cleaning up later
    - Respect for operational reality
  viewpoints: |
    To him the AI wave looks like a thousand unsanctioned data flows: staff
    pasting student records into chatbots, departments buying AI add-ons with
    no security review. Wants an approved-tools process with teeth before any
    encouragement campaign. Not anti-AI — he uses it for scripting daily and
    it has genuinely changed his job — which is exactly why he takes the
    data-handling risk seriously.
  quirks: Reads vendor security whitepapers recreationally; keeps a "told you so" folder he has never once opened in anger
```

Why it works, against §4: the skepticism has a source (11 years of inherited
integration messes), the tension is explicit (daily AI user *and* chief AI
worrier), the values are his rather than everyone's, and the quirk makes his
transcript turns identifiable without a speaker label.

## 7. Authoring checklist

Before adding a card to a bank:

- [ ] `id` unique, patterned, and permanent
- [ ] Role includes rank/contract status; department string matches the bank's spelling
- [ ] Background contains at least one formative professional experience
- [ ] `communication_style` distinct from every other card in its likely group
- [ ] Values are person-specific, ranked, ≤4
- [ ] Every viewpoint has a *because*
- [ ] At least one internal tension
- [ ] 1,200–2,300 characters rendered (`validate --card <id>` to check)
- [ ] No real person's identity without documented consent
- [ ] Bank-level: could this card's viewpoints be swapped with another's unnoticed? If yes, sharpen it
