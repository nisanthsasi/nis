"""Tests for all 5 industry-domain validators: MEDRA, AEGIS, LEXIS, QUANTA, SENTINEL."""

import pytest
from prompt_validator.result import Severity, Category


# =====================================================================
# MEDRA — Medical/Clinical Decision Systems
# =====================================================================

from prompt_validator import medra_rules

MINIMAL_MEDRA = """
You are a deterministic clinical decision support system.
SECTION 0 — AXIOMS
A0. Determinism: Every clinical output must be computable.
SECTION 1 — PATIENT DATA CONTRACT
PATIENT_ID, AGE, WEIGHT_KG, ALLERGIES[], MEDICATIONS[]
CRITICAL-PATH INPUTS (if missing → HALT)
SECTION 2 — VITAL SIGNS
HR: 60-100 bpm
SECTION 3 — TRIAGE ENGINE
GREEN: All vitals normal
YELLOW: One vital abnormal
ORANGE: Two+ vitals abnormal
RED: Critical vital
BLACK: Cardiac arrest — palliative pathway, attending review required
OVERRIDE: Attending physician can override
GREEN → YELLOW on deterioration
YELLOW → ORANGE on second abnormal
ORANGE → RED on critical threshold
RED → BLACK after resuscitation attempt
SECTION 4 — DOSAGE CALCULATIONS
DOSE_WEIGHT = prescribed_mg_per_kg * WEIGHT_KG
BSA = 0.007184 * (HEIGHT_CM ^ 0.725) * (WEIGHT_KG ^ 0.425)
CrCl = ((140 - AGE) * WEIGHT_KG) / (72 * CREATININE) * (0.85 if SEX == F)
GFR = 175 * (CREATININE ^ -1.154) * (AGE ^ -0.203)
AdjustedDose = DOSE_WEIGHT * (CrCl / 120)
InfusionRate = (DOSE_WEIGHT * 60) / CONCENTRATION
MAX_DAILY = drug_specific_max_mg_per_day
PeakTrough = measure_at_steady_state
Units: mg, mL, kg, mcg/kg/min
SECTION 5 — DRUG INTERACTIONS
Interaction severity: CONTRAINDICATED, MAJOR, MODERATE, MINOR
Interaction matrix lookup: pair (DRUG_A, DRUG_B)
SECTION 6 — CONTRAINDICATIONS
Allergy check, renal function (CrCl), hepatic function (ALT), pregnancy, age limits
SECTION 7 — CLINICAL DECISION TREE
Evidence-based rules, Grade A (RCT), Grade B, Grade C
SECTION 8 — ESCALATION PROTOCOL
HALT → attending notification, Code Blue
SECTION 9 — OUTPUT FORMAT
Print every clinical decision in exact order.
SECTION 10 — GOVERNANCE LOG
GOV-MED-001
Section: 4
Before: old formula
After: new formula
Rationale: FDA guidance
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestMedra:
    def test_section_completeness(self):
        assert medra_rules.check_section_completeness(MINIMAL_MEDRA) == []

    def test_missing_sections(self):
        issues = medra_rules.check_section_completeness("SECTION 0 — AXIOMS")
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR

    def test_formula_definitions(self):
        assert medra_rules.check_formula_definitions(MINIMAL_MEDRA) == []

    def test_triage_states(self):
        assert medra_rules.check_triage_states(MINIMAL_MEDRA) == []

    def test_missing_triage_states(self):
        issues = medra_rules.check_triage_states("GREEN YELLOW only")
        assert len(issues) == 1

    def test_triage_transitions(self):
        assert medra_rules.check_triage_transitions(MINIMAL_MEDRA) == []

    def test_determinism_clean(self):
        assert medra_rules.check_determinism("All outputs are computed.") == []

    def test_determinism_dirty(self):
        issues = medra_rules.check_determinism("Use your judgment to decide.")
        assert len(issues) == 1

    def test_safety_halts(self):
        assert medra_rules.check_safety_halts(MINIMAL_MEDRA) == []

    def test_interaction_matrix(self):
        assert medra_rules.check_interaction_matrix(MINIMAL_MEDRA) == []

    def test_contraindication_coverage(self):
        assert medra_rules.check_contraindication_coverage(MINIMAL_MEDRA) == []

    def test_integration(self):
        from prompt_validator.medra_validator import MedraValidator
        with open("prompts/medra_clinical.txt") as f:
            prompt = f.read()
        results = MedraValidator().validate(prompt)
        assert results["domain"].score >= 95
        assert results["combined_score"] >= 90


# =====================================================================
# AEGIS — Autonomous/Safety-Critical Systems
# =====================================================================

from prompt_validator import aegis_rules

MINIMAL_AEGIS = """
You are a deterministic autonomous vehicle safety controller.
SECTION 0 — AXIOMS
A0. Determinism: Every actuator command must be computable.
SECTION 1 — SENSOR DATA CONTRACT
LIDAR_POINTS[], CAMERA_FRAMES[], RADAR_RETURNS[]
CRITICAL-PATH INPUTS (if missing → EMERGENCY_STOP)
SECTION 2 — SENSOR FUSION
KALMAN_GAIN = P * H_T * inv(S)
FUSION_WEIGHT = 0.40*LIDAR + 0.35*CAMERA + 0.25*RADAR
CONFIDENCE = min(sensors)
SECTION 3 — PERCEPTION PIPELINE
Object classification
SECTION 4 — DECISION ENGINE
THREAT_SCORE = (1/dist) * velocity * alignment
STOPPING_DIST = (V^2 / (2*a)) + (REACTION_TIME * V)
REACTION_TIME = 0.1s
POSITION_EST = predicted + KALMAN_GAIN * innovation
VELOCITY_EST = v_pred + K * v_innovation
SECTION 5 — SAFETY CONSTRAINTS
ASIL D safety integrity level
MAX_SPEED = posted * 1.0
MIN_DISTANCE = MAX(2.0m, STOPPING_DIST * 1.5)
MAX_ACCELERATION = 3.0 m/s²
GEOFENCE = operational_domain_boundary
Operational domain defined
SECTION 6 — FAIL-SAFE FSM
States: NOMINAL, DEGRADED, EMERGENCY_STOP, SAFE_STATE, MANUAL_OVERRIDE, SHUTDOWN
NOMINAL → DEGRADED: sensor drop
DEGRADED → NOMINAL: restored
DEGRADED → EMERGENCY_STOP: second failure
EMERGENCY_STOP → SAFE_STATE: vehicle stopped
MANUAL_OVERRIDE → SAFE_STATE: released
SECTION 7 — ACTUATOR COMMANDS
Steering, Throttle, Brake
SECTION 8 — WATCHDOG TIMERS
Decision loop watchdog: 50ms timeout
Sensor heartbeat: 100ms
SECTION 9 — REDUNDANCY SPEC
Triple modular redundancy (TMR) for brake and steering
Dual modular redundancy (DMR) for sensors
Failover: N+1
SECTION 10 — OUTPUT FORMAT
Print every control cycle
SECTION 11 — GOVERNANCE LOG
GOV-AEG-001
Section: 5
Before: old limit
After: new limit
Rationale: regulatory compliance
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestAegis:
    def test_section_completeness(self):
        assert aegis_rules.check_section_completeness(MINIMAL_AEGIS) == []

    def test_formula_definitions(self):
        assert aegis_rules.check_formula_definitions(MINIMAL_AEGIS) == []

    def test_fsm_states(self):
        assert aegis_rules.check_fsm_states(MINIMAL_AEGIS) == []

    def test_missing_fsm_states(self):
        issues = aegis_rules.check_fsm_states("NOMINAL DEGRADED only")
        assert len(issues) == 1

    def test_fsm_transitions(self):
        assert aegis_rules.check_fsm_transitions(MINIMAL_AEGIS) == []

    def test_safety_levels(self):
        assert aegis_rules.check_safety_levels(MINIMAL_AEGIS) == []

    def test_sensor_redundancy(self):
        assert aegis_rules.check_sensor_redundancy(MINIMAL_AEGIS) == []

    def test_watchdog_timers(self):
        assert aegis_rules.check_watchdog_timers(MINIMAL_AEGIS) == []

    def test_determinism_clean(self):
        assert aegis_rules.check_determinism("All outputs computed.") == []

    def test_integration(self):
        from prompt_validator.aegis_validator import AegisValidator
        with open("prompts/aegis_autonomous.txt") as f:
            prompt = f.read()
        results = AegisValidator().validate(prompt)
        assert results["domain"].score >= 95
        assert results["combined_score"] >= 90


# =====================================================================
# LEXIS — Legal/Compliance Systems
# =====================================================================

from prompt_validator import lexis_rules

MINIMAL_LEXIS = """
You are a deterministic legal compliance decision system.
SECTION 0 — AXIOMS
A0. Determinism: Every compliance decision must be computable.
SECTION 1 — JURISDICTION CONTRACT
Jurisdiction: United States Federal Law
Governing law: Title 31 USC
SECTION 2 — STATUTE DEFINITIONS
§ 5311 (BSA), Regulation 1010
SECTION 3 — COMPLIANCE RULES
Rule evaluation based on statute thresholds
SECTION 4 — DECISION TREE
COMPLIANT, NON_COMPLIANT, UNDER_REVIEW, ESCALATED, APPEAL, RESOLVED
COMPLIANT → NON_COMPLIANT on violation
NON_COMPLIANT → ESCALATED on high severity
NON_COMPLIANT → UNDER_REVIEW on ambiguity
UNDER_REVIEW → RESOLVED on completion
ESCALATED → APPEAL on challenge
SECTION 5 — PENALTY MATRIX
PENALTY_CALC = BASE * SEVERITY_MULTIPLIER * REPEAT
SEVERITY_SCORE = (count * 10) + (amount * 0.01)
COMPLIANCE_RATE = compliant / total
RISK_RATING = weighted_average(scores)
STATUTE_MATCH = exact_match(violation, statute)
PRECEDENT_WEIGHT = relevance * court_factor
LIABILITY_INDEX = PENALTY * (1 - mitigation)
DEADLINE_CALC = trigger_date + statutory_period
SECTION 6 — ESCALATION PROTOCOL
HALT → general counsel notification
SECTION 7 — APPEAL PATH
Appeal within 30 days, review panel
SECTION 8 — CONFLICT RESOLUTION
Rule priority hierarchy (lex specialis):
Court orders > Federal statutes > Regulations > State law
Precedence rules for conflicts
SECTION 9 — OUTPUT FORMAT
Print every compliance decision
SECTION 10 — GOVERNANCE LOG
GOV-LEX-001
Section: 3
Before: old threshold
After: new threshold
Rationale: regulatory update
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestLexis:
    def test_section_completeness(self):
        assert lexis_rules.check_section_completeness(MINIMAL_LEXIS) == []

    def test_formula_definitions(self):
        assert lexis_rules.check_formula_definitions(MINIMAL_LEXIS) == []

    def test_decision_states(self):
        assert lexis_rules.check_decision_states(MINIMAL_LEXIS) == []

    def test_decision_transitions(self):
        assert lexis_rules.check_decision_transitions(MINIMAL_LEXIS) == []

    def test_jurisdiction_coverage(self):
        assert lexis_rules.check_jurisdiction_coverage(MINIMAL_LEXIS) == []

    def test_statute_references(self):
        assert lexis_rules.check_statute_references(MINIMAL_LEXIS) == []

    def test_appeal_path(self):
        assert lexis_rules.check_appeal_path(MINIMAL_LEXIS) == []

    def test_conflict_resolution(self):
        assert lexis_rules.check_conflict_resolution(MINIMAL_LEXIS) == []

    def test_determinism_clean(self):
        assert lexis_rules.check_determinism("All decisions computed.") == []

    def test_integration(self):
        from prompt_validator.lexis_validator import LexisValidator
        with open("prompts/lexis_compliance.txt") as f:
            prompt = f.read()
        results = LexisValidator().validate(prompt)
        assert results["domain"].score >= 95
        assert results["combined_score"] >= 90


# =====================================================================
# QUANTA — Scientific Computing/Research
# =====================================================================

from prompt_validator import quanta_rules

MINIMAL_QUANTA = """
You are a deterministic scientific computing system.
SECTION 0 — AXIOMS
A0. Determinism: Every output reproducible with fixed seed.
SECTION 1 — DATA CONTRACT
DATASET_ID, FORMAT, SCHEMA_VERSION
SECTION 2 — UNITS AND CONSTANTS
SI unit system throughout (meter, kilogram, second, kelvin)
Dimensionless quantities labeled.
pi = 3.14159265358979
SECTION 3 — CORE EQUATIONS
RESIDUAL = observed - predicted
CHI_SQUARED = SUM((RESIDUAL/sigma)^2)
RMSE = SQRT(SUM(RESIDUAL^2)/N)
NORM_ERROR = ||computed - exact|| / ||exact||
LIKELIHOOD = PRODUCT(PDF(data|theta))
SECTION 4 — ERROR BOUNDS
CONFIDENCE_INTERVAL = estimate ± z * SE
P_VALUE = prob(T >= observed | H0)
Error propagation, tolerance epsilon = 1e-10
SECTION 5 — STATISTICAL METHODS
Hypothesis testing with alpha = 0.05
Random seed = 42 (deterministic, fixed seed)
SECTION 6 — CONVERGENCE CRITERIA
CONVERGENCE_METRIC = |x_new - x_old| / |x_old|
Stopping criterion: CONVERGENCE_METRIC < epsilon
MAX_ITER = 10000, iterate until convergence or termination
SECTION 7 — VALIDATION PROTOCOL
Cross-validation K=10
Benchmark comparison
SECTION 8 — REPRODUCIBILITY
DRAFT, VALIDATED, PEER_REVIEWED, PUBLISHED, RETRACTED, ARCHIVED
DRAFT → VALIDATED: checks pass
VALIDATED → PEER_REVIEWED: reviewer sign-off
PEER_REVIEWED → PUBLISHED: editor approval
PUBLISHED → RETRACTED: error discovered
Seed = 42, library versions locked
SECTION 9 — OUTPUT FORMAT
Print every computation result
SECTION 10 — GOVERNANCE LOG
GOV-QNT-001
Section: 5
Before: N=1000
After: N=10000
Rationale: stability improvement
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestQuanta:
    def test_section_completeness(self):
        assert quanta_rules.check_section_completeness(MINIMAL_QUANTA) == []

    def test_formula_definitions(self):
        assert quanta_rules.check_formula_definitions(MINIMAL_QUANTA) == []

    def test_unit_definitions(self):
        assert quanta_rules.check_unit_definitions(MINIMAL_QUANTA) == []

    def test_error_bounds(self):
        assert quanta_rules.check_error_bounds(MINIMAL_QUANTA) == []

    def test_convergence_criteria(self):
        assert quanta_rules.check_convergence_criteria(MINIMAL_QUANTA) == []

    def test_repro_states(self):
        assert quanta_rules.check_repro_states(MINIMAL_QUANTA) == []

    def test_repro_transitions(self):
        assert quanta_rules.check_repro_transitions(MINIMAL_QUANTA) == []

    def test_random_seed(self):
        assert quanta_rules.check_random_seed(MINIMAL_QUANTA) == []

    def test_determinism_clean(self):
        assert quanta_rules.check_determinism("All outputs computed.") == []

    def test_integration(self):
        from prompt_validator.quanta_validator import QuantaValidator
        with open("prompts/quanta_research.txt") as f:
            prompt = f.read()
        results = QuantaValidator().validate(prompt)
        assert results["domain"].score >= 95
        assert results["combined_score"] >= 90


# =====================================================================
# SENTINEL — Cybersecurity/Threat Detection
# =====================================================================

from prompt_validator import sentinel_rules

MINIMAL_SENTINEL = """
You are a deterministic cybersecurity threat detection system.
SECTION 0 — AXIOMS
A0. Determinism: Every alert must be computable from defined rules.
SECTION 1 — DATA INGESTION CONTRACT
FIREWALL_LOGS[], IDS_ALERTS[], ENDPOINT_TELEMETRY[]
CRITICAL-PATH INPUTS (if missing → HALT)
SECTION 2 — IOC CLASSIFICATION
IP address, domain, file hash, URL, email, registry, process indicators
SECTION 3 — SEVERITY SCORING
SEVERITY_SCORE = CVSS_BASE * ASSET_CRITICALITY
CVSS_BASE = (impact + exploitability) / 2
CONFIDENCE_LEVEL = IOC_CONFIDENCE * CORRELATION
RISK_PRIORITY = SEVERITY * (1 + DWELL_TIME/24)
IOC_WEIGHT = 0.30*HASH + 0.25*BEHAVIOR + 0.25*NETWORK + 0.20*REPUTATION
CORRELATION_SCORE = matched / total_rules
FALSE_POS_RATE = false_alerts / total_alerts
DWELL_TIME = detection - compromise timestamp
SECTION 4 — DETECTION RULES
MITRE ATT&CK framework mapping
TA0001 Initial Access: T1566 Phishing, T1190 Exploit
TA0003 Persistence: T1053 Scheduled Task
Kill chain detection
SECTION 5 — CORRELATION ENGINE
Multi-event correlation: 3+ IOCs in 1 hour
SECTION 6 — ALERT FSM
NEW, TRIAGED, INVESTIGATING, ESCALATED, FALSE_POSITIVE, CONTAINED, RESOLVED
NEW → TRIAGED: severity classified
TRIAGED → INVESTIGATING: analyst assigned
TRIAGED → FALSE_POSITIVE: allowlist/exclusion match
INVESTIGATING → ESCALATED: severity upgrade
INVESTIGATING → CONTAINED: isolation executed
CONTAINED → RESOLVED: remediation verified
SECTION 7 — ESCALATION PROTOCOL
HALT → all hands SOC response
SECTION 8 — RESPONSE PLAYBOOKS
Playbook for phishing: quarantine + block
Containment steps, remediation, isolation
SECTION 9 — FALSE POSITIVE HANDLING
FALSE_POS_RATE tracked per rule
Allowlist/exclusion rules with expiration
Suppression rules documented
SECTION 10 — OUTPUT FORMAT
Print every alert in exact order
SECTION 11 — GOVERNANCE LOG
GOV-SEC-001
Section: 3
Before: old formula
After: new formula with exploit probability
Rationale: better risk prioritization
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestSentinel:
    def test_section_completeness(self):
        assert sentinel_rules.check_section_completeness(MINIMAL_SENTINEL) == []

    def test_formula_definitions(self):
        assert sentinel_rules.check_formula_definitions(MINIMAL_SENTINEL) == []

    def test_alert_states(self):
        assert sentinel_rules.check_alert_states(MINIMAL_SENTINEL) == []

    def test_missing_states(self):
        issues = sentinel_rules.check_alert_states("NEW TRIAGED only")
        assert len(issues) == 1

    def test_alert_transitions(self):
        assert sentinel_rules.check_alert_transitions(MINIMAL_SENTINEL) == []

    def test_mitre_mapping(self):
        assert sentinel_rules.check_mitre_mapping(MINIMAL_SENTINEL) == []

    def test_no_mitre(self):
        issues = sentinel_rules.check_mitre_mapping("No framework mapping here.")
        assert len(issues) == 1

    def test_ioc_classification(self):
        assert sentinel_rules.check_ioc_classification(MINIMAL_SENTINEL) == []

    def test_false_positive_handling(self):
        assert sentinel_rules.check_false_positive_handling(MINIMAL_SENTINEL) == []

    def test_response_playbooks(self):
        assert sentinel_rules.check_response_playbooks(MINIMAL_SENTINEL) == []

    def test_determinism_clean(self):
        assert sentinel_rules.check_determinism("All detections computed.") == []

    def test_integration(self):
        from prompt_validator.sentinel_validator import SentinelValidator
        with open("prompts/sentinel_security.txt") as f:
            prompt = f.read()
        results = SentinelValidator().validate(prompt)
        assert results["domain"].score >= 95
        assert results["combined_score"] >= 90
