# GST Reference Assistant — Plan v0.1 (PLAN ONLY, NO BUILD)

**Status:** Planning document. Nothing in this document has been built. Build starts only on explicit instruction.
**Date:** 2026-09-21
**Working name:** *GST Sahayak* (placeholder, rename freely)

---

## 0. Expert Panel and Problem Reframing

### 0.1 The panel (roles that must shape this plan)

These are the personas whose judgement the plan is written from. When the project staffs up, hire or consult people matching these profiles. No real individuals are named.

| # | Expert persona | Why they are on the panel | What they own in this plan |
|---|---|---|---|
| E1 | **Former GST Council Secretariat / CBIC policy officer** | Knows how a Council recommendation becomes a notification, and what is *not* law until notified | Legal hierarchy, corpus scope, "recommended vs notified" handling |
| E2 | **State GST Commissioner's office (Additional Commissioner, Law/Legal wing)** | The top user. Knows officer workflows: SCN, adjudication, appeals, audit, circular drafting | Officer and Commissioner use cases, internal-only corpus, approval workflow for published answers |
| E3 | **Indirect-tax partner (Big-4 / senior CA practising GST litigation)** | Represents the taxpayer and practitioner side; knows which questions are actually asked and where the law is ambiguous | Taxpayer use cases, golden question set, citation standard |
| E4 | **Legal-informatics / RAG architect** (has shipped statute search with point-in-time versioning) | Law is versioned text with effective dates; naïve chunk-and-embed RAG fails on amendments | Knowledge model, ingestion, retrieval, citation contract, evaluation harness |
| E5 | **Conversational-channel engineer** (WhatsApp Business Platform, Telegram, PWA) | India's public reaches services through WhatsApp far more than through apps | Channel architecture, session handling, media (PDF/image notices), rate limits, cost per conversation |
| E6 | **Indic-language and accessibility lead** (Bhashini / IndicTrans, voice) | A national taxpayer base is not English-first | Multilingual pipeline, voice, low-bandwidth UX |
| E7 | **GovTech security & compliance officer** (DPDP Act 2023, CERT-In, MeitY cloud empanelment, NIC/Parichay SSO) | A departmental deployment must survive audit | Data residency, PII handling, auth tiers, audit logs, retention |
| E8 | **Product manager for public-facing government services** (UMANG / DigiLocker style) | Keeps scope to what citizens will actually use, and what the department can operate | Roadmap, tiers, KPIs, operating model |
| E9 | **LLM evaluation lead** | Legal chatbots fail silently; hallucination must be measured, not assumed | Golden set, scoring, release gates, regression on every corpus update |

### 0.2 Reframed problem statement (contextual-engineering view)

The naïve ask is "a chatbot that knows GST". The engineering problem is:

> **Build a versioned, citable knowledge system over Indian GST law, where every answer is grounded in a specific provision as it stood on a specific date, and expose it through channels that anyone in India (taxpayer, practitioner, officer, Commissioner) can reach from any device, with role-appropriate depth and an audit trail.**

What that reframing changes:

1. **The corpus is a graph with time, not a pile of PDFs.** A rule is a node; each amendment is an edge carrying a notification number and an effective date. "What does Rule 36(4) say?" has no single answer without a date.
2. **The unit of trust is the citation, not the answer.** The system's contract is: *quote the text, name the provision, name the amending instrument, state the effective window, link the source.* The prose explanation is secondary.
3. **Council decisions are a separate class of object.** A Council recommendation is not law (Supreme Court, *Mohit Minerals*, 2022: recommendations are persuasive, not binding). The system must show "Recommended on date X at meeting N; notified by Notification Y on date Z" or "not yet notified".
4. **Users differ in what they are allowed to see and in the consequence of error.** A citizen asking "what is the GST on a restaurant bill" and an adjudicating officer drafting a Section 74A order need different depth, different sources, and different guardrails.
5. **Channels are thin; the core is one.** Web, WhatsApp, Telegram, and an API must all hit one conversation core so that answers, citations, and logs are identical everywhere.
6. **Quality is measured against a golden set curated by tax experts.** No release without citation-precision and hallucination numbers.

---

## 1. Vision, Users, Scope

### 1.1 One-line vision
A public, multilingual, device-independent GST reference assistant that answers with quotable citations from the Acts, Rules, Forms, Notifications, Circulars and GST Council decisions, with a privileged tier for the State GST Commissioner and departmental officers.

### 1.2 User tiers

| Tier | Who | Access | Typical questions |
|---|---|---|---|
| T0 Public | Any person in India, anonymous | Public law corpus, rate finder, forms, due dates | "GST rate on X?", "Which form to register?", "Last date for GSTR-3B?" |
| T1 Registered taxpayer / practitioner | Phone-OTP or email login; optional GSTIN on profile | T0 + saved conversations, notice upload and explanation, compliance calendar | "Explain this DRC-01 notice", "Can I claim ITC on this?", "Refund process for exports?" |
| T2 Departmental officer | Departmental SSO (NIC Parichay or state IdP) | T1 + internal circulars, SOPs, adjudication precedents, drafting aids | "Precedents on Section 16(4) time limit", "Draft SCN skeleton under 74A with citations" |
| T3 Commissioner / admin | Named accounts, MFA | T2 + analytics, corpus approval, publish clarifications, audit logs | "What are taxpayers asking most this month?", "Approve ingestion of Circular N" |

### 1.3 In scope (v1)
- CGST Act 2017, IGST Act 2017, UTGST Act 2017, GST (Compensation to States) Act 2017, and one State's SGST Act (start with the Commissioner's state; the CGST/SGST mirror structure makes others cheap to add).
- CGST Rules 2017 (all amendments, point-in-time) and the mirror State Rules.
- All GST forms (REG, GSTR, CMP, ITC, PMT, RFD, DRC, APL, EWB, ASMT, ADT, INS, etc.) with purpose, rule reference, due dates and filing guidance.
- Notifications (Central Tax, Central Tax (Rate), Integrated Tax, Integrated Tax (Rate), Compensation Cess), Circulars, Orders, Instructions, Press Releases, FAQs from CBIC.
- GST Council: agenda, minutes, press releases, decisions of every meeting (1st onward, including the 56th meeting of Sept 2025 whose rate rationalisation took effect 22 Sept 2025), each linked to its implementing notification (or flagged "not notified").
- Rate schedules by HSN / SAC with effective-date history.
- Web PWA + WhatsApp bot + Telegram bot on one core.

### 1.4 Out of scope (v1)
- Filing returns or any write to the GSTN portal (requires GSP/ASP licensing; separate project).
- Authoritative computation of a taxpayer's liability. The assistant explains and calculates illustratively, with a disclaimer.
- Case-law corpus (AAR, AAAR, High Court, Supreme Court, GSTAT) beyond a curated seed set. Planned for v2.
- Legal advice. Every answer carries a fixed "reference, not advice" line.

---

## 2. The Corpus: Sources and Legal Hierarchy

### 2.1 Sources (ingestion targets)

| Source | Content | Notes |
|---|---|---|
| cbic-gst.gov.in | Acts, Rules, Notifications, Circulars, Orders, Instructions, FAQs, rate schedules | Primary. Mostly PDF; some scanned. |
| gstcouncil.gov.in | Meeting agendas, minutes, press releases, decisions | Minutes lag meetings by weeks; press release is the fast signal. |
| gst.gov.in (GSTN portal) | Forms, user manuals, advisories, due-date notices, IMS advisories | Forms are the canonical layouts. |
| egazette.gov.in | Gazette copies of notifications | Ground truth for notification text and date. |
| indiacode.nic.in | Consolidated Acts | Useful for "as amended" consolidated text. |
| State commercial-tax department site (e.g. Kerala: keralataxes.gov.in) | SGST Act, State notifications, State circulars, internal circulars (T2 only) | Structure varies by state; one scraper per state. |
| Finance Acts (annual) | Amendments to the CGST/IGST Acts | Effective dates are often set later by separate notification. |

### 2.2 Legal hierarchy (used for ranking and for wording answers)

1. Act (as amended by Finance Acts, effective per notification)
2. Rules (CGST Rules, amended by Central Tax notifications)
3. Rate notifications (Central Tax (Rate), Integrated Tax (Rate)) and Cess notifications
4. Other notifications (exemptions, procedures, extensions)
5. Circulars and Instructions (binding on the department, not on taxpayers or courts)
6. Council decisions and press releases (recommendations; persuasive)
7. FAQs, user manuals, advisories (guidance only)
8. Case law (v2)

Answers state which level they rest on. A Circular is never presented as if it were the Act.

### 2.3 Knowledge model (the part that makes or breaks this)

```
Provision  (act_id, section/rule number, sub-clause path)
  └─ Version (text, effective_from, effective_to, amended_by → Instrument)
Instrument (type: notification|circular|order|finance_act|council_decision,
            number, date, gazette_ref, url, summary)
Form       (form_id, title, purpose, governing_rule → Provision, due_date_rule, version history)
RateEntry  (hsn_or_sac, description, cgst, sgst, igst, cess, effective_from, effective_to, instrument)
CouncilDecision (meeting_no, meeting_date, item, recommendation, status: notified|pending|withdrawn,
                 implemented_by → Instrument)
```

Every retrievable chunk carries this metadata so the retriever can filter by date and the answer layer can build a citation string mechanically rather than by asking the model.

### 2.4 Point-in-time rule
Default "as-of" date is today. Users can set a transaction date ("as on 15 March 2024"). Officers get it as a required field in adjudication mode. The retriever filters versions by `effective_from <= as_of < effective_to`.

---

## 3. Use Cases

### 3.1 Core (v1)

| # | Use case | Tier | Example |
|---|---|---|---|
| U1 | **Provision lookup with citation** | T0+ | "Text of Section 16(2)(aa) as on today" |
| U2 | **Rule / form finder** | T0+ | "Which form to cancel registration and under which rule?" |
| U3 | **Rate finder by HSN/SAC or description, with date** | T0+ | "GST on packaged paneer on 1 Oct 2025 vs 1 Sept 2025" |
| U4 | **Council decision tracker** | T0+ | "What did the 56th meeting decide on insurance, and is it notified?" |
| U5 | **Amendment history / diff of a provision** | T1+ | "How has Rule 36(4) changed since 2019?" |
| U6 | **Notice decoder** (upload PDF/image) | T1+ | "Explain this ASMT-10, what section, what deadline, which reply form" |
| U7 | **Compliance calendar** | T1+ | "My due dates this month as a monthly filer in Kerala" |
| U8 | **Concept explainers with citations** | T0+ | Place of supply, reverse charge, composition, ITC blocked credits, e-way bill thresholds |
| U9 | **Officer precedent and drafting aid** | T2 | "Skeleton for a Section 74A SCN on excess ITC with citations" |
| U10 | **Commissioner analytics** | T3 | Top questions, unanswered questions, corpus gaps, language split, channel split |

### 3.2 Extended (v2+)
- Case-law search (AAR/AAAR/HC/SC/GSTAT) with "distinguished / followed" tagging.
- Interest and late-fee calculator (Section 50, Section 47) with cited rates.
- Appeal timeline planner (APL-01 to GSTAT) with limitation computation.
- Multi-state comparison of SGST provisions and state notifications.
- Officer training / quiz mode built from the golden set.
- Grievance routing: unanswered or "disputed" questions become tickets for the department.
- Public API for GSPs, accounting software and trade bodies.
- Auto-drafted FAQ pages from the most common answered questions, approved by T3 before publishing.
- Voice on WhatsApp and web (Indic ASR/TTS via Bhashini).

---

## 4. Product Surfaces and How to Run Them

All surfaces are thin adapters over one **Conversation Core** API.

| Surface | Reach | Notes |
|---|---|---|
| **Web PWA** (installable, responsive) | Any phone, tablet, desktop; no app store | Primary surface. Offline cache of Acts/Rules text for reading. Shareable answer permalinks. |
| **WhatsApp bot** (WhatsApp Business Platform via a BSP) | Widest reach in India | Text, buttons/lists, document and image upload for notice decoding. Business verification and template approval needed. Per-conversation cost. |
| **Telegram bot** | Cheap, no approval friction | Good for pilot and for practitioners. |
| **Embeddable widget** | Department website, GSTN-adjacent portals | Same core, department branding. |
| **REST API** | GSPs, ERPs, trade associations | Keyed, rate-limited, T0 corpus only unless contracted. |
| **Android TWA wrapper** (optional) | Play Store presence | Wraps the PWA; no separate codebase. |

### Running it
- **Single deployable**: one container image for the core + adapters, one for ingestion workers, managed Postgres and object storage.
- **Hosting**: India region only (data residency). Options in order of preference for a government tenant: NIC MeghRaj / a MeitY-empanelled cloud; else AWS Mumbai or Azure Central India under a department account.
- **Model access**: Claude via the Anthropic API, or via Amazon Bedrock in an India region if the department mandates an in-country inference endpoint. Confirm region availability for the chosen model before committing.
- **Ops**: nightly ingestion run, weekly corpus review queue for T3, monthly golden-set regression.

---

## 5. Architecture

```
[Web PWA] [WhatsApp] [Telegram] [Widget] [API]
      \       |          |         |       /
       └──────┴── Channel Adapters ┴──────┘
                        |
              Conversation Core (FastAPI)
      ┌─────────────────┼─────────────────────┐
      |                 |                     |
  Auth & Tiers     Orchestrator           Session store
 (OTP / SSO / MFA)  - intent routing        (Redis)
                    - as-of date resolve
                    - retrieval
                    - answer + citation build
                    - guardrails
                        |
              Retrieval Layer (hybrid)
        BM25 (OpenSearch) + Vector (pgvector) + Graph filters
                        |
              Knowledge Store (Postgres)
   provisions · versions · instruments · forms · rates · council decisions
                        ^
              Ingestion Pipeline (workers)
   scrape → fetch → parse (PDF/OCR) → segment by section/rule → link amendments
   → extract metadata → human review queue (T3) → publish
                        ^
   cbic-gst · gstcouncil · gst.gov.in · egazette · indiacode · state site
```

### 5.1 Ingestion
- Scrapers per source with change detection (hash of listing page + document).
- PDF parsing with layout awareness; OCR for scanned gazette copies.
- Segmentation by legal structure (Chapter → Section → Sub-section → Clause; Rule → Sub-rule → Proviso), not by fixed token windows.
- Amendment linking: parse "In rule X, for the words ... the following shall be substituted" patterns from notifications; produce new Version rows with effective dates; flag ambiguous ones for the review queue.
- Every ingested item is **unpublished until a T3 reviewer approves** in the first months; later, auto-publish for low-risk classes (press releases, FAQs) with post-hoc review.

### 5.2 Retrieval
- Hybrid: lexical (section numbers, form IDs, notification numbers must match exactly) + semantic (paraphrased questions) + metadata filters (as-of date, tier, source class).
- Re-rank top 30 to top 8 with a cross-encoder or a small LLM pass.
- Always retrieve the provision **and** its most recent amending instrument so the citation can name both.

### 5.3 Answer generation (the LLM's job is narrow)
- Model: **Claude Opus 5** (`claude-opus-5`) for answers, adaptive thinking on, effort tuned per route (`low` for rate lookups and routing, `high` for officer drafting). **Claude Haiku 4.5** (`claude-haiku-4-5`) for intent classification and language detection. Prompt caching on the fixed system prompt and the citation-format rules.
- The system prompt is frozen and versioned; corpus text is passed as `document` blocks with citations enabled so the API returns the exact quoted spans.
- Output is a structured object: `{answer_text, citations[], as_of_date, confidence, disclaimer_class, follow_ups[]}`. Citations are built from metadata, then the quoted spans are verified against the stored text before rendering. A citation that does not verify is dropped and the answer is marked degraded.
- If retrieval confidence is low, the assistant says it cannot find a governing provision and offers the closest matches. It does not guess.

### 5.4 Guardrails
- Refuse to fabricate section numbers, notification numbers or dates (checked mechanically: every number in the answer must appear in a retrieved chunk).
- Fixed disclaimer by tier: public ("reference only, not legal advice"), officer ("verify against gazette before issuing").
- No personal advice on evasion, no assistance in structuring to defeat the law. Standard content policy.
- Prompt-injection isolation for uploaded notices (documents are data, never instructions).
- PII redaction on uploaded notices (GSTIN, PAN, names) before anything is logged.

### 5.5 Multilingual
- Detect language per message. Retrieve in English (the law is in English; Hindi versions exist for Acts and can be added as parallel text).
- Answer in the user's language via Bhashini or IndicTrans2, keeping quoted statutory text in the original English with a translated gloss underneath.
- v1 languages: English, Hindi, Malayalam (Commissioner's state; adjust). Add others by configuration.

---

## 6. Citation and Trust Contract

Every answer that relies on law renders citations in this fixed shape:

```
[1] CGST Act 2017, s. 16(2)(aa) — inserted by Finance Act 2021, s. 100; effective 01-01-2022 (Notification 39/2021-Central Tax, 21-12-2021)
    "…" (exact quoted text)
    Source: <url>  · As on: 21-09-2026
[2] 56th GST Council meeting, 03-09-2025, Item 4 — recommended … ; implemented by Notification 09/2025-Central Tax (Rate), 17-09-2025, effective 22-09-2025
```

Rules:
- Quote, then explain. Never explain without a quote when the question is about what the law says.
- Name the level (Act / Rule / Notification / Circular / Council recommendation).
- State the effective window and the as-of date used.
- Council decisions always carry a notified / pending flag.
- Officers see an extra line: "Internal: <SOP or internal circular ref>" when used.

---

## 7. Recommended Stack

| Layer | Choice | Reason |
|---|---|---|
| Web | Next.js PWA (React, TypeScript), installable, responsive | Mature PWA tooling, SSR for shareable answer pages |
| Bot adapters | WhatsApp Cloud API via a BSP; Telegram Bot API | Standard, well documented |
| Core API | Python 3.12, FastAPI | Matches this repository's Python base; strong LLM ecosystem |
| LLM | Anthropic SDK (`anthropic`), Claude Opus 5 + Haiku 4.5 | Citations feature, large context, prompt caching |
| Knowledge store | PostgreSQL 16 + pgvector | One database for graph metadata and vectors |
| Lexical search | OpenSearch | Exact match on numbers and IDs |
| Cache / sessions | Redis | Conversation state, rate limiting |
| Object storage | S3-compatible | Source PDFs, uploads (encrypted, short retention) |
| Ingestion | Python workers (Celery or Arq), Playwright for JS-heavy sites, OCR (Tesseract/Surya) | |
| Indic language | Bhashini APIs (govt) with IndicTrans2 fallback | Data-residency friendly |
| Observability | OpenTelemetry + Langfuse (self-hosted) | Trace every answer to its retrieval set |
| Eval | Custom harness in `evals/` with golden set in version control | Release gate |
| Infra | Docker, Kubernetes or a managed container service, Terraform | India region only |

Repository note: this repository currently holds the Prompt System Validator and trading-system documents. The GST assistant should live in its **own repository**; this plan is stored here for reference. The existing `prompt_validator` can be reused to lint the assistant's system prompts before release.

---

## 8. Security, Privacy, Compliance

- **DPDP Act 2023 and its Rules**: purpose limitation, consent notice at login, data-principal rights (access, erasure), breach notification. Uploaded notices are personal data; retain 30 days by default, user-deletable.
- **Data residency**: all storage and, where the department requires, all inference inside India.
- **CERT-In** logging requirements (180-day log retention for security events; separate from conversation retention).
- **Auth**: T0 anonymous; T1 phone OTP or email; T2 departmental SSO; T3 SSO + MFA. Role claims decide corpus visibility at the retrieval filter, not in the prompt.
- **Audit trail**: every answer stores the retrieval set, prompt version, model, and citations, so any answer can be reconstructed later. Essential for a Commissioner-endorsed service.
- **No training on user data**; contractual confirmation from the model provider.
- **Abuse controls**: per-user and per-channel rate limits; cost caps per day.
- **Accessibility**: WCAG 2.1 AA on the web surface; GIGW (Government of India web guidelines) if hosted under a department domain.

---

## 9. Evaluation and Quality Gates

1. **Golden set**: 300 questions for v1 (100 rate, 60 procedure/forms, 60 provisions, 40 Council decisions, 40 officer-grade), each with expected citations and an expert-approved answer. Built with E3 and E2. Grows with every reviewed real conversation.
2. **Metrics**: citation precision (cited span actually supports the claim), citation recall (the governing provision is cited), hallucinated-identifier rate (must be 0), refusal correctness, latency, cost per answer, language fidelity.
3. **Gates**: no release if hallucinated-identifier rate > 0 or citation precision < 95% on the golden set. Regression run after every corpus update.
4. **Human review loop**: T3 dashboard shows low-confidence and thumbs-down answers weekly; corrections become golden-set entries.

---

## 10. Roadmap

| Phase | Duration | Deliverable | Exit criteria |
|---|---|---|---|
| **P0 Discovery** | 2–3 weeks | Corpus audit (what is machine-readable, what needs OCR), state selection, hosting decision, golden set v0 (100 Q), legal sign-off on disclaimers | Commissioner approves scope and tiers |
| **P1 MVP** | 8–10 weeks | Ingestion for CGST Act/Rules, forms, Central notifications, Council press releases; hybrid retrieval; citation contract; web PWA; Telegram pilot; English + one Indic language | Golden set gates pass; 50 pilot users (officers + practitioners) |
| **P2 Public beta** | 6–8 weeks | WhatsApp channel, rate finder with date, amendment diff, notice decoder, T1 accounts, analytics v1 | Public launch on department site |
| **P3 Officer tier** | 6–8 weeks | SSO, internal corpus, drafting aids, adjudication mode with mandatory as-of date, audit reconstruction | Legal wing sign-off |
| **P4 Scale** | ongoing | More states, case law, API for GSPs, voice, calculators | Per-state onboarding under 2 weeks |

---

## 11. Team and Rough Cost

**Build team (P1–P3)**: 1 product lead, 1 tax-domain analyst (CA), 2 backend engineers, 1 frontend engineer, 1 data/ingestion engineer, 1 ML/eval engineer, 0.5 security/compliance, 0.5 designer. Advisory: E1, E2, E3 part-time.

**Running cost drivers**: LLM tokens (dominant; prompt caching cuts the fixed part by most), WhatsApp conversation fees, hosting, OCR. Order of magnitude at 10,000 conversations/day with caching: low lakhs INR per month for inference; validate in P1 with real token counts. Public rate-lookups can be served from a precomputed table without any LLM call, which is the biggest single cost lever.

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Amendment linking errors (wrong text shown as current) | Human review queue for every amendment in the first six months; diff view for reviewers; golden-set coverage of recently amended rules |
| Scanned or inconsistent source PDFs | OCR with confidence scores; low-confidence pages routed to review; gazette copy as tiebreaker |
| Hallucinated identifiers | Mechanical check that every identifier in the answer exists in the retrieval set; zero-tolerance gate |
| Council recommendation shown as law | Separate object class with notified/pending flag; wording template enforced |
| Liability for wrong public answers | Disclaimers, citation-first rendering, Commissioner-approved FAQ tier for the most common questions |
| WhatsApp approval or policy changes | Telegram and web are independent of it; WhatsApp is additive |
| Data residency or vendor lock-in | Abstract the LLM client; keep corpus and evals portable; India-region hosting from day one |
| Corpus drift after each Council meeting or Budget | Ingestion alerts on new documents; "what changed" digest to T3 within 24 hours |

---

## 13. Decisions Needed Before "Build"

1. Which state's SGST corpus first (assumed Kerala; confirm).
2. Hosting: department-owned cloud account, NIC, or a vendor-managed tenancy.
3. Model access path: Anthropic API directly, or Bedrock in an India region.
4. Launch surfaces for the pilot: web + Telegram (recommended), or web + WhatsApp from the start.
5. Languages for v1 beyond English (assumed Hindi + Malayalam).
6. Whether the officer tier (T2/T3) is in the first build or follows the public MVP.
7. Whether the assistant may show case law in v1 at all (recommended: no, v2).
8. Ownership of the review queue: who in the Commissioner's office approves ingested items.

---

## 14. What "Build" Will Mean

When instructed to build, the first increment will be:

1. New repository skeleton (core API, ingestion, web, evals) with the knowledge schema from §2.3.
2. Ingestion for the CGST Act and CGST Rules with version history, and Council press releases.
3. Retrieval + citation contract + golden-set harness (50 questions) running end to end.
4. Minimal web PWA and a Telegram bot on the same core.

Nothing beyond this document is created until that instruction is given.
