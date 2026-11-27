# 01 — Needs Discovery & Domain Glossary

> **Traceability Root**: This document establishes the empirical foundation for **Solveur Magique** *(working codename)* by synthesizing two primary discovery sources:
> 1. **Stakeholder Discovery Interview** — A recorded walkthrough of real-world monthly schedule creation with a Swiss care-sector team manager (strictly anonymized below).
> 2. **Market, Legal & Technical Viability Study** — Analysis of Swiss shift-scheduling demand, labor law (`LTr`, `OLT 2`, `L-GAV`, cantonal `CCT`), data protection (`nLPD`), constraint-programming feasibility (`CP-SAT`), pricing, and Swiss sovereign hosting economics.

---

## 1. Empirical Findings from Field Discovery (Anonymized)

*All personal and institutional identifiers from the field interview have been replaced with fictional equivalents: **Fondation Les Tilleuls** (Swiss care foundation), **Claire** (unit/team manager), **Sophie** (part-time colleague), **Nadia** (colleague), and **Martine** (former manager of a larger 13-person unit).*

### 1.1 Current As-Is Workflow: "Spreadsheet-Like Legacy ERP"
At **Fondation Les Tilleuls**, schedules are entered into an institutional web-based ERP that functions essentially as a glorified spreadsheet grid:
- **Manual code entry**: Managers place their cursor inside a cell and type raw alphanumeric codes by hand — e.g., `V` (vacation), `X` (day off), `MC1` (shift code, such as split/morning-evening care blocks `07:00–09:00` and `16:00–21:00`), or `SDE/9/11` (*séance d'équipe* from 09:00 to 11:00) — and rely heavily on copy-paste.
- **No input guardrails**: Typing an invalid code (e.g., `B`) is accepted without warning; the ERP only recognizes known shift codes to sum total monthly hours per employee.
- **Basic visual outputs only**: The ERP provides a monthly matrix (rows = staff with `%` *pensum*, monthly target hours, scheduled hours, running overtime/deficit column; columns = days `1..31` with pink shading for weekends and darker shading for public holidays; footer = daily headcount and total daily hours). It offers **no shift-slot coverage view** and **no automated scheduling suggestions**.

### 1.2 Observed Pain Points & Operational Failure Modes

| # | Observed Problem | Real Operational Consequence |
| :-: | :--- | :--- |
| **P1** | **Silent coverage errors (*"plantées graves"*)** | In larger teams (13+ staff), managers have accidentally assigned two people to the same weekend shift while leaving another shift completely uncovered. The ERP raises zero alerts; errors are only caught when staff read the printed schedule. |
| **P2** | **No fatigue or rest-period checks** | The ERP never warns when an employee finishes at `21:00` and restarts at `07:00` (10h turnaround vs. statutory 11h rest) or is scheduled for 6+ consecutive days (*"6 jours bloc"*). Validation is 100% mental. |
| **P3** | **Manual hour-balance drift (`±10h` rule vs. `-30h` deficit)** | The foundation mandates a monthly hour tolerance of **`±10h`** balanced across the year. Without proactive balance optimization, managers in 13-person teams copy-paste schedules month-to-month; employees accumulate deficits as severe as **`-30h` by December**, creating end-of-year conflict and stress. |
| **P4** | **Rigid copy-paste & arbitrary wish caps** | To survive manual scheduling in a 13-person unit, former manager *Martine* either copy-pasted static monthly templates or imposed arbitrary caps on employee monthly requests — blocking compatible wishes while still failing to prevent incompatible ones. |
| **P5** | **Unfair distribution of recurring soft preferences** | *Sophie* has a young teenager and prefers not to work Tuesday evenings or Wednesdays. Respecting her preference manually forces *Claire* to absorb early-week shifts repeatedly, causing *Claire* to miss her own recurring hobbies (badminton, theater). There is no systematic multi-month fairness balancing. |
| **P6** | **Complex implicit operational rules** | Real schedules combine non-trivial domain rules: (a) requesting a week of vacation (`V`) **automatically protects the weekends immediately before and after**; (b) new hires require paired **onboarding shifts (*doublure*)** with an experienced colleague; (c) extra *doublures* are sometimes needed just to meet an employee's contractual hours; (d) fixed team meetings (`SDE`) must be slotted accurately. |
| **P7** | **Manual replacement-pool (*pouliste*) gap detection** | When permanent staff are unavailable (vacation, onboarding restriction, long consecutive stretch), the manager must mentally deduce which slots cannot be filled and mark them *"vide disponible"* to request an external *pouliste* (on-call pool worker). |
| **P8** | **Institutional buyer reality** | When asked about paying for a helper tool, *Claire* immediately noted: *"In that case, it would be the foundation paying for it."* Team managers will adopt a simple tool if it removes pain, **but they will not pay personally** — and organizational adoption requires institutional approval. |

---

## 2. Synthesis of Market, Legal & Technical Viability Findings

### 2.1 Structural Swiss Market Drivers
- **Extreme part-time prevalence**: Switzerland has Europe's second-highest part-time rate — **38.6%** of the active workforce (Q4 2025) and **58.6%** of working women. A small team of `3.5–4 FTE` (*EPT*) frequently comprises **7–9 individuals**, and `12 FTE` easily reaches **20–25 people** (including auxiliary and pool staff). Combinatorial scheduling complexity starts at just **6–8 employees**.
- **SME density**: **99.7%** of Swiss enterprises are SMEs.
- **High-fit target verticals (irregular hours + strict legal rules)**:
  1. **Care, Social & Long-Term Institutions (Beachhead #1)**: ~1,600 Swiss EMS (nursing homes), socio-educational homes (ARTISET / INSOS / CURAVIVA networks), and rapidly growing home-care services (*Spitex*: 29.6M care hours in 2025, +15.3% YoY; 44,000+ staff). Smaller foundations and decentralized units still rely on spreadsheets or rigid legacy grids.
  2. **Hospitality & Gastronomy (`L-GAV`)**: 20,000+ GastroSuisse members and ~3,963 hotels. Strict `L-GAV` Art. 21 compliance acts as a strong financial trigger (avoiding the 125% overtime penalty saves ~CHF 3,840/year even for an 8-person venue).
  3. **Independent Retail, Pharmacies & Field Services**: 66,600+ registered retail entities combining extended opening hours, student auxiliaries, and part-time contracts.
- **Competitive whitespace**: The Swiss market is polarized between heavy enterprise suites (*Polypoint PEP*, *Abacus AbaPlan*, *Lobos*, *Mirus* — expensive, quote-only, complex) and generic EU/US drag-and-drop tools (*Skello*, *Papershift*, *Shiftbase*, *Deputy*, *Connecteam* — per-employee pricing that penalizes Swiss part-time teams, weak Swiss `LTr`/`OLT 2` presets, non-Swiss hosting). Meanwhile, the #1 competitor remains **Excel + WhatsApp + Bexio**.

### 2.2 Swiss Legal & Regulatory Constraints
1. **Swiss Labor Law (`LTr`, `OLT 2`, `L-GAV`, cantonal `CCT`)**:
   - Weekly maximums: `45h` (office/large retail/industrial) or `50h` (care/homes/small hospitality); `L-GAV` norm `42h`–`45h`.
   - Daily span & breaks: Max `14h` span (`12.5h` effective work); mandatory breaks of `15 min` (>5.5h), `30 min` (>7h), `60 min` (>9h).
   - Daily rest: Minimum **`11h` consecutive** (reducible under strict averaging: `8h` 1×/week under `LTr`, or `9h` with `12h` 2-week average under Art. 9 `OLT 2`).
   - Consecutive days & Sundays: Max `6` consecutive days (`7` under strict `OLT 2` hospital/home rules); compensatory rest of `24h + 11h = 35h` (or `36h + 11h` in clinics) for Sundays >5h; minimum `12–18` free Sundays/year in care/homes; `2` rest days/week in `L-GAV`.
   - Night work (`23:00–06:00`) & supplements: `+10%` mandatory time supplement (≥25 nights/year, non-cashable); certain cantonal social CCTs (e.g., Vaud 2026) grant `+20%` time between `20:00` and `06:00`.
   - Publication & archival: `L-GAV` / `OLT 1` requires publishing schedules **2 weeks in advance**; Art. 46 `LTr` mandates **5-year record retention**.
2. **Revised Swiss Federal Act on Data Protection (`nLPD` / `nFADP`)**:
   - In force since September 1, 2023 for all Swiss organizations regardless of size.
   - **Personal criminal liability up to CHF 250,000** (Art. 60–62 `nLPD`) against the *responsible natural person* for intentional breach of minimum security standards, using a processor without a compliant Data Processing Agreement (`DPA`, Art. 9), or unlawful cross-border data transfers.
   - Absence reasons (illness, pregnancy, medical restrictions) constitute **sensitive personal data** (Art. 5 let. c `nLPD`).
   - **Implication**: Selling "Shadow IT" to managers on personal credit cards is legally dangerous and commercially fragile. The product **must** offer a **Zero-PII Anonymous Sandbox** for risk-free bottom-up evaluation, followed by a 1-click **"Pack Direction"** (ROI + pre-signed `nLPD` DPA + Swiss hosting attestation) for institutional B2B conversion, backed by **100% Swiss sovereign hosting** (outside the US CLOUD Act).

### 2.3 Technical Feasibility Boundaries
- **Discrete Constraint Programming (`CP-SAT`)**: Shift rostering is an NP-hard discrete combinatorial problem (binary assignment variables $x_{e,d,s} \in \{0,1\}$), *not* continuous linear algebra. **Google OR-Tools CP-SAT** (Apache 2.0, C++ core via Python) solves typical 5–60 staff fixed-shift instances in milliseconds to a few seconds on standard CPUs (no GPUs required) and supports exact conflict core extraction via `SufficientAssumptionsForInfeasibility`.
- **Critical V1.0.0 Boundary**: Research (ICAPS 2026 CASP:ER) demonstrates that continuous 30–60 minute granularity explodes to ~180k variables / ~350k constraints with 36%–99% optimality gaps after 600s. Therefore, **V1.0.0 must strictly model predefined discrete shifts** (deferring continuous hour-by-hour demand decomposition to a future release).

---

## 3. Domain Glossary

| Term | Language / Origin | Definition in Solveur Magique |
| :--- | :--- | :--- |
| **Pensum / Taux d'occupation** | Swiss FR / DE | Contractual employment percentage (e.g., `100%`, `80%`, `60%`) defining an employee's monthly target working hours. |
| **Solde d'heures** | Swiss FR | Cumulative hour balance (overtime `+h` or deficit `-h`) carried across months relative to contractual *pensum*. |
| **Shift Template / Code** | Domain | A predefined discrete work block with a custom ERP code (e.g., `MC1`, `M`, `S`, `N`), start/end times (including split shifts), unpaid break deduction, and effective paid duration. |
| **Doublure** | Swiss Care FR | Shadowing/onboarding assignment where a junior or newly hired employee is paired on the same shift alongside an experienced colleague (does not independently satisfy solo coverage requirements unless configured). |
| **Pouliste** | Swiss Care FR | On-call / replacement pool worker external to the core team who fills uncovered slots (*"vide disponible"*) when permanent staff cannot cover demand legally or due to absences. |
| **SDE (*Séance d'équipe*)** | Swiss Care FR | Scheduled mandatory team meeting with custom time bounds (e.g., `09:00–11:00`) that counts toward working hours and interacts with rest periods. |
| **Pinning (*Verrouillage*)** | Scheduling | Locking specific cells/assignments manually so the solver treats them as immutable constraints when re-optimizing the remaining schedule. |
| **Hard Constraint** | Optimization | An inviolable rule (labor law, approved vacation, coverage minimum, pinned cell). Violation renders a schedule infeasible. |
| **Soft Constraint (Preference)** | Optimization | A weighted desire (e.g., "prefer not to work Tuesday evenings", hour-balance closeness, multi-month equity) maximized by the solver's objective function without arbitrary request quotas. |
| **Infeasibility Core** | CP-SAT | Minimal subset of mutually contradictory hard constraints extracted by the solver and translated into plain human language. |
| **LTr / OLT 1 / OLT 2** | Swiss Law | *Loi sur le travail* (Federal Labor Act) and its Ordinances (notably `OLT 2` special exemptions for healthcare, nursing homes, and social institutions). |
| **L-GAV / CCT** | Swiss Law | Collective Bargaining Agreements (*Convention collective de travail*; `L-GAV` specifically governs Swiss hospitality/gastronomy). |
| **nLPD / nFADP** | Swiss Law | Revised Swiss Federal Act on Data Protection (effective Sept 1, 2023), including Art. 9 (`DPA`) and Art. 60–62 (personal fines up to CHF 250k). |
| **Pack Direction** | Commercial | One-click generated institutional PDF dossier containing ROI estimate, pre-signed `nLPD` DPA, and Swiss hosting security attestation to unlock B2B purchase approval. |

---

## 4. Derived Stakeholder Needs Catalog

Every requirement (`FR`/`NFR`) and use case (`UC`) in subsequent documents must trace directly to one or more of the following stakeholder needs:

| Need ID | Category | Stakeholder Need Statement | Source(s) |
| :--- | :--- | :--- | :--- |
| **NEED-01** | Interoperability | Managers need to keep their existing institutional ERP for official payroll/HR while using a fast companion optimizer that exports schedules as ERP-mapped **Excel (`.xlsx`)** (and CSV/PDF) ready for manual transcription or import. | User Vision, Interview (P1, P8) |
| **NEED-02** | Coverage Safety | Managers need automated verification and optimization of shift coverage so that **no shift is silently left uncovered or accidentally double-booked**. | Interview (P1) |
| **NEED-03** | Legal Compliance | Managers and directors need built-in, one-click Swiss labor law presets (`LTr`, `OLT 2`, `L-GAV`, customizable `CCT`) enforcing rest periods, consecutive-day caps, weekly limits, and Sunday/night rules automatically. | Interview (P2), Viability (§1) |
| **NEED-04** | Hour-Balance Control | Managers need the solver to respect contractual *pensums* and monthly tolerance corridors (e.g., `±10h/month`) while tracking cumulative carry-over balances to prevent end-of-year deficits (e.g., `-30h`). | Interview (P3) |
| **NEED-05** | Fair Preference Optimization | Staff and managers need unlimited submission of soft preferences (recurring or one-off) optimized fairly across months via rolling equity weights, eliminating arbitrary monthly request quotas and chronic favoritism. | Interview (P4, P5), Viability (§1) |
| **NEED-06** | Domain-Specific Operational Rules | Care and service managers need native support for real-world operational patterns: custom shift codes (including split shifts), vacation pre/post-weekend protection, fixed team meetings (`SDE`), and *doublure* (onboarding pairing). | Interview (P6) |
| **NEED-07** | Replacement Pool (*Pouliste*) Signaling | When permanent staff cannot legally or feasibly cover all shifts, managers need the system to explicitly flag minimal open *"pouliste required"* slots rather than failing blindly. | Interview (P7) |
| **NEED-08** | Human-in-the-Loop Control (*Pinning*) | Managers need to lock (*pin*) specific assignments (validated shifts, sudden illness replacements, forced swaps) and re-optimize only unlocked slots without destroying the rest of the monthly schedule. | Viability (§1), Interview (P1) |
| **NEED-09** | Explainable Infeasibility | When constraints are mathematically impossible, managers need plain-language conflict explanations identifying the exact conflicting staff, dates, and rules so they know what to relax. | Viability (§1) |
| **NEED-10** | Familiar, Low-Friction UX | Non-technical team managers need an intuitive monthly matrix grid mirroring familiar ERP layouts (employee rows, day columns, weekend/holiday highlights, daily headcount/hours totals, running hour deltas) usable without lengthy training. | Interview (P1, P8) |
| **NEED-11** | Fast, Predictable Compute | Managers need discrete-shift optimization to return high-quality schedules within seconds (under 5s–30s depending on tier) even during end-of-month publication peaks. | Viability (§1, §5) |
| **NEED-12** | Zero-PII Trial & `nLPD` Compliance | Managers need a legally risk-free **Anonymous Sandbox** (pseudonyms only, zero sensitive medical reasons stored) so they can evaluate the solver immediately without violating `nLPD` or needing IT approval first. | Viability (§3) |
| **NEED-13** | 100% Swiss Sovereign Data Hosting | Institutions and directors need contractual assurance that all personal/scheduling data is stored and processed exclusively in ISO 27001 Swiss data centers (outside the US CLOUD Act) with a signed `nLPD` DPA and 5-year legal archiving option. | Viability (§3, §5) |
| **NEED-14** | Frictionless B2B Institutional Purchase | Managers need a 1-click **Pack Direction** (ROI summary + DPA + hosting proof) and institutions need **Swiss QR-Bill** annual invoicing (alongside card payments) so foundations and SMEs can subscribe effortlessly. | Interview (P8), Viability (§3, §4) |
| **NEED-15** | Part-Time-Friendly Pricing | Swiss organizations with high part-time ratios need flat-tier CHF pricing by team-size bracket (not per-head fees) so they include all part-time and auxiliary staff without financial penalty. | Viability (§4) |
| **NEED-16** | Scalable Self-Service Wish Collection *(Higher Tiers)* | Growing teams (10–60 staff) on higher commercial tiers need an optional way for employees to submit their own availability and soft preferences digitally, eliminating paper notes and WhatsApp chats. | Viability (§4), User Scope |
