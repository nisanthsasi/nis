# Agent contract (read before implementing any agent)

Every agent subclasses `BaseAgent[T]` (`the_panel/agents/base.py`) and sets:

| ClassVar | Meaning |
|---|---|
| `stage` | routing/budget key: `parser, analyst_film, analyst_scene, breakdown, style_bible, sequence_lens, lens, critique, integrator, department, auditor, judge` |
| `name` | snapshot folder + log name |
| `template` | registry key from `the_panel/prompts/registry.py` (NOT a filename) |
| `output_model` | the Pydantic model `messages.parse` validates against |
| `uses_header` | `False` only for L1–L4 (no Film Brief Header exists yet) |

`await agent.run(key=..., **variables)` renders the template with `variables`
(pydantic models are auto-dumped to dicts by `prepare`), calls the model with structured
output, validates, retries once with the error as a repair instruction, persists a snapshot
and returns `AgentResult` (`.parsed`, `.usage`, `.attempts`, `.over_budget`).

Override `check(parsed, variables)` to raise `ValueError` with a *repair instruction* for
agent-specific rules (scene_id matches, every shot has a beat_ref that exists, lens name
matches the card, set_piece ⇒ must_remember, …). Never call other agents from an agent.

Offline: `AgentContext.offline()` uses `the_panel.testing.FakeLLM`, which returns
schema-valid examples (or a scripted `responder`). Hints `scene_id`, `lens`, `sequence_id`,
`dept` are auto-derived from variables so ids line up.
