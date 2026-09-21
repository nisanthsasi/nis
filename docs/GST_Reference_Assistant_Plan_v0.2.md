# GST Reference Assistant — Plan v0.2 (LLM-FREE, PLAN ONLY, NO BUILD)

**Status:** Planning document. Supersedes v0.1 on architecture. Nothing has been built.
**Date:** 2026-09-21
**Decision recorded:** The system uses **no large language model** anywhere. Every answer is a retrieved, quoted, cited record from a reviewed corpus. Deterministic, auditable, zero inference cost.

---

## 0. What changed from v0.1

| v0.1 | v0.2 |
|---|---|
| LLM writes explanations over retrieved law | No generated prose. Answers are the law text itself, plus curated explainers written and approved by humans |
| Semantic (vector) retrieval + reranker | Lexical search (BM25) + synonym dictionary + structured filters |
| Free-text conversational bot | Menu-driven bot with keyword search fallback |
| Notice decoder explains the allegation | Notice decoder identifies the form, section, deadline and reply form from templates |
| Officer drafting aid adapts to facts | Officer drafting aid is a fill-in template bank with cited provisions |
| Machine translation of generated answers | Pre-translated static content; optional Bhashini translation of search queries and explainer pages (translation model, not an LLM) |
| Hallucination gate | Not needed: nothing is generated, so nothing can be invented |

Everything else from v0.1 stands: expert panel, user tiers, corpus sources, legal hierarchy, knowledge model, point-in-time rule, citation contract, security and compliance, roadmap shape.

---

## 1. Core principle

> Every screen and every bot reply is one of three things: **(a)** a quoted record from the corpus with its citation, **(b)** a human-written, reviewer-approved explainer page, or **(c)** a menu.

There is no fourth kind of output.

---

## 2. Architecture (LLM-free)

```
[Web PWA] [Telegram bot] [WhatsApp bot] [Widget] [REST API]
      \         |             |            |         /
       └────────┴── Channel Adapters ──────┴────────┘
                          |
                   Reference Core (FastAPI)
      ┌───────────────────┼─────────────────────────┐
  Auth & Tiers      Query Router               Session store
                    - menu state machine        (Redis)
                    - identifier parser
                      (s.16(2)(aa), Rule 36(4),
                       GSTR-3B, Notif 09/2025-CT(R),
                       HSN 0406, "56th meeting")
                    - keyword search
                    - as-of date filter
                    - citation builder (mechanical)
                          |
                 Search Layer: OpenSearch (BM25)
              + synonym dictionary + facets + date filters
                          |
                 Knowledge Store: PostgreSQL
    provisions · versions · instruments · forms · rates
    · council decisions · explainers · templates · synonyms
                          ^
                 Ingestion Pipeline (workers)
   scrape/upload → parse (PDF / OCR) → segment by section/rule
   → rule-based amendment linker → metadata extract
   → human review queue (T3) → publish
```

### 2.1 Query Router (replaces the LLM orchestrator)

Order of resolution for any user input:

1. **Menu state**: if the user is inside a menu flow, interpret the input as a menu choice.
2. **Identifier parser**: regexes for section, rule, form, notification, circular, HSN/SAC, Council meeting number. A hit returns the record directly with its citation. This covers most officer and practitioner queries.
3. **Structured lookups**: rate finder (HSN/SAC or description → rate table filtered by date), form finder, due-date engine, Council tracker.
4. **Keyword search**: BM25 over provision text, headings, explainer pages, form descriptions and Council decisions, with a maintained synonym dictionary (e.g. "input credit" → "input tax credit", "late fee" → "section 47", "e-way" → "e-way bill, Rule 138"). Returns a ranked list of records, each with citation.
5. **No match**: show the top-level menu and log the query for the T3 gap report. Unanswered queries feed the explainer backlog.

### 2.2 Ingestion without a model

- Scrapers per source with change detection.
- PDF text extraction; OCR for scanned pages with a confidence score; low-confidence pages go to review.
- Segmentation by legal structure using the numbering conventions of Indian statutes and rules (Section → sub-section → clause → proviso; Rule → sub-rule → proviso; Explanation).
- **Amendment linker**: rule-based parser for the standard drafting patterns in Central Tax notifications ("in rule X, in sub-rule (Y), for the words ..., the words ... shall be substituted", "shall be inserted", "shall be omitted", "with effect from"). Produces a proposed new Version with effective date. Every proposal is reviewed by a human before publishing. Ambiguous patterns are flagged, not guessed.
- Rate schedules parsed from notification annexures into the RateEntry table; every rate change creates a new dated row.

### 2.3 Explainer pages (replace generated explanations)

A curated, versioned set of pages, each with: title, plain-language text (English + chosen Indic languages), the provisions it relies on (linked, so citations render automatically), last-reviewed date, reviewer. Seeded from CBIC FAQs and the department's existing FAQs. New pages are written when the gap report shows repeated unanswered queries. Target for v1: 150 pages covering registration, returns, ITC, rates, e-way bill, refunds, notices, appeals, composition, reverse charge, place of supply.

### 2.4 Notice decoder (template-based)

Upload PDF or image → OCR → detect form ID and section from known layouts (ASMT-10, DRC-01, DRC-01A, DRC-07, REG-17, REG-23, APL-02, etc.) → return: what this form is, governing section and rule, the reply form and time limit, and the explainer page for that notice type. No interpretation of the facts.

### 2.5 Officer drafting aid (template bank)

Reviewed templates for SCN, orders, replies and appeals, with placeholders and pre-linked citations. Officers fill placeholders in a form; the system assembles the document with a citation block. T2 only.

### 2.6 Multilingual

Statutory text stays in English (with the official Hindi text where available). Explainer pages, menus and form descriptions are translated once and reviewed. Search accepts Indic-script input via a transliteration map and the synonym dictionary; optional Bhashini machine translation of the query string.

---

## 3. Use cases (v1, all LLM-free)

| # | Use case | Mechanism |
|---|---|---|
| U1 | Provision lookup with citation | Identifier parser or keyword search → Version filtered by as-of date |
| U2 | Rule / form finder | Form table with governing rule and purpose |
| U3 | Rate finder with date | RateEntry lookup by HSN/SAC or description |
| U4 | Council decision tracker | CouncilDecision table with notified/pending status |
| U5 | Amendment history / diff | Text diff between Versions |
| U6 | Notice decoder | OCR + template detection |
| U7 | Compliance calendar | Rule engine on filer profile |
| U8 | Explainers | Curated pages |
| U9 | Officer template bank | T2 templates |
| U10 | Commissioner analytics | Query logs, gap report, corpus status |

---

## 4. Surfaces

- **Web PWA**: search box with facets (Act, level, date, topic), law browser (Act → Chapter → Section with version timeline), rate finder, form library, Council tracker, explainer library, notice decoder upload. Shareable permalinks per provision and version. Offline cache of Act and Rule text.
- **Telegram bot** (pilot): menu buttons + keyword search fallback. Zero approval friction.
- **WhatsApp bot** (after pilot): same state machine on the WhatsApp Business Platform through a BSP. Needs business verification, a dedicated number, and template approval.
- **REST API**: the same lookups for GSPs, ERPs and trade bodies.

---

## 5. Stack

| Layer | Choice |
|---|---|
| Web | Next.js PWA (TypeScript), server-rendered law pages |
| Core API | Python 3.12, FastAPI |
| Search | OpenSearch (BM25, synonyms, facets) |
| Store | PostgreSQL 16 |
| Cache / sessions | Redis |
| Ingestion | Python workers; pdfplumber / PyMuPDF; Tesseract or Surya OCR; Playwright for JS-heavy sites |
| Bots | python-telegram-bot; WhatsApp Cloud API via a BSP later |
| Infra | Docker Compose for pilot; Kubernetes or managed containers for production; India region |
| Quality | Golden set of questions with expected records; automated regression on every corpus update |

No AI-provider account, no API key, no inference budget.

---

## 6. Quality gates (LLM-free)

- **Coverage**: every section and rule in scope has at least one published Version.
- **Identifier parser accuracy**: 100% on the golden set of identifier queries.
- **Search quality**: expected record in the top 3 for at least 90% of golden keyword queries; top 1 for at least 75%.
- **Amendment correctness**: every published Version traced to an Instrument with an effective date, reviewer-signed.
- **Gap rate**: share of queries that reach "no match" is tracked weekly and drives the explainer backlog.

---

## 7. Roadmap

| Phase | Duration | Deliverable |
|---|---|---|
| P0 Setup | 1–2 weeks | Repo, schema, corpus acquisition (scrape or upload), golden set v0 (100 queries), reviewer onboarding |
| P1 Pilot | 6–8 weeks | CGST Act + Rules + forms + Central notifications + Council decisions ingested; identifier parser; search; web PWA; Telegram bot; 50 explainers; English + one Indic language |
| P2 Public | 4–6 weeks | State SGST corpus, rate finder history, amendment diff, notice decoder, WhatsApp, 150 explainers, analytics |
| P3 Officer tier | 4–6 weeks | SSO, internal corpus, template bank, adjudication mode |
| P4 Scale | ongoing | More states, case-law index, API partners |

Shorter than v0.1 because there is no model layer, no prompt engineering, and no hallucination evaluation.

---

## 8. Inputs required from the project owner before build

### 8.1 Decisions (blocking)
1. **First state** for the SGST corpus (assumed Kerala) and its department website.
2. **Where the code lives**: a new repository (recommended, e.g. `gst-sahayak`) or a folder in this one.
3. **Corpus access path**: allow scraping of the public sources from the build environment, or supply the documents (PDFs of Acts, Rules, notifications, Council minutes) as an upload, a shared drive folder, or a zip in the repository.
4. **Pilot channels**: web + Telegram (recommended) or web only.
5. **Languages for v1** beyond English (assumed Hindi + Malayalam).
6. **Public tier first** (recommended) or officer tier in the first build.

### 8.2 People
7. **One reviewer with GST expertise** (CA, practitioner or departmental officer) who will approve ingested amendments and sign off the golden set and explainer pages. Roughly 4–6 hours a week during P1.
8. **Who approves the disclaimer text and product name.**

### 8.3 Content (any of these helps, none is blocking)
9. Existing department FAQs, circular lists, rate schedule spreadsheets, form lists.
10. Any internal SOPs or circulars intended for the officer tier (later phase).
11. Logo and colour preference for the web surface.

### 8.4 Credentials (only at deployment, never pasted into chat; set as environment secrets)
12. Telegram bot token (created by you via BotFather, two minutes).
13. Domain name and DNS access.
14. Hosting account (VPS or cloud in an India region) or a decision to use a department-provided server.
15. Later: WhatsApp Business Platform access through a BSP, verified business and phone number.

### 8.5 Not required
- No AI-provider API keys.
- No GSTN or GSP credentials (the system never writes to the GST portal).
- No taxpayer data of any kind.

---

## 9. What the first build increment will contain (on instruction)

1. Repository skeleton: `core/` (FastAPI), `ingest/`, `web/`, `bots/telegram/`, `evals/`, `docker-compose.yml`.
2. Knowledge schema and migrations for provisions, versions, instruments, forms, rates, council decisions, explainers, synonyms.
3. Ingestion for the CGST Act and CGST Rules with version history; parsers for Central Tax notifications; Council press releases.
4. Identifier parser, OpenSearch index, citation builder.
5. Web PWA with search, law browser and rate finder; Telegram bot with menus and search.
6. Golden set of 100 queries with an automated regression runner.
