# THE PANEL — AI Director Prompt & Build Suite

A multi-lens directing system: **script → understanding → deliberation → department directives**.
Built for a director-writer working in Malayalam cinema and Indian OTT, with world-cinema grounding.
The full design document is in [`docs/SPEC.md`](docs/SPEC.md).

"Build an AI Director" is not one clever prompt. It is a **context pipeline** that converts a screenplay
into a coherent, department-ready directing plan by (1) constructing a structured *understanding* before
any visual decision is allowed; (2) generating aesthetic *diversity* through constrained priors — an
auteur bloc and a commercial-energy bloc of lenses; (3) *collapsing* that diversity into one plan via an
Integrator bound by a per-film constitution (the Style Bible), whose commercial-posture dial decides how
much pleasure, energy and colour weigh against style purity; (4) keeping the human director sovereign.

## Pipeline

```
L0 INGEST      Fountain / FDX / PDF / DOCX (Malayalam script, Manglish, English) → raw text + page map
L1 PARSE       → Scene[] skeletons (slug, INT/EXT, D/N, characters, dialogue blocks, action lines)
L2 UNDERSTAND  Film-level: theme, structure model, arcs, motifs, mechanism, set-piece candidates, star cast, release target
               Scene-level: objective/obstacle/tactic/turn, rasa, temperature, must-feel, pleasure, set-piece, load-bearing flag
L3 BREAKDOWN   Production breakdown per scene (incl. set-piece, song, choreography, crowd costs) + film-level location/cast/cost map
L4 STYLE BIBLE Form · Structure · Style; audience promise; commercial posture; pleasure map; structural hooks;
               device permissions and caps; lens affinity
               ─────────── FILM BRIEF HEADER frozen & cached here ───────────
L5 PANEL       Sequence-level (shape, energy curve, pleasure placement) → scene-level (shots)
               Lenses in parallel → cross-critique (steal / risk / conflict)
L6 INTEGRATE   Integrator → IntegratedScenePlan (Option A + B, shots, blocking, pleasure beat, energy check, attributions, scores)
L7 DEPARTMENTS Cinematography · Editing · Colour · Music/BGM & Song · Sound Design · Production Design/Mise-en-scène · Performance
L8 AUDIT       Continuity/Coherence · Feasibility/Compliance · Earned-Device · Engagement
HUMAN REVIEW   Digest (pitch voice) → decisions → Decision Log → Style Bible amendments → re-run affected scenes
PERSIST        SQLite state + markdown per scene into the Obsidian vault + Commercial Hooks Ledger
```

**Granularity rule.** Sequence-level deliberation first, then scene-level. Never the reverse.
**Posture rule.** `style_bible.commercial_posture` (0–10) is read — never hardcoded — by the rubric
weights, the panel sizer, the device audit, the caps and the department prompts. 0–3 arthouse · 4–6 hybrid · 7–10 mass.

## The nine laws

1. Understanding precedes vision. 2. Every stage speaks schema. 3. A lens is a prior, not a costume.
4. Diversity needs a collapse function. 5. The Style Bible is the constitution. 6. Departments derive; they
do not reinvent. 7. Coherence is a separate pass. 8. The human is sovereign. 9. Pleasure is engineered, not hoped for.

## Install

```bash
cd the_panel
uv sync --extra dev          # Python 3.12, deps from pyproject.toml
uv run pytest -q             # everything runs offline against a fake model client
export ANTHROPIC_API_KEY=…   # only needed for live runs
```

Model IDs live in `config.yaml` (`models.fast`, `models.reasoning`, `models.judge`) — verify them against
docs.claude.com before a live run. Parse and breakdown route to the fast model; understanding, lenses,
the integrator, departments and auditors route to the reasoning model. The Film Brief Header is
prompt-cached (1h TTL) into every call after L4.

## Usage (CLI)

```bash
uv run panel ingest script.fountain                 # L0/L1 → parsed script
uv run panel analyse                                # L2 film + scenes
uv run panel breakdown --budget-tier low            # L3 (+ breakdown.xlsx)
uv run panel bible --intent CLAUDE.md               # L4 draft
uv run panel bible approve --by nisanth --posture 5 # Gate 1: freezes the Film Brief Header
uv run panel sequence SEQ1                          # Round 0 → SequencePlan (Gate 2 optional)
uv run panel panel S3                               # Rounds 1–3 → IntegratedScenePlan
uv run panel departments S3                         # L7
uv run panel audit SEQ1                             # L8
uv run panel review S3                              # Gate 3: A | B | custom, overrides, amendments
uv run panel export                                 # xlsx, Obsidian vault, director's notes PDF, hooks
uv run panel run-all script.fountain --offline      # end-to-end dry run with the fake client
```

## Layout

```
the_panel/schemas/       Pydantic v2 contract: film_brief, scene, sequence_plan, style_bible, vision, plan,
                         directive, audits, decisions, hooks_ledger, breakdown
the_panel/prompts/       P0…P11 templates (*.md.j2), lenses/*.yaml lens cards, posture_presets.yaml, registry
the_panel/ingest/        fountain, fdx, pdf, docx, normalise (Malayalam/Manglish safe)
the_panel/agents/        base (render → call → validate → one repair retry → persist), parser, analyst,
                         breakdown, style_bible, lens, integrator, departments/, auditors/, review, judge
the_panel/orchestrator/  pipeline (state machine), panel (parallel rounds), scoring, lenses, posture, caps,
                         header, routing, understand, breakdown, bible, departments, audit, review
the_panel/store/         SQLite via sqlmodel + versioned JSON snapshots
the_panel/export/        xlsx, Obsidian markdown, director's-notes PDF, hooks ledger
the_panel/testing/       FakeLLM + schema-driven example builder (offline runs, tests)
the_panel/eval/          golden-scene harness, judge grading, cost dashboard, batch mode
tests/                   golden scripts, schema/posture/prompt-render/agent/orchestrator tests
```

## Posture presets (every value overridable in the Style Bible)

| Dial | Arthouse 0–3 | Hybrid 4–6 | Mass 7–10 |
|---|---|---|---|
| Rubric weights (DF/EI/EN/SC/FE/EF) | .30/.25/.05/.20/.10/.10 | .25/.25/.15/.15/.10/.10 | .20/.25/.25/.10/.10/.10 |
| Panel mix (primaries) | 3 auteur; ≥1 commercial secondary | ≥1 auteur + ≥1 commercial | ≥2 commercial; ≥1 auteur secondary |
| Elevation / slow-mo / needle-drop caps | 1 / 1 / 0 | 3 / 3 / 2 | 5 / ∞ / 4 |
| Max pleasure gap (screen min) | not audited | ~10 | ~6 |
| must_remember per act | ≥0 | ≥1 | ≥2 |

*A posture-2 film with a perfect earned elevation still passes the Earned-Device audit — it spends its single cap.*
