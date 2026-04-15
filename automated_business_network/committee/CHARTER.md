# Automated Business Network — Planning Committee Charter

## Mission

Design and launch a network of **10 automated businesses** that generate
real revenue, operated primarily by software with a **single human owner**
("the Principal") acting as approver, signer, and escalation point.

## Operating model

- **Human-in-the-loop by design.** The Principal owns bank accounts,
  legal entities, and the final "go/no-go" on any irreversible action
  (payments out, contracts, public statements, hiring). Everything else
  is automated.
- **One shared platform, ten P&Ls.** Each venture is a module on a common
  infrastructure (auth, payments, CRM, observability, task queue, LLM
  orchestration) so marginal cost of adding venture #11 is low.
- **Real money, not hypothetical.** Every venture must have (1) a
  customer willing to pay, (2) a payment rail, (3) a measurable unit
  economic model showing gross margin > 0 before scaling.

## Committee seats

Each seat is a specialist "role" the planner will consult before any
major decision. In the code, each seat is an agent persona with a
clear prompt and review checklist.

| # | Seat | Responsibility |
|---|------|----------------|
| 1 | **Chair / Portfolio Strategist** | Selects and sequences the 10 ventures, kills losers, rebalances capital. |
| 2 | **CTO / Automation Architect** | Shared platform, LLM orchestration, reliability, cost-per-task. |
| 3 | **CFO / Unit Economics** | Pricing, COGS, cash runway, tax, bookkeeping automation. |
| 4 | **CMO / Growth** | Acquisition channels, SEO, paid, content, referral loops. |
| 5 | **General Counsel** | Entity structure, contracts, ToS, IP, regulated-industry gating. |
| 6 | **COO / Ops & Fulfillment** | SLAs, vendor management, customer support automation. |
| 7 | **Risk & Compliance** | Fraud, chargebacks, AML/KYC, content policy, platform ToS. |
| 8 | **Ethics & Trust** | "Would we be proud if this were on the front page?" veto. |
| 9 | **Data / Analytics** | Single dashboard across all 10 ventures; kill criteria. |
| 10 | **Principal (Human)** | Final authority. Signs, approves payouts, hires, shuts down. |

## Decision rules

1. **Two-key rule** on any outbound money movement > a threshold the
   Principal sets: automation proposes, Principal approves.
2. **Kill switch.** Any venture missing its 90-day milestone is paused
   automatically and reviewed by Chair + CFO.
3. **No dark patterns, no spam, no regulatory grey zones** without
   General Counsel sign-off in writing.
4. **Audit log.** Every automated decision is logged with inputs,
   prompt, model, output, and the human who (if anyone) approved it.

## Deliverables from this committee (next steps)

1. A shortlist of **15–20 candidate ventures**, scored on:
   fit × margin × automatability × legal risk × capital required.
2. The **top 10** selected, each with a one-page venture brief.
3. A **shared platform spec** (auth, payments, queue, observability).
4. A **90-day launch plan** with milestones and kill criteria.

## Open questions for the Principal

Before the committee can shortlist ventures, it needs answers to the
questions listed in `committee/OPEN_QUESTIONS.md`.
