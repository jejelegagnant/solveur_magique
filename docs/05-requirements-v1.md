# 05 — Detailed Functional & Non-Functional Requirements (V1.0.0 Commercial Launch)

> **Traceability**: Translates [`docs/01-needs-discovery.md`](01-needs-discovery.md) (`NEED-01`–`NEED-16`), [`docs/02-vision-and-goals.md`](02-vision-and-goals.md) (`GOAL-01`–`GOAL-07`), and [`docs/03-users-and-use-cases.md`](03-users-and-use-cases.md) (`UC-01`–`UC-12`) into verifiable, unambiguous engineering specifications for **V1.0.0** (initial commercial sales release across Swiss care & service industries).

---

## 1. Conventions & Prioritization (MoSCoW)

- **`Must`**: Non-negotiable for V1.0.0 commercial launch; launch is blocked without passing acceptance criteria.
- **`Should`**: High-value commercial capability (typically differentiated in **Pro / Business** tiers) targeted for V1.0.0 GA.
- **`Could`**: Desirable polish included if schedule permits without slipping V1.0.0 launch.
- **Tier Legend**: `Free` (Découverte, ≤5 staff) · `Starter` (Équipe, ≤10 staff) · `Pro` (PME, ≤25 staff) · `Business` (Institution, ≤60+ staff).

---

## 2. Functional Requirements (`FR-001`–`FR-048`)

### 2.1 Workspace, Authentication & Zero-PII Anonymous Sandbox

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-001** | `Must` | Free+ | **Zero-PII Anonymous Sandbox Creation**: Allow any visitor to launch an instant sandbox workspace without credit card or real personal identifiers, pre-populated with pseudonymized staff labels (`Staff A`, `Staff B`, etc.). | Sandbox opens in ≤2 clicks; displays prominent `nLPD` non-PII banner; supports full shift setup and solving up to Free-tier limits. | `NEED-12`, `UC-01` |
| **FR-002** | `Must` | All | **Seamless Sandbox Promotion**: Preserve all shift templates, coverage matrices, and legal presets when a user upgrades a sandbox session into a registered Organization account. | Zero configuration loss on conversion; user can optionally map pseudonyms to real staff names post-upgrade. | `NEED-12`, `UC-01`, `UC-11` |
| **FR-003** | `Must` | All | **Sovereign Account Registration & Authentication**: Support email/password registration (Argon2id hashing) and optional passwordless magic-link sign-in hosted exclusively on Swiss infrastructure. | Passwords meet minimum entropy rules; sessions use `HttpOnly`, `Secure`, `SameSite=Lax` cookies; zero third-party US auth dependencies. | `NEED-13`, `UC-11` |
| **FR-004** | `Must` | Starter+ | **Multi-Tenant Role-Based Access Control (RBAC)**: Enforce distinct roles per Organization: `OrgAdmin` (billing/DPA/multi-unit), `TeamManager` (schedule/staff editing for assigned teams), and `StaffViewer` (Pro+ wish portal). | A `TeamManager` of Unit A cannot read or mutate schedules of Unit B or any other Organization. | `NEED-13`, `UC-11` |
| **FR-005** | `Must` | All | **Tier Quota & Entitlement Enforcement**: Enforce flat-tier limits dynamically across active staff count (`5 / 10 / 25 / 60+`), team count, monthly solve count (`5/mo` on Free, unlimited on paid), and solver time cap (`5s / 15s / 30s`). | Exceeding a tier cap returns a deterministic HTTP `402`/`403` error code and renders a non-destructive upgrade prompt. | `NEED-15`, `UC-01`, `UC-11` |

---

### 2.2 Team, Shift Templates & Swiss Cantonal Calendar

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-006** | `Must` | All | **Team & Swiss Cantonal Holiday Calendar**: Allow each team to select its Swiss canton (`FR`, `VD`, `GE`, `BE`, `ZH`, etc.) to auto-populate official cantonal public holidays (*jours fériés*) for any calendar year. | Public holidays are visually distinguished in the monthly grid and automatically treated as holiday-coverage days. | `NEED-06`, `UC-02` |
| **FR-007** | `Must` | All | **Custom Discrete Shift Templates & ERP Codes**: Allow managers to define reusable discrete shifts with custom ERP short codes (e.g., `MC1`, `M`, `S`, `N`), color, display name, and required role tags. | Custom codes are unique per team and preserved verbatim in UI grid cells and Excel/CSV exports. | `NEED-01`, `NEED-06`, `UC-02` |
| **FR-008** | `Must` | All | **Split-Shift & Break Modeling**: Support single-segment and multi-segment (**split shifts**, e.g., `07:00–09:00` + `16:00–21:00`) per shift template, with configurable unpaid break minutes vs. paid on-post breaks. | System automatically calculates effective paid duration and total daily span (start of first segment to end of last segment) and warns if `LTr` break thresholds (`15m`/`30m`/`60m`) are unmet. | `NEED-03`, `NEED-06`, `UC-02` |
| **FR-009** | `Must` | All | **Day-Type & Date-Override Coverage Matrix**: Allow managers to specify minimum and target staff headcounts per shift template for `Weekday`, `Saturday`, `Sunday`, and `Public Holiday`, plus individual date overrides. | Every shift slot for every day of a schedule period resolves to a deterministic `(min_headcount, target_headcount)` pair. | `NEED-02`, `UC-02` |
| **FR-010** | `Must` | All | **Custom Non-Shift Status & Fixed Event Codes**: Support configurable ERP codes for non-shift cells — Vacation (`V`), Rest/Day Off (`X`), Generic Unavailable (`ABS`), Open Pool Slot (`VIDE`/`POULISTE`), and **Fixed Events** (`SDE` team meetings with arbitrary `HH:MM–HH:MM` intervals). | `SDE` events count toward an employee's monthly hours and daily rest/span calculations without consuming regular shift coverage headcount. | `NEED-01`, `NEED-06`, `UC-02`, `UC-05` |
| **FR-011** | `Should` | Starter+ | **Vertical Starter Templates**: Provide 1-click starter team templates for Swiss Care/EMS (`OLT 2`), Hospitality (`L-GAV`), and Retail (`LTr`) to accelerate onboarding. | Selecting a template pre-populates realistic shifts, coverage matrix, and legal preset editable immediately by the manager. | `NEED-10`, `UC-01`, `UC-02` |

---

### 2.3 Employee Profiles, Pensum, Hour Balances & *Doublure*

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-012** | `Must` | All | **Staff Contractual *Pensum* & Target Hours**: Store each employee's contractual employment rate (`pensum` `5%–100%`), weekly/monthly full-time base hours, and qualified shift templates. | Monthly contractual target hours adjust accurately for month length, approved vacation days (`V`), and statutory public holidays. | `NEED-04`, `UC-04` |
| **FR-013** | `Must` | All | **Cumulative *Solde d'heures* & Monthly Tolerance Corridor**: Track each employee's carried-over hour balance from previous months and enforce a configurable monthly tolerance corridor (default `±10.0h`, customizable per team/employee). | Solver and UI compute both monthly delta (`scheduled - target`) and projected cumulative ending balance (`carry_over + monthly_delta`), flagging breaches immediately. | `NEED-04`, `UC-04`, `UC-09` |
| **FR-014** | `Must` | All | **Data-Minimization Staff Schema (`nLPD`)**: Restrict staff profiles to scheduling essentials only (pseudonym/name, optional work email on paid tiers, pensum, role tags); **explicitly exclude** medical diagnoses, AHV/AVS numbers, salaries, or free-text health fields. | Database schema and API reject/omit sensitive `nLPD` Art. 5 let. c health attributes by design. | `NEED-12`, `NEED-13`, `UC-04` |
| **FR-015** | `Must` | Starter+ | **Onboarding / *Doublure* Pairing Rule**: Allow marking an employee as `Trainee (Doublure)` for a date range paired with one or more `Mentor`-eligible staff, configuring whether the trainee counts toward solo coverage headcount (default: `false`). | Solver guarantees a trainee is never scheduled alone on a shift without a qualified mentor on the same shift/day. | `NEED-06`, `UC-04`, `UC-06` |
| **FR-016** | `Should` | Starter+ | **Optional Hours-Completion *Doublure* Allowance**: Allow managers to permit surplus paired shifts (*doublure* above minimum headcount) on specified days when needed to help a part-time employee meet their contractual minimum hours. | Solver only uses extra *doublure* assignments when standard coverage slots cannot keep an employee within their lower hour-balance corridor. | `NEED-04`, `NEED-06`, `UC-04` |

---

### 2.4 Constraints, Vacation Buffers & Soft Preferences

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-017** | `Must` | All | **Hard Vacations (`V`) & Automatic Weekend Protection**: Allow managers to enter vacation date ranges with a configurable rule (enabled by default) that automatically blocks the **Saturday/Sunday immediately preceding and following** a full-week vacation as hard unavailability (`X`). | Entering Mon–Fri vacation automatically marks adjacent Sat/Sun unavailable unless explicitly overridden by the manager; solver never assigns shifts on protected days. | `NEED-06`, `UC-05` |
| **FR-018** | `Must` | All | **Hard Unavailability & Fixed `SDE` Assignments**: Allow entering hard unavailable days/shifts (`X`/`ABS`) and fixed mandatory events (`SDE` with start/end times) for one or all team members. | Hard unavailabilities cannot be violated; fixed `SDE` slots are pre-assigned and factored into daily rest and weekly hours. | `NEED-06`, `UC-05` |
| **FR-019** | `Must` | All | **Unlimited Weighted Soft Preferences**: Allow entering an unlimited number of soft preferences per employee per month (e.g., *"avoid Tuesday evening"*, *"prefer morning shift"*, *"day off desired"*) with 3 priority weights (`Low`, `Medium`, `High`), both one-off and recurring weekly templates. | No artificial monthly cap on requests; solver maximizes weighted preference satisfaction without failing if preferences conflict. | `NEED-05`, `UC-05`, `UC-06` |
| **FR-020** | `Should` | Pro+ | **Rolling Multi-Month Fairness Engine**: Maintain a rolling historical satisfaction index per employee across finalized months (configurable 3-to-6-month window) and dynamically boost preference weights for staff who experienced lower satisfaction in recent months. | When two employees have mutually exclusive soft wishes, the employee with the lower historical satisfaction score receives higher priority in the CP-SAT objective. | `NEED-05`, `UC-06` |
| **FR-021** | `Should` | Pro+ | **Tokenized Employee Wish Submission Portal**: Allow managers on Pro/Business tiers to open a monthly wish-collection window and email employees a secure, mobile-responsive link to submit their own vacation requests and soft preferences. | Submitted soft wishes flow directly into the draft period; vacation requests require explicit manager approval before becoming hard constraints; closing the window locks edits. | `NEED-16`, `UC-12` |

---

### 2.5 Swiss Legal Rule Engine (`LTr` / `OLT 2` / `L-GAV` / `CCT`)

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-022** | `Must` | All | **Built-in Swiss Legal Presets**: Provide 1-click legal rule presets encoding statutory Swiss constraints: `LTr General (45h/50h)` (Free+), `OLT 2 Care & Homes` (Starter+), and `L-GAV Hospitality` (Starter+). | Activating a preset immediately populates all underlying numeric parameters with plain-language legal references. | `NEED-03`, `UC-03` |
| **FR-023** | `Must` | All | **Daily Rest & Span Enforcement**: Enforce minimum consecutive rest between shifts (default **`11h`**; `OLT 2` option: reducible to **`9h`** provided 2-week average ≥ **`12h`**) and maximum daily work span (`14h` span / `12.5h` effective work). | Solver rejects any consecutive shift pair across day boundaries (including month boundary from prior month's last day!) that violates active rest rules. | `NEED-03`, `UC-03`, `UC-06` |
| **FR-024** | `Must` | All | **Consecutive Working Days & Weekly Rest**: Enforce maximum consecutive working days (default **`6`** under `LTr`, configurable to **`7`** under `OLT 2` strict cap) and mandatory weekly rest (including `L-GAV` **`2` rest days/week** and `35h`/`47h` Sunday compensatory rest when Sunday shift >5h). | No generated schedule contains illegal 7+ day streaks or missing weekly/Sunday compensatory rest under the active preset. | `NEED-03`, `UC-03`, `UC-06` |
| **FR-025** | `Must` | Starter+ | **Sunday Quota & Night-Work Time Supplement Tracking**: Track annual free Sundays against configurable minimums (`12` or `18`/year under `OLT 2`) and calculate automatic night-work time credits (`+10%` for `23:00–06:00` under `LTr`, or customizable `+20%` for `20:00–06:00` under cantonal social `CCT`s). | Night time supplements are transparently itemized in the employee's monthly hour total and exported summary. | `NEED-03`, `NEED-04`, `UC-03`, `UC-09` |
| **FR-026** | `Should` | Pro+ | **Custom `CCT` Rule Overrides**: Allow Pro/Business managers to clone a Swiss preset and fine-tune parameters (weekly max, rest minimums, night bonus window/percentage, consecutive weekend cap) for cantonal or institutional collective agreements. | Custom `CCT` rules are versioned per period so historical schedules retain the exact rules active when published. | `NEED-03`, `UC-03` |

---

### 2.6 CP-SAT Optimization Engine, Pinning, Diagnostics & *Poulistes*

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-027** | `Must` | All | **Discrete Fixed-Shift CP-SAT Solver**: Formulate and solve the monthly scheduling problem using Google OR-Tools CP-SAT over binary variables $x_{e,d,s} \in \{0,1\}$ respecting all active hard constraints and optimizing the multi-term weighted soft objective. | Produces mathematically verified schedules with `0` hard constraint violations within the tier timeout (`5s / 15s / 30s`); gracefully returns best incumbent feasible solution if timeout is reached before global optimality proof. | `NEED-02`, `NEED-03`, `NEED-11`, `UC-06` |
| **FR-028** | `Must` | All | **Cross-Month Boundary Continuity**: Automatically load the final 7 days of the previous finalized month (assignments, shift end times, consecutive working day streak, carry-over *solde d'heures*) as fixed boundary context for the new month's solve. | Solver prevents illegal 1st-of-month rest violations (e.g., evening shift on 31st → morning shift on 1st) and 6-day streaks crossing month-end. | `NEED-03`, `NEED-04`, `UC-06` |
| **FR-029** | `Must` | Starter+ | **Manual Cell *Pinning* & Stability Re-Solve**: Allow managers to lock (*pin*) any subset of cells (assignments or explicit days off) and trigger a partial re-solve that keeps all pinned cells immutable while minimizing unnecessary changes to previously generated unlocked cells. | 100% of pinned cells remain identical after re-optimization; stability penalty minimizes churn on unaffected days. | `NEED-08`, `UC-08` |
| **FR-030** | `Must` | Starter+ | **Human-Readable Infeasibility Diagnostics**: When CP-SAT proves a problem `INFEASIBLE`, execute `SufficientAssumptionsForInfeasibility` on labeled constraint assumptions and translate the minimal conflict core into clear natural-language explanations (FR/DE/EN). | Every `INFEASIBLE` response identifies the exact conflicting dates, employees, and rules plus ≥1 actionable resolution button. | `NEED-09`, `UC-07` |
| **FR-031** | `Must` | Starter+ | **Explicit *Pouliste* Open-Slot Slack Modeling**: Provide an opt-in (default-on) *"Allow Pouliste Open Slots"* solver mode that introduces high-penalty slack variables for unmet shift coverage, ensuring the solver fills maximum legal slots with permanent staff and flags remaining gaps as **`POULISTE`**. | Rather than crashing on understaffed weekends, solver minimizes total *pouliste* slots needed and lists each open slot with date, shift code, and reason permanent staff couldn't cover it. | `NEED-07`, `UC-06`, `UC-07` |
| **FR-032** | `Must` | All | **Real-Time Validation of Manual Grid Edits**: Whenever a manager manually types or modifies a shift cell in the grid, run instant deterministic validation checking all hard rules (rest periods, consecutive days, double-booking, coverage, hour corridor). | Violations highlight the offending cell(s) within `< 200ms` with clear tooltip explanations; manager may acknowledge an override only where legally permissible or revert. | `NEED-02`, `NEED-03`, `UC-08` |
| **FR-033** | `Should` | Starter+ | **Multi-Option Schedule Comparison**: Allow requesting up to 2–3 distinct high-scoring feasible schedule alternatives (varying tie-breaks or fairness/balance weights) for side-by-side KPI comparison before adopting one. | Manager can compare KPIs (wish %, hour-balance max deviation, *pouliste* count) and switch active draft in 1 click. | `NEED-05`, `NEED-08`, `UC-06` |

---

### 2.7 Interactive Monthly Matrix Grid UI

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-034** | `Must` | All | **ERP-Familiar Monthly Matrix View**: Render the monthly schedule as a responsive grid: sticky left employee columns (`Name/Pseudonym`, `% Pensum`, `Target h`, `Scheduled h`, `Monthly Delta`, `Cumulative Solde`), scrollable day columns (`1..31`), and sticky bottom coverage/hours summary rows. | Supports keyboard navigation, visual shading for weekends (distinct tint) and cantonal public holidays (darker tint), and color-coded hour-balance badges (`green` inside corridor, `amber` near limit, `red` breached). | `NEED-10`, `UC-09` |
| **FR-035** | `Must` | All | **Daily Coverage & Headcount Footer**: Display per-day shift coverage counters (e.g., `MC1: 2/2`, `S: 1/2 ⚠`), total staff present, and total scheduled hours at the bottom of every day column. | Immediately surfaces any under-covered or over-covered shift slot (eliminating silent weekend double-bookings). | `NEED-02`, `NEED-10`, `UC-09` |
| **FR-036** | `Must` | All | **Cell Inspector & Wish-Satisfaction Indicators**: Display pin status, *doublure* badge, *pouliste* marker, and subtle wish-match indicator inside cells, with a hover/click popover showing exact shift timestamps, rest gap from prior shift, and preference status. | Manager can inspect full context of any assignment without leaving the monthly grid. | `NEED-05`, `NEED-08`, `NEED-10`, `UC-09` |
| **FR-037** | `Must` | All | **Month Finalization & Carry-Over Rollover**: Provide a **"Finalize Month"** workflow that locks the approved schedule snapshot, records the publication timestamp (supporting 2-week advance compliance), and propagates ending `solde d'heures` and boundary days into the next month. | Finalized schedules become read-only (amendable only via versioned revision log); next month automatically inherits accurate carry-over balances. | `NEED-04`, `NEED-13`, `UC-09` |
| **FR-038** | `Should` | Pro+ | **One-Click Email Schedule Publication**: Allow managers on Pro/Business tiers to email staff when a monthly schedule is finalized, attaching their personal `.ics` calendar file and summary link. | Emails are dispatched via Swiss SMTP containing zero sensitive absence reasons. | `NEED-16`, `UC-09` |

---

### 2.8 ERP Companion Export Engine

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-039** | `Must` | Starter+ *(Watermarked preview on Free)* | **ERP-Mapped Excel Workbook (`.xlsx`) Export**: Generate a styled multi-sheet Excel workbook containing: (1) **Monthly Matrix Sheet** matching the team's exact ERP codes (`MC1`, `V`, `X`, `SDE/9/11`, `VIDE`), weekend/holiday shading, employee hour balances, and daily totals; (2) **Normalized Flat Import Sheet** (`Employee_Code, Date, Shift_Code, Start, End, Paid_Hours, Is_Doublure`); (3) **Pouliste Request Sheet** listing all open slots. | Generated `.xlsx` opens cleanly without warnings in Microsoft Excel and LibreOffice Calc; Excel formulas recalculate totals dynamically if edited downstream. | `NEED-01`, `NEED-07`, `UC-10` |
| **FR-040** | `Must` | Starter+ | **Configurable CSV Export & Mapping Profiles**: Allow exporting flat or matrix CSV files with customizable delimiter (`;` default for Swiss Excel, or `,`), UTF-8 BOM, date format (`DD.MM.YYYY` / `YYYY-MM-DD`), and saved column-mapping profiles. | Managers can save reusable mapping profiles matching their institutional ERP's import template. | `NEED-01`, `UC-10` |
| **FR-041** | `Should` | Business | **Swiss Payroll/Accounting CSV Presets**: Include pre-built monthly hour-summary CSV export templates formatted for **Bexio**, **Abacus**, and **Crésus** (planned hours, night supplements, Sunday hours, monthly delta). | Exported CSV imports cleanly into target template schemas without manual column reformatting. | `NEED-01`, `UC-10` |
| **FR-042** | `Must` | All | **Clean Printable Landscape PDF**: Generate an A4/A3 landscape printable schedule poster preserving shift colors, weekend/holiday shading, and daily totals (watermarked on Free tier; clean with optional organization header on paid tiers). | PDF renders cleanly at 1-page-per-team fit for up to 25 staff without clipping text. | `NEED-01`, `NEED-10`, `UC-10` |
| **FR-043** | `Should` | Starter+ | **Employee iCal (`.ics`) Export**: Generate standard RFC 5545 `.ics` files per employee containing their assigned shifts and `SDE` events (excluding colleague schedules). | Imports cleanly into Apple Calendar, Google Calendar, and Outlook with accurate `Europe/Zurich` timezone handling (including DST transitions). | `NEED-10`, `UC-10` |

---

### 2.9 Commercial Launch, Billing, *Pack Direction* & Localization

| ID | Priority | Tier | Requirement Description | Acceptance Criteria | Traceability |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **FR-044** | `Must` | All | **One-Click *Pack Direction* PDF Generator**: Generate a polished 2-page PDF dossier populated with the user's team size, transparent ROI calculation, pre-signed Swiss **`nLPD` Art. 9 DPA** (with explicit decision-support / employer-sign-off clause and config-driven vendor legal identity supporting *raison individuelle* → Sàrl evolution), and Infomaniak ISO 27001 Swiss hosting attestation. | Generated in `< 3s` from Sandbox or Free workspace in FR, DE, or EN; vendor legal name, address, IDE/UID, and `dpa_version` are loaded from config without code changes; includes unique upgrade URL linking back to the saved sandbox. | `NEED-12`, `NEED-13`, `NEED-14`, `UC-11` |
| **FR-045** | `Must` | Paid | **Stripe Switzerland Self-Serve Checkout**: Integrate Stripe Billing in **CHF** supporting domestic credit/debit cards and **TWINT** for monthly and annual flat-tier plans (`Starter`, `Pro`, `Business`), automated dunning, and customer billing portal. | Webhook-driven subscription activation completes in `< 5s`; invoices load vendor legal identity from config and support Swiss formatting (`0%` non-VAT-registered note for *raison individuelle* under CHF 100k LTVA threshold, or `8.1%` VAT when toggled on). | `NEED-14`, `NEED-15`, `UC-11` |
| **FR-046** | `Must` | Business *(Annual Starter/Pro opt-in)* | **Native Swiss QR-Bill Invoicing**: Generate compliant **ISO 20022 Swiss QR-Bill** PDF invoices (with config-driven creditor legal name/address/QR-IBAN, structured reference, CHF amount, optional VAT line, and 30-day due date) for annual institutional subscriptions, plus an Operator reconciliation endpoint to mark invoices paid. | QR code passes official SIX Swiss Payment Standards validation; creditor details switch cleanly from *raison individuelle* to Sàrl via config; subscription activates smoothly on institutional approval. | `NEED-14`, `UC-11` |
| **FR-047** | `Must` | Business | **5-Year Statutory Schedule Archival (`Art. 46 LTr`)**: Automatically archive finalized monthly schedules, active legal rule snapshots, and publication timestamps in immutable, downloadable audit bundles retained for **5 years**. | OrgAdmins can export a signed ZIP/PDF compliance archive for any past 5-year date range in 1 click. | `NEED-13`, `UC-09` |
| **FR-048** | `Must` | All | **Trilingual UI Localization (`FR` / `DE` / `EN`)**: Provide complete UI, conflict explanation, and export label localization in **French (`fr-CH`)**, **German (`de-CH`)**, and **English (`en`)**, using Swiss date (`DD.MM.YYYY`), 24h time, and `CHF` number formatting. | Switching locale updates all UI labels, Swiss legal descriptions, and CP-SAT conflict messages immediately without data loss. | `NEED-10`, `NEED-14` |

---

## 3. Non-Functional Requirements (`NFR-001`–`NFR-025`)

### 3.1 Performance & Solver Scalability

| ID | Metric / Constraint | Quantitative Target | Verification Method | Traceability |
| :--- | :--- | :--- | :--- | :--- |
| **NFR-001** | **Typical CP-SAT Solve Latency** | Median (`p50`) solve time **`< 2.0s`** and `p95` **`< 10.0s`** for standard fixed-shift teams of 5–35 staff over a 31-day month. | Automated benchmark suite on 2-vCPU reference worker. | `NEED-11`, `GOAL-01` |
| **NFR-002** | **Hard Solver Timeout & Fairness Guardrails** | Strict per-job CPU wall-clock ceilings enforced in worker: **`5s` (Free)**, **`15s` (Starter)**, **`30s` (Pro/Business)**; zero HTTP worker thread blocking. | Integration test verifying timeout cutoff & graceful incumbent return. | `NEED-11`, `GOAL-06` |
| **NFR-003** | **End-of-Month Burst Concurrency** | Async job queue absorbs **`5×` publication-week bursts** (modeled via Little's Law: up to `1.25` concurrent solves at 1,000 teams, `5.0` at 4,000 teams) with queue wait time `p95 < 15s` at target scale. | Load test simulating 50 concurrent monthly solve submissions. | `NEED-11`, `GOAL-06` |
| **NFR-004** | **Interactive Grid Responsiveness** | Grid rendering, cell pinning, and real-time manual edit rule validation complete in **`< 200ms`** (`p95`) for a 60-staff × 31-day matrix (`1,860` cells). | Frontend performance profiling & Playwright timing check. | `NEED-10` |
| **NFR-005** | **Export Generation Latency** | `.xlsx`, `.csv`, `.pdf`, and *Pack Direction* PDF generation completes in **`< 3.0s`** (`p95`). | API integration timing assertions. | `NEED-01`, `NEED-14` |

### 3.2 Security & Swiss `nLPD` Legal Compliance

| ID | Metric / Constraint | Quantitative Target | Verification Method | Traceability |
| :--- | :--- | :--- | :--- | :--- |
| **NFR-006** | **100% Swiss Sovereign Data Residency** | **`100%`** of application compute, primary PostgreSQL storage, Redis queue, transactional email relay, and encrypted backups physically reside in **ISO 27001 certified Swiss data centers (Geneva/Zurich)** operated by Swiss legal entities outside US CLOUD Act jurisdiction. | Infrastructure-as-Code & vendor contract audit (Infomaniak / Exoscale CH). | `NEED-13`, `GOAL-05` |
| **NFR-007** | **Strict Multi-Tenant Data Isolation** | Enforce tenant isolation at both application middleware and **PostgreSQL Row-Level Security (RLS)** layers; zero cross-tenant data leakage possible even under ORM query bugs. | Automated security test suite asserting cross-tenant read/write returns 0 rows / `403`. | `NEED-13`, `GOAL-05` |
| **NFR-008** | **Encryption in Transit & at Rest** | All external traffic encrypted with **TLS 1.3** (HSTS enabled); database volumes and S3 backups encrypted with **AES-256**; passwords hashed via **Argon2id**. | SSL Labs A+ check; infrastructure encryption audit. | `NEED-13`, `GOAL-05` |
| **NFR-009** | **Privacy by Design & Data Minimization (`nLPD`)** | Zero sensitive medical free-text fields in schema; Zero-PII Anonymous Sandbox auto-purges unclaimed ephemeral sessions after **30 days**; error logs/Sentry telemetry scrub all employee names and emails before capture. | Schema lint check, log redaction unit tests, TTL purge job test. | `NEED-12`, `NEED-13`, `GOAL-05` |
| **NFR-010** | **Data Subject Rights & Portability (`nLPD`)** | OrgAdmin can export complete tenant data (JSON/CSV) or permanently erase an employee/organization (hard-delete respecting 5-year statutory archive separation) within **`< 24 hours`** via self-service controls. | End-to-end deletion & export compliance test. | `NEED-13` |
| **NFR-011** | **Immutable Security & Compliance Audit Log** | Log all authentication events, DPA acceptances, schedule finalizations, role changes, and data exports with UTC timestamps and actor IDs (tamper-evident append-only table). | Audit trail verification tests. | `NEED-13`, `GOAL-05` |
| **NFR-012** | **OWASP Web Security Baseline** | Enforce CSRF protection, strict Content-Security-Policy (CSP), parameterized SQL (zero raw string interpolation), rate limiting on auth & solve endpoints, and automated dependency vulnerability scanning in CI. | CI SAST/dependency checks (`bandit`, `pip-audit`, `npm audit`). | `NEED-13` |

### 3.3 Usability & Accessibility

| ID | Metric / Constraint | Quantitative Target | Verification Method | Traceability |
| :--- | :--- | :--- | :--- | :--- |
| **NFR-013** | **Time-to-First-Schedule** | A first-time non-technical team manager completes setup and generates a valid schedule in the Anonymous Sandbox in **`< 10 minutes`** without reading a manual. | Moderated usability tests with ≥5 Swiss care/service managers. | `NEED-10`, `GOAL-04` |
| **NFR-014** | **Accessibility & Browser Support** | Comply with **WCAG 2.1 Level AA** color contrast (never rely solely on color to convey rest violations or weekend shading — pair with icons/patterns); support latest 2 versions of Chrome, Firefox, Safari, and Edge. | Automated Lighthouse/axe accessibility score ≥90. | `NEED-10` |
| **NFR-015** | **Responsive Mobile Wish Portal** | Employee Wish Submission Portal (`FR-021`) is fully usable on mobile viewports (`≥ 360px` width); Manager Matrix Grid targets desktop/tablet (`≥ 1024px`) with graceful horizontal scrolling on smaller screens. | Playwright viewport regression tests. | `NEED-10`, `NEED-16` |

### 3.4 Reliability, Availability & Disaster Recovery

| ID | Metric / Constraint | Quantitative Target | Verification Method | Traceability |
| :--- | :--- | :--- | :--- | :--- |
| **NFR-016** | **Service Availability** | Target **`99.9%`** monthly uptime (≤43 min unplanned downtime/month), backed by Infomaniak 99.99% infrastructure SLA and zero-downtime rolling Docker container deployments. | External uptime monitoring + healthcheck probes. | `NEED-11` |
| **NFR-017** | **Backup, RPO & RTO** | Automated daily encrypted PostgreSQL backups + continuous WAL archiving to **Infomaniak Swiss Backup S3**; **`RPO ≤ 24h`** (≤15 min at 100+ teams with WAL), **`RTO ≤ 4h`**; quarterly restore drill. | Automated staging restore script verification. | `NEED-13`, `GOAL-05` |
| **NFR-018** | **Idempotent & Fault-Tolerant Solver Jobs** | Worker crash or OOM restarts cleanly without corrupting draft schedules; dead-letter queue alerts operator while returning a clear retryable status to UI. | Chaos test killing solver worker mid-execution. | `NEED-11` |

### 3.5 Maintainability, Testability & FinOps

| ID | Metric / Constraint | Quantitative Target | Verification Method | Traceability |
| :--- | :--- | :--- | :--- | :--- |
| **NFR-019** | **Deterministic Solver Invariant Verification** | **`100%`** of Swiss legal constraints (`LTr`, `OLT 2`, `L-GAV`), *doublure* rules, and vacation weekend buffers verified via automated unit & property-based tests (Pytest + Hypothesis) on every PR; fixed random seeds for reproducible test runs. | GitHub Actions CI gating every merge to `main`. | `NEED-02`, `NEED-03`, `GOAL-02` |
| **NFR-020** | **Decoupled Solver Domain Module** | CP-SAT model builder (`solver_core`) has zero web/HTTP or database ORM dependencies, accepting pure Pydantic schemas so it can be benchmarked, unit-tested, or scaled to dedicated compute nodes independently. | Architectural import boundary check (`import-linter`). | `NEED-11` |
| **NFR-021** | **Containerized Portability** | Entire stack builds and boots reproducibly via Docker Compose (`docker compose up`) for local dev and sovereign VPS production with zero cloud-vendor lock-in. | Clean-slate CI container boot & smoke test. | `GOAL-06` |
| **NFR-022** | **Launch Infrastructure Cost Ceiling (FinOps)** | V1.0.0 launch hosting cost (up to 10–30 active teams) **`≤ CHF 50/month`**; marginal compute/storage cost per Free-tier team **`≤ CHF 0.15/month`**; unit gross margin on paid tiers **`> 90%`**. | Monthly cloud billing tracking vs. MRR dashboard. | `GOAL-06`, `NEED-15` |
| **NFR-023** | **Zero-PII Observability & Alerting** | Structured JSON logs, Prometheus metrics (solve duration, queue depth, infeasible rate, HTTP 5xx), and self-hosted error tracking (GlitchTip) running on Swiss infrastructure with PII scrubbing enabled. | Telemetry audit & synthetic error alert test. | `NEED-13`, `GOAL-05` |
| **NFR-024** | **Timezone & DST Correctness** | All timestamps stored in UTC internally and converted accurately to `Europe/Zurich` for shift duration, daily rest, and iCal exports—explicitly handling spring-forward (`23h` day) and fall-back (`25h` day) DST transitions without breaking 11h rest math. | Dedicated DST boundary unit tests (March & October transitions). | `NEED-03` |
| **NFR-025** | **Backward-Compatible Schema Migrations** | All PostgreSQL schema evolutions managed via versioned Alembic migrations tested forward and backward in CI before production rollout. | CI migration up/down test on realistic seed database. | `GOAL-06` |

---

## 4. Requirements Traceability Matrix (RTM)

| Need ID | Strategic Goal(s) | Use Case(s) | Functional Requirements (`FR`) | Non-Functional Requirements (`NFR`) |
| :--- | :--- | :--- | :--- | :--- |
| **NEED-01** | `GOAL-01` | `UC-02`, `UC-10` | `FR-007`, `FR-010`, `FR-039`, `FR-040`, `FR-041`, `FR-042` | `NFR-005` |
| **NEED-02** | `GOAL-02` | `UC-02`, `UC-06`, `UC-09` | `FR-009`, `FR-027`, `FR-032`, `FR-035` | `NFR-019` |
| **NEED-03** | `GOAL-02` | `UC-03`, `UC-06` | `FR-008`, `FR-022`, `FR-023`, `FR-024`, `FR-025`, `FR-026`, `FR-028`, `FR-032` | `NFR-019`, `NFR-024` |
| **NEED-04** | `GOAL-02` | `UC-04`, `UC-06`, `UC-09` | `FR-012`, `FR-013`, `FR-016`, `FR-025`, `FR-028`, `FR-037` | `NFR-019` |
| **NEED-05** | `GOAL-03` | `UC-05`, `UC-06`, `UC-12` | `FR-019`, `FR-020`, `FR-033`, `FR-036` | `NFR-001` |
| **NEED-06** | `GOAL-02` | `UC-02`, `UC-04`, `UC-05` | `FR-006`, `FR-007`, `FR-008`, `FR-010`, `FR-015`, `FR-016`, `FR-017`, `FR-018` | `NFR-019` |
| **NEED-07** | `GOAL-02` | `UC-06`, `UC-07`, `UC-08` | `FR-031`, `FR-039` | `NFR-001` |
| **NEED-08** | `GOAL-01` | `UC-08` | `FR-029`, `FR-033`, `FR-036` | `NFR-004` |
| **NEED-09** | `GOAL-03` | `UC-07` | `FR-030` | `NFR-001`, `NFR-013` |
| **NEED-10** | `GOAL-01`, `GOAL-04` | `UC-01`, `UC-02`, `UC-09`, `UC-10` | `FR-011`, `FR-034`, `FR-035`, `FR-036`, `FR-042`, `FR-043`, `FR-048` | `NFR-004`, `NFR-013`, `NFR-014`, `NFR-015` |
| **NEED-11** | `GOAL-01`, `GOAL-06` | `UC-06` | `FR-027` | `NFR-001`, `NFR-002`, `NFR-003`, `NFR-016`, `NFR-018`, `NFR-020` |
| **NEED-12** | `GOAL-04`, `GOAL-05` | `UC-01`, `UC-04`, `UC-05`, `UC-11` | `FR-001`, `FR-002`, `FR-014`, `FR-044` | `NFR-009` |
| **NEED-13** | `GOAL-05` | `UC-10`, `UC-11` | `FR-003`, `FR-004`, `FR-014`, `FR-037`, `FR-044`, `FR-047` | `NFR-006`, `NFR-007`, `NFR-008`, `NFR-009`, `NFR-010`, `NFR-011`, `NFR-012`, `NFR-017`, `NFR-023` |
| **NEED-14** | `GOAL-06`, `GOAL-07` | `UC-11` | `FR-044`, `FR-045`, `FR-046`, `FR-048` | `NFR-005`, `NFR-022` |
| **NEED-15** | `GOAL-06`, `GOAL-07` | `UC-04`, `UC-11` | `FR-005`, `FR-045` | `NFR-022` |
| **NEED-16** | `GOAL-07` | `UC-12` | `FR-021`, `FR-038` | `NFR-015` |
