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

    def test_cross_section_tr_thresholds_not_flagged(self):
        """Different TR thresholds in different sections are intentional."""
        prompt = (
            "SECTION 6 — ABT\nTR >= 2.2*ATR5m means spike\n"
            "SECTION 9 — EXPANSION\nTR >= 1.2*ATR5m valid\nTR >= 1.4*ATR5m strong\n"
        )
        issues = rules.check_threshold_consistency(prompt)
        tr_issues = [i for i in issues if "TR" in i.message]
        assert len(tr_issues) == 0

    def test_same_section_abt_conflict_flagged(self):
        """Multiple TR thresholds WITHIN ABT section should be flagged."""
        prompt = (
            "SECTION 6 — ABT\nTR >= 2.2*ATR5m spike\nTR >= 1.8*ATR5m also spike\n"
        )
        issues = rules.check_threshold_consistency(prompt)
        tr_issues = [i for i in issues if "ABT" in i.message]
        assert len(tr_issues) == 1


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


class TestV15Modules:
    def test_v15_modules_not_checked_on_v14(self):
        """v15 module checks should not run on v14 prompts."""
        issues = rules.check_v15_modules(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_v15_modules_present(self):
        """v15 prompt with all modules should pass."""
        with open("prompts/satva_v15.0.0.txt") as f:
            prompt = f.read()
        issues = rules.check_v15_modules(prompt)
        assert len(issues) == 0

    def test_v15_missing_setup_d(self):
        """v15 prompt without Setup D should be flagged."""
        prompt = "SATVA v15.0.0\nHTF EXEC TAS RSI divergence VOL_EXPANDING VOL_CONTRACTING VOL_DRYUP PB_DEPTH PB_CANDLE\nTier 1 Tier 2 watchdog DATA_STALE"
        issues = rules.check_v15_modules(prompt)
        setup_d_issues = [i for i in issues if "Setup D" in i.message]
        assert len(setup_d_issues) == 1


class TestPartialExitTiers:
    def test_v14_skipped(self):
        issues = rules.check_partial_exit_tiers(MINIMAL_SATVA)
        assert len(issues) == 0

    def test_v15_correct_tiers(self):
        prompt = "SATVA v15.0.0\nSECTION 22 — PARTIAL EXIT ENGINE\nClose 40% of position\nClose 30% of position\nExit 30% trailing\n"
        issues = rules.check_partial_exit_tiers(prompt)
        assert len(issues) == 0


class TestVersionDetection:
    def test_detect_v14(self):
        assert rules._detect_version(MINIMAL_SATVA) == "v14"

    def test_detect_v15(self):
        assert rules._detect_version("SATVA v15.0.0 prompt") == "v15"


class TestSatvaValidatorIntegration:
    def test_full_satva_v14_prompt(self):
        """Load the actual SATVA v14 prompt and validate it."""
        with open("prompts/satva_v14.4.2.txt") as f:
            prompt = f.read()

        from prompt_validator.satva_validator import SatvaValidator
        validator = SatvaValidator()
        results = validator.validate(prompt)

        # Domain score should be high after fixes
        assert results["domain"].score >= 90
        # Combined should pass conditional threshold
        assert results["combined_score"] >= 75
        # Cross-section TR thresholds (ABT=2.2, Expansion=1.2/1.4) should NOT
        # be flagged — they are intentionally different across sections
        false_positive_tr = [
            i for i in results["domain"].issues
            if "inconsistent tr" in i.message.lower()
        ]
        assert len(false_positive_tr) == 0

    def test_full_satva_v15_prompt(self):
        """Load the actual SATVA v15 prompt and validate it."""
        with open("prompts/satva_v15.0.0.txt") as f:
            prompt = f.read()

        from prompt_validator.satva_validator import SatvaValidator
        validator = SatvaValidator()
        results = validator.validate(prompt)

        # Domain score should be high for a well-structured v15 prompt
        assert results["domain"].score >= 85
        # Combined should pass
        assert results["combined_score"] >= 70
        # Should not have any ERROR-level domain issues
        domain_errors = [
            i for i in results["domain"].issues
            if i.severity == Severity.ERROR
        ]
        assert len(domain_errors) == 0, (
            f"Unexpected domain errors: {[e.message for e in domain_errors]}"
        )
