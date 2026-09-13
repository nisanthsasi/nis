# Lens cards

A lens is a **constrained prior**, not a costume. Each card is a YAML file, `<name>.yaml`, whose
stem is a roster name from `the_panel/prompts/registry.py` (`AUTEUR_LENSES`, `AUTEUR_EXTENSION_LENSES`,
`COMMERCIAL_LENSES`, `COMMERCIAL_EXTENSION_LENSES`, `DP_LENSES`, `CRAFT_LENSES`). The loader
(`the_panel/prompts/loader.py`) validates every card against `LensCard` and refuses the roster if one
is missing, mis-blocked or reads like an impersonation.

## The no-impersonation rule (law 3)

A lens applies **documented, widely analysed craft principles** associated with a filmmaker's work.
It never speaks as the person. Cards and lens outputs may not contain:

- invented quotes or attributed lines (`"…" — Name`),
- anecdotes or biography (`once said`, `as he put it`, `I remember`),
- "as [name] would say" framing.

`filmmaker_basis` must begin `craft principles associated with …` — principles only. The P5 / P5s / P6
prompts say so again to the model, and `BaseAgent` rejects any output that slips into first person.

## Card format (SPEC §4.4)

```yaml
name: rajamouli                 # snake_case; must equal the file stem and a roster name
bloc: commercial                # auteur | commercial (directing) · dp · craft
filmmaker_basis: "craft principles associated with S.S. Rajamouli's films"
conviction: "spectacle is emotion at scale; an elevation is a payoff, never a gift"
decision_rules:                 # when <dramatic situation> → do <the lens's move>
  - {when: "elevation", do: "plant it three scenes earlier; land it on a character choice; then crowd and BGM detonate"}
signature_devices: [earned elevation, interval image, chorus cutaway, slow motion on the decision]
refusals: [irony, unearned mass beats, ambiguity at the climax]
blind_spots: [subtlety, realism, restraint, budget]     # declared; the lens's risks must reckon with them
dp_pairing: kk_senthil_kumar    # directing lenses only — a DP card name
best_for: [mass moments, interval blocks, finales]
slate_fit: "THOOKKAM's mass ceiling"                   # optional
posture_range: [4, 10]          # postures at which this lens may be a PRIMARY
principles: [...]               # DP and craft cards only — the principles the lens applies
```

Rules the validator enforces:

- `posture_range` is `[lo, hi]`, both 0–10, `lo ≤ hi`. Directing lenses derive it from bloc and
  `best_for` (a commercial card reaches ≥ 7; an auteur card reaches down to ≤ 3). DP and craft cards
  are `[0, 10]` — they serve any posture.
- Directing lenses (`auteur` / `commercial`) name a `dp_pairing` that exists in `DP_LENSES`; DP and
  craft cards carry `principles` and no `dp_pairing`.
- `decision_rules` entries have both `when` and `do`; every list is non-empty.

## How the cards are used

- `load_lens_card(name, with_dp_principles=True)` hands P5 / P5s / P6 the card as `lens_card`; a
  directing lens also receives its paired DP's `principles` as `dp_principles`, so it lights and moves
  by its cinematographer.
- `directing_cards_for_posture(posture)` lists the lenses whose `posture_range` admits the Style
  Bible's `commercial_posture` as a primary — P4's lens-affinity check reads it.
- Craft cards (editing, sound, music, BGM & song, design, performance, star & ensemble) are the priors
  the department heads (P8.x) and the Integrator's handoff stances draw on; they are not seated at the
  scene-level panel.
