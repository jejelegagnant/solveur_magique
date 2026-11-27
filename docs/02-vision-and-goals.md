# 02 — Project Vision & Strategic Goals

> **Traceability**: Derives directly from [`docs/01-needs-discovery.md`](01-needs-discovery.md) (`NEED-01`–`NEED-16`) and defines the strategic boundaries for V1.0.0 (initial commercial sales release).

---

## 1. Product Vision Statement

> **For** team managers and directors of Swiss care, social, hospitality, and service SMEs (5–35 employees per team)
> **Who** lose hours every month building part-time shift schedules manually in rigid, validation-free ERPs or spreadsheets while risking Swiss labor-law violations and unfair staff rosters,
> **Solveur Magique** *(working codename)* is a **100% Swiss-hosted, constraint-programming (CP-SAT) scheduling companion**
> **That** computes legally compliant, fair, hour-balanced monthly schedules in seconds—with transparent conflict explanations, manual cell pinning, and clean ERP-mapped Excel/CSV exports—
> **Unlike** heavy enterprise ERP suites (*Polypoint PEP*, *Abacus AbaPlan*) or generic foreign drag-and-drop tools (*Skello*, *Papershift*, *Deputy*) that charge per employee and ignore Swiss legal nuances,
> **Our product** plugs in alongside the customer's existing ERP with zero migration friction, zero-PII trial onboarding, and flat-tier CHF pricing built for Switzerland's part-time workforce.

---

## 2. Core Product Pillars

1. **Companion-First, Zero-Migration Interoperability (`NEED-01`)**: We do *not* ask a foundation or SME to rip out Polypoint, Abacus, Bexio, or Crésus on day one. V1.0.0 acts as the *intelligent solver brain* that exports clean, shift-code-mapped **Excel (`.xlsx`)** (plus CSV, PDF, iCal) ready for instant transcription or automated import into the legacy ERP.
2. **Mathematical Fairness & Explainable Optimization (`NEED-02`, `NEED-04`, `NEED-05`, `NEED-08`, `NEED-09`)**: Replace copy-pasted static schedules and arbitrary wish caps with discrete CP-SAT optimization, rolling multi-month equity scores, manual *pinning*, explicit *pouliste* open-slot detection, and plain-language infeasibility diagnostics.
3. **Swiss-Native Legal Compliance (`NEED-03`, `NEED-06`)**: First-class presets for `LTr`, `OLT 2` (Care/Homes), `L-GAV` (Hospitality), and custom cantonal `CCT` overrides—plus native care-domain primitives (vacation weekend buffering, *doublure* onboarding pairs, split shifts, `±10h` monthly hour corridors).
4. **Trust-by-Design Sovereignty & Frictionless B2B Conversion (`NEED-12`, `NEED-13`, `NEED-14`, `NEED-15`)**: Zero-PII Anonymous Sandbox to eliminate personal `nLPD` exposure during evaluation, 1-click *Pack Direction* PDF for management sign-off, 100% Swiss sovereign hosting (Geneva/Zurich, outside US CLOUD Act), and flat-tier CHF pricing payable via Stripe or Swiss QR-Bill.

---

## 3. Strategic Goals for V1.0.0 Commercial Launch

| Goal ID | Objective | Measurable Success Target (V1.0.0) | Linked Needs |
| :--- | :--- | :--- | :--- |
| **GOAL-01** | **Dramatic Time Reduction** | Reduce monthly schedule drafting time for a 5–25 person team from `3–8 hours` to **`< 30 minutes`** end-to-end (including manual pinning tweaks and Excel export). | `NEED-01`, `NEED-08`, `NEED-10`, `NEED-11` |
| **GOAL-02** | **Zero Silent Schedule Defects** | Guarantee **`100%`** automated detection of coverage gaps, double-bookings, statutory rest violations (`LTr`/`OLT 2`/`L-GAV`), and `±10h` monthly balance breaches on every published or exported schedule. | `NEED-02`, `NEED-03`, `NEED-04`, `NEED-06`, `NEED-07` |
| **GOAL-03** | **Measurable Roster Fairness** | Eliminate arbitrary monthly wish caps and achieve **`≥ 85%`** soft-preference satisfaction on feasible monthly schedules while balancing satisfaction scores across rolling 3–6 month windows. | `NEED-05`, `NEED-09` |
| **GOAL-04** | **Sub-10-Minute Risk-Free Onboarding** | Enable a first-time team manager to configure a team and generate their first valid optimized schedule in the Zero-PII Anonymous Sandbox in **`< 10 minutes`** with zero IT involvement. | `NEED-10`, `NEED-12` |
| **GOAL-05** | **Legal & Sovereign Trust Readiness** | Launch commercially with **`100%`** of customer workloads and backups hosted in ISO 27001 Swiss data centers, a downloadable pre-signed `nLPD` Art. 9 DPA, and zero sensitive medical free-text fields in the database. | `NEED-12`, `NEED-13` |
| **GOAL-06** | **Sustainable Unit Economics from Day 1** | Maintain launch infrastructure cost **`≤ CHF 50/month`** (Infomaniak Swiss Cloud), achieving operational break-even at **`2–3 paying teams`** and **`> 90%`** unit gross margin across paid tiers. | `NEED-11`, `NEED-14`, `NEED-15` |
| **GOAL-07** | **Commercial Sales Readiness (Care & Services)** | Support self-serve subscription (Stripe CHF) and institutional invoicing (Swiss QR-Bill), flat-tier quota gating (including Pro-tier employee wish collection), and 1-click *Pack Direction* conversion at V1.0.0 launch. | `NEED-14`, `NEED-15`, `NEED-16` |

---

## 4. Target Market & Commercial Positioning

### 4.1 Target Verticals for V1.0.0 Launch
1. **Primary Beachhead — Care, Social & Long-Term Institutions**: Swiss EMS, socio-educational homes, disability foundations (*ARTISET / INSOS / CURAVIVA* networks), and home-care (*Spitex*) units with 5–35 staff operating under `OLT 2` and cantonal social `CCT`s.
2. **Secondary Vertical — Service & Hospitality (`L-GAV`)**: Independent restaurants, small hotels, bakeries, and catering teams facing strict `L-GAV` Art. 21 scheduling and documentation audits.
3. **Tertiary Vertical — Independent Retail & Pharmacies**: Multi-shift retail shops and pharmacies coordinating part-time staff and student auxiliaries under `LTr` general rules.

### 4.2 Commercial Packaging & Pricing Alignment (CHF Flat Tiers)
Flat-tier pricing by team-size bracket eliminates the "part-time penalty" imposed by per-employee SaaS competitors and creates a natural upgrade ladder:

| Tier | Monthly (CHF) | Annual (CHF, ~2 mo. free) | Capacity | V1.0.0 Feature Allocation |
| :--- | :---: | :---: | :--- | :--- |
| **Découverte (Free)** | **0** | **0** | ≤ 5 staff, 1 team | Zero-PII Anonymous Sandbox, 5 CP-SAT solves/mo (5s cap), basic `LTr` preset, watermarked PDF/Excel preview. |
| **Équipe (Starter)** | **39** | **390** | ≤ 10 staff, 1 site | Unlimited solves (15s cap), conflict explainer, manual pinning, `LTr`/`OLT 2`/`L-GAV` presets, *doublure* & *pouliste* flags, full ERP-mapped Excel/CSV/PDF/iCal exports, *Pack Direction*. |
| **PME (Pro)** | **69** | **690** | ≤ 25 staff, 1–2 sites | Everything in Starter + **Employee Wish Submission Portal** (higher-tier exclusive), multi-month rolling fairness, custom `CCT` overrides, email schedule distribution, 30s solver cap. |
| **Institution (Business)** | **129** | **1,290** | ≤ 60 staff (+CHF 2/extra) | Everything in Pro + multi-unit teams, executed `nLPD` DPA, **5-year legal archive** (Art. 46 `LTr`), payroll CSV templates (Bexio/Abacus/Crésus), **Swiss QR-Bill** invoicing. |

*Tax & Swiss legal entity evolution*:
- **V1.0.0 Launch (*Raison individuelle* / Sole Proprietorship)**: Launching as a Swiss *raison individuelle* keeps startup cost and administrative overhead near zero (simplified accounting under CHF 500k per Art. 957 al. 2 CO; no mandatory Commercial Register entry or `8.1%` VAT registration below `CHF 100,000` annual turnover per Art. 934 CO & Art. 10 LTVA — ~170 paying teams at CHF 49 ARPU). Because a *raison individuelle* carries unlimited personal liability, V1.0.0 enforces strict risk hygiene: zero medical/health fields in the database, 100% Swiss hosting, and explicit Terms/DPA wording positioning Solveur Magique as a **scheduling decision-support tool** where the employer retains final statutory compliance sign-off.
- **Scale-Up Path (Sàrl / GmbH Conversion)**: All generated legal and financial artifacts (*Pack Direction*, `nLPD` DPA, Stripe invoices, Swiss QR-Bills) must read vendor identity (`legal_name`, `brand_name`, `address`, optional `IDE/UID`, optional `VAT` toggle, `QR-IBAN`, `dpa_version`) from configuration so transitioning to a **Sàrl** once commercial traction grows requires **zero code changes**.

---

## 5. V1.0.0 Scope Boundaries (In-Scope vs. Post-V1 Roadmap)

Strict scope discipline is essential for a solo/lean commercial launch:

| Domain | Included in **V1.0.0 (Commercial Launch)** | Deferred to **V1.1 / V2.0 (Post-Launch)** |
| :--- | :--- | :--- |
| **Scheduling Paradigm** | Predefined discrete shifts (`MC1`, `M`, `S`, `N`, split shifts, custom `SDE` events). | Continuous hour-by-hour demand decomposition / auto-shift generation. |
| **Optimization Engine** | Google OR-Tools CP-SAT with hard legal/coverage rules, soft weighted wishes, rolling equity, manual cell pinning, *pouliste* open-slot slack, and human-readable infeasibility cores. | Multi-site vehicle/route scheduling (e.g., *Spitex* geographic routing), automated shift-swap marketplace. |
| **ERP Integration** | Configurable **Excel (`.xlsx`)** shift-code export, standardized CSV templates (Bexio/Abacus/Crésus/generic ERP), printable PDF, iCal (`.ics`). | Bidirectional REST/SOAP API connectors to Polypoint PEP, Abacus AbaPlan, Bexio, or Crésus. |
| **Employee Access** | Manager-entered schedules in all tiers; lightweight web-based **Employee Wish Submission Link/Portal** gated to **Pro & Business tiers**. | Native iOS/Android mobile apps, push notifications, digital timeclock / badgeuse, actual-vs-planned hours reconciliation. |
| **Legal & Compliance** | `LTr`, `OLT 2`, `L-GAV` presets + custom `CCT` parameters; Zero-PII Sandbox; Swiss hosting; 1-click *Pack Direction* & DPA; 5-year archive (Business). | Automated cantonal labor-inspectorate audit submissions, full Swissdec ELM payroll calculation. |
| **Localization** | UI localized in **English, French, and German** (French/German prioritized for Swiss end-users; internal engineering docs in English). | Italian (`IT-CH`) localization and cross-border EU labor presets (France HCR, Germany ArbZG). |
