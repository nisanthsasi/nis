"""Tests for SATVA domain-specific validation rules."""

import pytest
from prompt_validator.result import Severity, Category
from prompt_validator import satva_rules as rules


MINIMAL_SATVA = """
SECTION 0 — AXIOMS
A0. Determinism: Every output must be computable from defined inputs.
SECTION 1 — DATA CONTRACT
TICK_SIZE, ROUND_STEP, SESSION_OPEN, SESSION_CLOSE, PDO, PDH, PDL, PDC
CRITICAL-PATH INPUTS (if missing → SESSION_LOCK / HALT)
SECTION 2 — CORE MEASUREMENTS
TR[i] = max(High[i]-Low[i], abs(High[i]-Close[i-1]), abs(Low[i]-Close[i-1]))
ATR5m = SMA(TR, 14) on 5m
ATR_prev = mean(ATR5m values over prior 24 bars)
SLIPPAGE_PAD = SLIPPAGE_BASE
SECTION 3 — SESSION GOVERNOR
SessionLossR >= 2.0 → SESSION_LOCK
SECTION 5 — DETERMINISTIC LEVEL SET
L = {PDO, PDH, PDL, PDC, VWAP_session}
SECTION 6 — ABT
ABT_ACTIVE = TRUE for next 6 bars
SECTION 8 — COMPRESSION ENGINE
OverlapPct = OverlapRange / MedianRange
Contraction = ATR5m / ATR_prev
CompressionValid if ALL conditions met
SECTION 9 — EXPANSION
ExpansionValid if TR >= 1.2*ATR5m
SECTION 10 — ENTROPY
EntropyScore = 100 * (sum / 20)
SECTION 12 — RCS
RCS = 0.30*HTF + 0.20*VOL + 0.20*BEH + 0.15*LVL + 0.15*TIME
SECTION 13 — REGIME BANNER
REGIME = TREND or RANGE or UNCLEAR or SHOCK
SECTION 15 — SES
SES = 0.30*TRIG + 0.25*STR + 0.25*LVLQ + 0.20*EFF
SECTION 16 — SETUPS
Setup A, Setup B, Setup C
SECTION 17 — TARGETS
T1 = Entry +/- T1_distance
SECTION 19 — RISK DEFINITIONS
R_trade = |Entry - Stop|
SECTION 22 — FSM
States: FLAT, ARMED, IN_POSITION, COOLDOWN, SESSION_LOCK, MEG_LOCK
FLAT → ARMED
ARMED → IN_POSITION
ARMED → FLAT
IN_POSITION → FLAT
IN_POSITION → SESSION_LOCK
MEG_LOCK → FLAT when Exp_M > 0
SECTION 23 — OUTPUT FORMAT
Print every update in same order.
SECTION 24 — GOVERNANCE LOG
GOV-TEST-01
Section: 1
Before: old rule
After: new rule
Rationale: testing
FREEZE DECLARATION
LOCK STATEMENT
Eff = StopDist / ATR5m
Exp_M = (WinRate*AvgWin) - (LossRate*AvgLoss)
"""


class TestSectionCompleteness:
    def test_complete_prompt(self):
        issues = rules.check_section_completeness(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_missing_sections(self):
        prompt = "SECTION 0 — AXIOMS\nSECTION 1 — DATA\n"
        issues = rules.check_section_completeness(prompt)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR


class TestFreezeDeclaration:
    def test_has_freeze(self):
        issues = rules.check_freeze_declaration(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_missing_freeze(self):
        issues = rules.check_freeze_declaration("Some prompt without freeze.")
        assert any("freeze" in i.message.lower() for i in issues)


class TestFormulaDefinitions:
    def test_all_formulas_present(self):
        issues = rules.check_formula_definitions(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_missing_formula(self):
        prompt = "No formulas defined here."
        issues = rules.check_formula_definitions(prompt)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR


class TestBinCoverage:
    def test_correct_rcs_weights(self):
        issues = rules.check_bin_coverage(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_wrong_rcs_weights(self):
        prompt = "RCS = 0.30*HTF + 0.20*VOL + 0.20*BEH + 0.15*LVL + 0.10*TIME"
        issues = rules.check_bin_coverage(prompt)
        assert len(issues) == 1
        assert "RCS weights" in issues[0].message


class TestThresholdConsistency:
    def test_consistent_loss_cap(self):
        prompt = "SessionLossR >= 2.0 triggers lock. SessionLossR >= 2.0 again."
        issues = rules.check_threshold_consistency(prompt)
        loss_issues = [i for i in issues if "SessionLossR" in i.message]
        assert len(loss_issues) == 0

    def test_inconsistent_loss_cap(self):
        prompt = "SessionLossR >= 2.0 triggers lock. But also SessionLossR >= 3.0 elsewhere."
        issues = rules.check_threshold_consistency(prompt)
        loss_issues = [i for i in issues if "SessionLossR" in i.message]
        assert len(loss_issues) == 1


class TestFSM:
    def test_all_states_present(self):
        issues = rules.check_fsm_states(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_missing_state(self):
        prompt = "States: FLAT, ARMED, IN_POSITION"
        issues = rules.check_fsm_states(prompt)
        assert len(issues) == 1

    def test_transitions_present(self):
        issues = rules.check_fsm_transitions(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_meg_lock_has_exit(self):
        issues = rules.check_fsm_dead_states(MINIMAL_SATVA)
        meg_issues = [i for i in issues if "MEG_LOCK" in i.message]
        assert len(meg_issues) == 0


class TestDeterminism:
    def test_clean_prompt(self):
        issues = rules.check_determinism("All outputs are computed from inputs.")
        assert len(issues) == 0

    def test_judgment_words(self):
        issues = rules.check_determinism("Use your judgment to decide. It could be anything.")
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR


class TestHaltConditions:
    def test_has_halt(self):
        issues = rules.check_halt_conditions(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_no_halt(self):
        issues = rules.check_halt_conditions("Just compute the answer.")
        assert any(i.severity == Severity.ERROR for i in issues)


class TestCrossReferences:
    def test_all_defined(self):
        issues = rules.check_cross_references(MINIMAL_SATVA)
        assert len(issues) == 0


class TestGovernance:
    def test_governance_present(self):
        issues = rules.check_governance_entries(MINIMAL_SATVA)
        # Should find GOV-TEST-01 with all fields
        error_issues = [i for i in issues if i.severity == Severity.ERROR]
        assert len(error_issues) == 0

    def test_no_governance(self):
        issues = rules.check_governance_entries("No gov entries here.")
        assert len(issues) == 1
        assert issues[0].severity == Severity.INFO


class TestSatvaValidatorIntegration:
    def test_full_satva_prompt(self):
        """Load the actual SATVA prompt and validate it."""
        with open("prompts/satva_v14.4.2.txt") as f:
            prompt = f.read()

        from prompt_validator.satva_validator import SatvaValidator
        validator = SatvaValidator()
        results = validator.validate(prompt)

        # Domain score should be high after fixes
        assert results["domain"].score >= 80
        # Combined should pass conditional threshold
        assert results["combined_score"] >= 70
        # Should detect the intentionally varied TR thresholds
        threshold_issues = [
            i for i in results["domain"].issues
            if "threshold" in i.message.lower() or "TR" in i.detail
        ]
        assert len(threshold_issues) >= 1
