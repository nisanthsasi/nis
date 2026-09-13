"""Resonance scoring, the collapse function and the anti-groupthink rules (SPEC §5 P6).

Diversity needs a collapse function: the Integrator scores Option A and B on the Resonance
Rubric, this module weights those scores with the posture's rubric weights, applies the
consensus-device penalty, ranks the options and decides which HUMAN_QUESTIONs the plan must
carry to Gate 3. It also produces the *pre-scores* that feed the Integrator's anti-groupthink
hints — the lone high-fidelity vision that must survive as Option B, and the lone
high-engagement pleasure beat that must not die in committee.

Pre-scores are a deterministic heuristic over what a vision *declares* (beat coverage, energy
against target, declared conflicts, devices with setups). They are a routing hint for the
Integrator, never a judgement of the vision — the rubric is scored by the Integrator with the
scene in front of it, and weighed here.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from ..schemas.common import HumanQuestion
from ..schemas.plan import IntegratedScenePlan, Justification, PlanOption, ResonanceScore
from ..schemas.scene import Scene
from ..schemas.sequence_plan import SequenceSceneEntry
from ..schemas.vision import Critique, SceneVision
from .caps import CapLedger
from .posture import PosturePolicy

_WORD = re.compile(r"[a-zഀ-ൿ]{3,}")
_STOPWORDS = frozenset({"the", "and", "that", "this", "with", "from", "for", "has", "have", "her", "his", "she", "him", "its", "into", "not", "but", "are", "was", "will", "what", "who", "how", "when", "where", "under", "over", "gone", "then", "than"})


def normalise_device(name: str) -> str:
    return name.strip().lower()


def normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower()).rstrip(".!")


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS}


def _clamp(v: float) -> float:
    return round(max(0.0, min(10.0, v)), 2)


# --- weighting and ranking ---------------------------------------------------------


def score_options(plan: IntegratedScenePlan, policy: PosturePolicy) -> IntegratedScenePlan:
    """Fill ``weighted_total`` on both options from the posture's rubric weights (in place)."""
    policy.score(plan.resonance_A)
    policy.score(plan.resonance_B)
    return plan


def detect_consensus_devices(visions: Iterable[SceneVision], share: float) -> list[str]:
    """Devices used by more than ``share`` of the visions — the panel converging on a device is not the device being earned."""
    visions = list(visions)
    if not visions:
        return []
    counts: Counter[str] = Counter()
    for v in visions:
        counts.update(v.device_names)
    return sorted(d for d, c in counts.items() if c / len(visions) > share)


def apply_consensus_penalty(plan: IntegratedScenePlan, consensus_devices: Iterable[str], penalty: float, policy: PosturePolicy) -> IntegratedScenePlan:
    """Set ``consensus_device_penalty`` (Earned Freshness −penalty) on every option that uses a consensus device, then re-score.

    Authoritative and idempotent: an option that uses no consensus device carries no penalty.
    """
    consensus = {normalise_device(d) for d in consensus_devices}
    for label in ("A", "B"):
        option = plan.option(label)
        score = plan.resonance_scores[label]
        score.consensus_device_penalty = float(penalty) if _device_names(option) & consensus else 0.0
    return score_options(plan, policy)


def recommend(plan: IntegratedScenePlan, policy: PosturePolicy) -> str:
    """Rank A and B by weighted total, then the posture's tie-break order; the winner becomes ``plan.recommended``."""
    score_options(plan, policy)
    plan.recommended = policy.rank(plan.resonance_scores)[0]
    return plan.recommended


# --- pre-scores (anti-groupthink hints) ----------------------------------------------


def prescore_vision(
    vision: SceneVision,
    scene: Scene,
    policy: PosturePolicy,
    seq_entry: SequenceSceneEntry | None = None,
    *,
    consensus_devices: Iterable[str] = (),
    max_setups: int | None = None,
) -> ResonanceScore:
    """A deterministic heuristic pre-score of one vision — a routing hint, not a judgement.

    dramatic_fidelity: distinct valid beat_refs / beats (70%) + must_feel word overlap with the
    governing idea, key image and blocking (30%). emotional_impact: share of the tension curve
    whose beats the shots cover. engagement: energy_level against the sequence's energy_target,
    a pleasure offered, colour given a job. style_coherence: 10 minus 2 per declared Style Bible
    conflict and per device the posture does not permit. feasibility: shots against max_setups
    (estimated_setups × 1.25 unless given). earned_freshness: devices with setups minus consensus
    devices. The Integrator scores the rubric properly; this only decides who gets protected.
    """
    beats = {b.n for b in scene.beats} or {1}
    covered = {s.beat_ref for s in vision.shots} & beats
    coverage = len(covered) / len(beats)
    must_feel = _words(scene.must_feel)
    said = _words(" ".join([vision.governing_idea, vision.key_image, vision.blocking_note, vision.pleasure_offer]))
    overlap = (len(must_feel & said) / len(must_feel)) if must_feel else coverage
    fidelity = 10 * (0.7 * coverage + 0.3 * overlap)

    curve = scene.tension_curve
    if curve and len(curve) == len(scene.beats) and sum(curve) > 0:
        by_beat = {b.n: t for b, t in zip(scene.beats, curve)}
        impact = 10 * sum(by_beat[n] for n in covered) / sum(curve)
    else:
        impact = 10 * coverage

    target = seq_entry.energy_target if seq_entry is not None else scene.energy_target
    energy_match = 1 - abs(vision.energy_level - target) / 10
    offers_pleasure = 0.0 if vision.pleasure_offer.strip().lower().startswith("none") else 1.0
    colour_works = 1.0 if vision.colour_note.strip() else 0.0
    engagement = 10 * (0.5 * energy_match + 0.3 * offers_pleasure + 0.2 * colour_works)

    devices = vision.device_names
    unpermitted = {d for d in devices if not policy.permits(d)}
    coherence = 10 - 2 * len(vision.style_bible_conflicts) - 2 * len(unpermitted)

    cap = max_setups if max_setups is not None else math.ceil(scene.estimated_setups * 1.25)
    feasibility = 10 if len(vision.shots) <= cap else 10 - 2 * (len(vision.shots) - cap)

    consensus = {normalise_device(d) for d in consensus_devices}
    fresh, stale = devices - consensus, devices & consensus
    freshness = 6 + len(fresh) - 2 * len(stale)

    score = ResonanceScore(
        dramatic_fidelity=_clamp(fidelity),
        emotional_impact=_clamp(impact),
        engagement=_clamp(engagement),
        style_coherence=_clamp(coherence),
        feasibility=_clamp(feasibility),
        earned_freshness=_clamp(freshness),
        consensus_device_penalty=float(policy.consensus_device_penalty) if stale else 0.0,
        justifications=[
            Justification(criterion="dramatic_fidelity", note=f"hint: {len(covered)}/{len(beats)} beats covered; must_feel overlap {overlap:.2f}"),
            Justification(criterion="emotional_impact", note="hint: tension-weighted beat coverage"),
            Justification(criterion="engagement", note=f"hint: energy {vision.energy_level} vs target {target}; pleasure {'offered' if offers_pleasure else 'none'}; colour {'given a job' if colour_works else 'silent'}"),
            Justification(criterion="style_coherence", note=f"hint: {len(vision.style_bible_conflicts)} declared conflicts; unpermitted devices {sorted(unpermitted)}"),
            Justification(criterion="feasibility", note=f"hint: {len(vision.shots)} shots vs max_setups {cap}"),
            Justification(criterion="earned_freshness", note=f"hint: earned devices {sorted(fresh)}; consensus devices {sorted(stale)}"),
        ],
    )
    return policy.score(score)


def apply_critique_revisions(visions: Iterable[SceneVision], critiques: Iterable[Critique]) -> dict[str, SceneVision]:
    """Visions by lens with each critique's ONE revised element applied (a revision that does not validate is ignored)."""
    by_lens = {v.lens: v for v in visions}
    for c in critiques:
        vision = by_lens.get(c.lens)
        if vision is None or not c.revised_element or c.revised_value is None:
            continue
        try:
            by_lens[c.lens] = SceneVision.model_validate({**vision.model_dump(mode="json"), c.revised_element: c.revised_value})
        except ValidationError:
            continue
    return by_lens


def prescore_panel(
    visions: Iterable[SceneVision],
    scene: Scene,
    policy: PosturePolicy,
    seq_entry: SequenceSceneEntry | None = None,
    *,
    critiques: Iterable[Critique] = (),
    consensus_devices: Iterable[str] | None = None,
    max_setups: int | None = None,
) -> dict[str, ResonanceScore]:
    """Pre-score every vision (after Round-2 revisions) — the input to the two lone-vision rules."""
    visions = list(visions)
    consensus = list(consensus_devices) if consensus_devices is not None else detect_consensus_devices(visions, policy.consensus_device_share)
    revised = apply_critique_revisions(visions, critiques)
    return {lens: prescore_vision(v, scene, policy, seq_entry, consensus_devices=consensus, max_setups=max_setups) for lens, v in revised.items()}


def lone_high_fidelity(prescores: Mapping[str, ResonanceScore]) -> str | None:
    """The one lens with the strictly highest Dramatic Fidelity pre-score — preserved as Option B even if its total is lower."""
    if len(prescores) < 2:
        return None
    top = max(s.dramatic_fidelity for s in prescores.values())
    leaders = [lens for lens, s in prescores.items() if s.dramatic_fidelity == top]
    return leaders[0] if len(leaders) == 1 else None


def lone_high_engagement(prescores: Mapping[str, ResonanceScore], visions: Iterable[SceneVision], threshold: float) -> dict[str, Any] | None:
    """The pleasure beat of the single lens whose Engagement pre-score reaches ``threshold`` — carried into A or B."""
    qualifying = [lens for lens, s in prescores.items() if s.engagement >= threshold]
    if len(qualifying) != 1:
        return None
    lens = qualifying[0]
    vision = next((v for v in visions if v.lens == lens), None)
    if vision is None:
        return None
    return {"lens": lens, "pleasure_offer": vision.pleasure_offer, "engagement": prescores[lens].engagement}


# --- caps, permissions and the human gate ----------------------------------------


def _device_names(option: PlanOption) -> set[str]:
    return {normalise_device(d.device) for d in option.devices_used}


def over_cap_devices(option: PlanOption, ledger: CapLedger, scene_id: str) -> list[str]:
    """Devices in ``option`` that would push a film cap over its limit, counting every use in the option against spends by other scenes."""
    uses: dict[str, int] = defaultdict(int)
    names: dict[str, set[str]] = defaultdict(set)
    for d in option.devices_used:
        key = ledger.cap_key(d.device)
        if key is None:
            continue
        uses[key] += 1
        names[key].add(normalise_device(d.device))
    over: list[str] = []
    for key, n in uses.items():
        limit = getattr(ledger.caps, key)
        if limit is None:
            continue
        elsewhere = sum(1 for s in ledger.spends[key] if s.scene_id != scene_id)
        if elsewhere + n > limit:
            over.extend(sorted(names[key]))
    return over


def unpermitted_devices(option: PlanOption, policy: PosturePolicy) -> list[str]:
    """Devices in ``option`` the Style Bible's device_permissions do not allow."""
    return sorted(d for d in _device_names(option) if not policy.permits(d))


def blocked_devices(option: PlanOption, ledger: CapLedger, policy: PosturePolicy, scene_id: str) -> set[str]:
    """Devices the panel must not spend: over cap or not permitted — each is a HUMAN_QUESTION, never a silent spend."""
    return set(over_cap_devices(option, ledger, scene_id)) | set(unpermitted_devices(option, policy))


def needs_human_question(plan: IntegratedScenePlan, policy: PosturePolicy, ledger: CapLedger, *, conflicts: Iterable[str] = ()) -> list[HumanQuestion]:
    """The HUMAN_QUESTIONs P6 escalates: the top two options differ in governing idea; an option needs a Style Bible amendment; a device is over cap or not permitted.

    ``conflicts`` are the visions' declared style_bible_conflicts (the plan itself carries
    only unresolved_tensions and rationales). Ids continue the plan's own numbering.
    """
    questions: list[HumanQuestion] = []
    counter = len(plan.human_questions)

    def ask(question: str, options: list[str], conservative: int, rationale: str) -> None:
        nonlocal counter
        counter += 1
        questions.append(HumanQuestion(id=f"HQ-{plan.scene_id}-{counter}", scene_id=plan.scene_id, raised_by="panel", question=question, options=options, conservative_option=conservative, rationale=rationale))

    idea_a, idea_b = normalise_text(plan.option_A.governing_idea), normalise_text(plan.option_B.governing_idea)
    if idea_a and idea_b and idea_a != idea_b:
        ask(
            "Option A and Option B differ in governing idea — which idea directs this scene?",
            [f"A: {plan.option_A.governing_idea}", f"B: {plan.option_B.governing_idea}"],
            0 if plan.recommended == "A" else 1,
            f"the top two options differ in governing_idea; the panel recommends {plan.recommended} on the Resonance Rubric",
        )
    mentions = [t for t in [*plan.unresolved_tensions, plan.option_A.rationale, plan.option_B.rationale, *conflicts] if "amend" in t.lower()]
    if mentions:
        ask(
            "An option requires a Style Bible amendment — amend the constitution, or restage within it?",
            [f"Amend the Style Bible: {mentions[0][:200]}", "Keep the Style Bible as approved; restage the scene within it"],
            1,
            "; ".join(m[:200] for m in mentions[:3]),
        )
    seen: set[str] = set()
    for option in (plan.option_A, plan.option_B):
        for device in over_cap_devices(option, ledger, plan.scene_id):
            if device in seen:
                continue
            seen.add(device)
            ask(
                f"'{device}' in Option {option.label} would exceed the film cap ({ledger.position(device)} already spent) — replace it, or raise an amendment?",
                [f"Replace '{device}' with an earned alternative that keeps the beat", f"Raise a Style Bible amendment extending the {ledger.cap_key(device)} cap"],
                0,
                "over-cap devices are never spent silently (P7)",
            )
        for device in unpermitted_devices(option, policy):
            if device in seen:
                continue
            seen.add(device)
            ask(
                f"'{device}' in Option {option.label} is not in the Style Bible's device_permissions — replace it, or raise an amendment?",
                [f"Replace '{device}' with a permitted device that pays off the same beat", f"Raise a Style Bible amendment permitting '{device}' and naming what it must pay off"],
                0,
                "a device outside device_permissions is a Style Bible conflict, not a default (law 5)",
            )
    return questions
