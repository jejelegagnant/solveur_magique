# 03 — Users, Personas & Use Case Scenarios

> **Traceability**: Maps stakeholder needs (`NEED-01`–`NEED-16`) and goals (`GOAL-01`–`GOAL-07`) into concrete user archetypes and behavioral scenarios (`UC-01`–`UC-12`) for V1.0.0. All names and institutions below are fictional.

---

## 1. User Personas

### Persona 1 — Claire (Unit / Team Manager — Swiss Care Foundation)
- **Role & Context**: Leads a residential care unit (3–15 staff plus external *poulistes*) at *Fondation Les Tilleuls* in Western Switzerland. Must enter final monthly schedules into a rigid institutional ERP grid (`MC1`, `V`, `X`, `SDE`) two weeks in advance.
- **Tech Comfort**: Moderate (comfortable with web browsers, Excel, and her legacy ERP; has zero patience for complex configuration or opaque "black-box" software).
- **Primary Pain Points**:
  - Manually balancing `±10h/month` contractual corridors across part-time staff while avoiding `-30h` end-of-year drifts.
  - Fear of silent weekend double-bookings or uncovered shifts.
  - Mentally juggling vacation weekend buffers, new-hire *doublure* pairings, *pouliste* requests, and recurring colleague preferences without sacrificing her own evenings.
- **Goals**: Generate a fair, legally safe schedule in <30 minutes, tweak edge cases by locking (*pinning*) cells, and export an Excel sheet matching her ERP's exact codes.
- **Buying Power**: **Champion / Evaluator** (uses Anonymous Sandbox first; forwards *Pack Direction* to her director for budget sign-off).

---

### Persona 2 — Marc (Institution Director / HR Decision-Maker)
- **Role & Context**: Administrative director of a 45-employee Swiss social foundation or EMS operating 3–4 decentralized units under `OLT 2` and a cantonal `CCT`.
- **Tech Comfort**: Moderate-high; delegates daily rostering to unit leads like Claire but owns legal risk, IT compliance, and budget.
- **Primary Pain Points**:
  - Personal criminal liability under **`nLPD`** (up to CHF 250,000) if unit managers upload staff data into unauthorized US-hosted SaaS tools.
  - Labor-inspectorate audit exposure (missing rest periods or 5-year archive records).
  - Unwillingness to undergo a 12-month, CHF 50k+ ERP replacement project.
- **Goals**: Approve a low-cost, 100% Swiss-hosted companion tool with a signed `nLPD` DPA, predictable flat-tier CHF pricing, and annual **Swiss QR-Bill** invoicing.
- **Buying Power**: **Economic Buyer / Approver** (Starter / Pro / Business tiers).

---

### Persona 3 — Sophie (Part-Time Staff Member — 60% Pensum)
- **Role & Context**: Experienced social care educator working `60%` *pensum* with a teenage child. Strongly prefers avoiding Tuesday evenings and Wednesdays, and books family vacations well in advance.
- **Tech Comfort**: Smartphone-first; wants simple, transparent web interactions without installing another heavy corporate app.
- **Primary Pain Points**:
  - Arbitrary caps on monthly wish requests under old manual systems.
  - Feeling guilty when her preferences overload colleagues, or frustrated when her vacation weekends get accidentally booked.
  - Ending the year with unexpected `-20h` / `-30h` deficits or 6-day consecutive stretches.
- **Goals**: Submit her hard absences and soft preferences easily (via manager in Starter, or directly via a simple web portal in Pro/Business tiers) and receive fair, predictable monthly rosters.

---

### Persona 4 — Thomas (Owner-Manager — Independent Swiss Service / Hospitality SME)
- **Role & Context**: Runs a 12-person independent restaurant, bakery, or neighborhood pharmacy in Switzerland. Acts as both the weekly/monthly planner and the sole financial decision-maker.
- **Tech Comfort**: Practical; currently uses Excel, WhatsApp, and Bexio.
- **Primary Pain Points**:
  - `L-GAV` / `LTr` audit risks (forgetting 2-week advance publication or failing to document rest/overtime, triggering 125% overtime penalties).
  - Coordinating 12 part-time staff and student auxiliaries who have ever-changing weekly exam/course availability.
  - Competitors charging CHF 5–9 *per head* even for students working 4 shifts/month.
- **Goals**: Quickly apply the `L-GAV` or `LTr` preset, run the solver in seconds, pay a flat CHF 39–69/month by card or QR-Bill, and export CSV/Excel cleanly for his accountant/Bexio.

---

### Persona 5 — Platform Operator (Secondary Actor — SaaS Support & Billing)
- **Role & Context**: Founder / operator maintaining Solveur Magique's Swiss cloud infrastructure.
- **Goals**: Monitor CP-SAT worker queue health during end-of-month spikes, reconcile Swiss QR-Bill bank transfers to activate/renew annual Business accounts, and inspect anonymized error telemetry with zero access to raw tenant PII unless explicitly authorized.

---

## 2. Detailed Use Case Scenarios (`UC-01`–`UC-12`)

### `UC-01` — Evaluate Solver in Zero-PII Anonymous Sandbox
- **Primary Actor**: Team Manager (Claire) or SME Owner (Thomas)
- **Linked Needs**: `NEED-10`, `NEED-12`
- **Preconditions**: User lands on the web app without an institutional account or IT approval.
- **Main Success Scenario**:
  1. User clicks **"Start Anonymous Sandbox"** (no credit card, no mandatory real names).
  2. System creates an ephemeral or free-tier sandbox workspace pre-seeded with pseudonymized labels (`Staff A`, `Staff B`, `Staff C` — or lets user enter custom pseudonyms) and an optional care/service starter template.
  3. System displays a clear `nLPD` privacy banner reminding the user not to input real employee names or medical details while in Sandbox mode.
  4. User defines 2–3 shifts, adjusts pensums/wishes, and clicks **Optimize** (up to 5 free solves/month, 5s solver timeout).
  5. System returns an optimized monthly grid and lets the user preview a watermarked PDF/Excel output.
- **Alternative Flows**:
  - *A1 — Conversion*: User clicks **"Save & Convert to Organization"** or **"Generate Pack Direction"** (`UC-11`), preserving all shift templates and rules without re-entering data.
  - *A2 — Quota Reached*: After 5 free solves or >5 staff, system prompts upgrade to *Starter* (`UC-11`).
- **Postconditions**: User experiences real CP-SAT value in <10 minutes with zero personal `nLPD` liability.

---

### `UC-02` — Configure Team, Shift Templates & Daily Coverage Matrix
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-01`, `NEED-02`, `NEED-06`, `NEED-10`
- **Preconditions**: Workspace exists (Sandbox or authenticated tenant).
- **Main Success Scenario**:
  1. Manager creates or edits a team and selects the Swiss canton (to auto-load cantonal public holidays, *jours fériés*).
  2. Manager defines discrete **Shift Templates**, specifying:
     - Custom **ERP Code** (e.g., `MC1`, `M`, `S`, `N`), color, and label.
     - One or more time segments (supporting **split shifts**, e.g., `07:00–09:00` + `16:00–21:00`).
     - Unpaid break duration and resulting effective paid hours (e.g., `7.0h`).
     - Optional role/qualification tag (e.g., *Educator*, *Nurse*, *Service*).
  3. Manager configures the **Coverage Matrix**: required minimum and target headcount per shift template for weekdays, Saturdays, Sundays, and public holidays (plus optional date-specific overrides).
  4. System validates time bounds and mandatory Swiss break thresholds (`15m`/`30m`/`60m`) and saves the configuration.
- **Alternative Flows**:
  - *A1 — Invalid Break Warning*: If a shift exceeds `5.5h`/`7h`/`9h` with insufficient unpaid break and is not marked as "paid on-post break", system warns the manager immediately.
- **Postconditions**: Team shift definitions and daily demand targets are stored and ready for optimization.

---

### `UC-03` — Configure Swiss Legal Rule Preset (`LTr` / `OLT 2` / `L-GAV` / `CCT`)
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-03`, `NEED-06`
- **Preconditions**: Team exists (`UC-02`).
- **Main Success Scenario**:
  1. Manager opens **Legal & Rule Settings** and chooses a Swiss preset:
     - **LTr General** (`45h` or `50h` weekly max, `11h` daily rest, max `6` consecutive days, `35h` Sunday compensatory rest).
     - **OLT 2 Care & Homes** (`50h` weekly max, `11h` daily rest reducible to `9h` if 2-week avg ≥ `12h`, up to `7` consecutive days under strict cap, min `12–18` free Sundays/year, `+10%`/`+20%` night time supplement).
     - **L-GAV Hospitality** (`42h`/`43.5h`/`45h` weekly norm, `11h` daily rest, `2` rest days/week including ≥1 full day).
  2. System displays human-readable summaries of each active hard constraint.
  3. *(Pro/Business tiers)* Manager optionally customizes cantonal `CCT` overrides (e.g., Vaud `+20%` night bonus between `20:00` and `06:00`, team-specific `±10h` monthly hour corridor).
  4. System saves the active `LegalRuleSet` versioned per schedule period.
- **Postconditions**: Every subsequent solve enforces the chosen Swiss legal constraints as hard rules (or explicitly flagged soft warnings where legally derogable).

---

### `UC-04` — Manage Staff Profiles, Pensums, Hour Balances & *Doublure* Rules
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-04`, `NEED-06`, `NEED-12`, `NEED-15`
- **Preconditions**: Team exists (`UC-02`).
- **Main Success Scenario**:
  1. Manager adds staff members (pseudonym in Sandbox; name + optional email in named tenant) up to the subscription tier cap.
  2. For each employee, manager configures:
     - Contractual **`pensum` (`%`)** and monthly base full-time hours (e.g., `168h` → `60%` = `100.8h`).
     - Allowed monthly balance corridor (e.g., `±10h`) and starting carry-over **`solde d'heures`** from the prior month (e.g., `-4.5h` or `+6.0h`).
     - Qualified shift templates / roles.
     - Optional **Onboarding / *Doublure* Flag**: designates employee as *Trainee* requiring co-assignment with a *Senior/Mentor* for specified dates (and whether the trainee counts toward solo headcount coverage).
  3. System computes each employee's exact target monthly hours for the selected schedule period (accounting for public holidays and approved vacation days).
- **Alternative Flows**:
  - *A1 — Tier Limit Reached*: Attempting to add employee #6 on Free or #11 on Starter displays clear flat-tier upgrade prompt without blocking existing schedules.
- **Postconditions**: Staff capacities, carry-over balances, and *doublure* constraints are persisted.

---

### `UC-05` — Capture Hard Absences, Fixed Events (`SDE`) & Soft Preferences
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-05`, `NEED-06`, `NEED-12`
- **Preconditions**: Schedule period (e.g., next month) and staff list exist (`UC-04`).
- **Main Success Scenario**:
  1. Manager enters **Hard Absences** on the monthly calendar:
     - **Vacation (`V`)**: When a contiguous vacation block (e.g., Mon–Fri) is entered, system offers/applies the **"Auto-protect adjacent weekends"** toggle (`X` before and after) as a hard unavailability constraint.
     - **Unavailability / Generic Absence (`X` / `ABS`)**: *No free-text medical/illness reason field is provided*, enforcing `nLPD` data minimization by design.
  2. Manager adds **Fixed Team Events** (e.g., `SDE` team meeting `09:00–11:00` on a specific date for selected staff) which count toward hours and rest checks.
  3. Manager enters unlimited **Soft Preferences** (one-off or recurring weekly rules, e.g., *"Sophie prefers no Tuesday evening / Wednesday"*, *"Claire prefers Monday evening off"*), each with priority weight (`Low` / `Medium` / `High`).
  4. System automatically adjusts soft-preference weights using each employee's historical rolling fairness score (Pro/Business) so no individual consistently bears the brunt of compromises.
- **Postconditions**: All hard blocks, fixed events, and weighted soft preferences are linked to the target schedule period.

---

### `UC-06` — Generate Optimized Monthly Schedule (CP-SAT)
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-02`, `NEED-03`, `NEED-04`, `NEED-05`, `NEED-07`, `NEED-11`
- **Preconditions**: Shifts, coverage matrix, legal preset, staff profiles, and requests exist (`UC-02`–`UC-05`).
- **Main Success Scenario**:
  1. Manager configures solve options (e.g., enable **"Allow *pouliste* open slots if team capacity is insufficient"**, enable **Carry-over balance correction**).
  2. Manager clicks **"Optimize Schedule"**.
  3. API validates inputs, checks tier quota, enqueues an asynchronous `SolverJob`, and streams progress to the UI.
  4. CP-SAT worker solves the discrete assignment model under hard constraints (coverage, `LTr`/`OLT 2`/`L-GAV`, vacations + buffers, `SDE`, *doublure*, pinned cells, monthly hour corridor) while maximizing the weighted soft objective (employee preferences, rolling equity, minimal hour-balance drift, minimal *pouliste* slack).
  5. Within seconds (capped by tier timeout: 5s/15s/30s), solver persists the optimal schedule (plus optional 2nd/3rd alternative solutions if requested) and computes summary KPIs (`%` preferences satisfied, hour deltas, *pouliste* slots needed, `0` legal violations).
  6. UI renders the completed monthly matrix grid (`UC-09`).
- **Alternative Flows**:
  - *A1 — Infeasible Constraints*: Solver proves no valid assignment satisfies all hard constraints → transitions directly to `UC-07`.
  - *A2 — Feasible Only with Pouliste Slots*: If *pouliste* slack is enabled, solver fills as much as legally possible with permanent staff and explicitly highlights uncovered slots as **`VIDE / POULISTE`** with explanation.
- **Postconditions**: A draft optimized monthly schedule is saved and ready for review.

---

### `UC-07` — Diagnose & Resolve Infeasible Constraints
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-07`, `NEED-09`
- **Preconditions**: `UC-06` returns `INFEASIBLE` status.
- **Main Success Scenario**:
  1. CP-SAT worker runs `SufficientAssumptionsForInfeasibility` on tracked constraint assumptions to extract the minimal conflicting subset.
  2. System translates internal constraint IDs into plain-language conflict cards in the user's language (FR/DE/EN), e.g.:
     - *"Tuesday 14 Evening (`MC1`) cannot be covered: Nadia is on Vacation (`V`), Sophie has a pinned shift conflict, and Claire would violate the 11h daily rest after Monday Evening."*
  3. System presents concrete 1-click resolution suggestions:
     - Mark the specific slot as **`POULISTE` (open pool slot)**;
     - Temporarily widen monthly hour tolerance (e.g., `±12h` instead of `±10h`);
     - Unpin a conflicting manual cell.
  4. Manager selects a resolution and clicks **"Re-Optimize"** (`UC-06`).
- **Postconditions**: Conflict is transparently understood and resolved without trial-and-error guesswork.

---

### `UC-08` — Pin Manual Assignments & Re-Optimize Partial Schedule
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-08`, `NEED-07`
- **Preconditions**: A draft or published schedule exists (`UC-06`).
- **Main Success Scenario**:
  1. Manager edits a specific cell (e.g., due to sudden illness, a manually agreed swap, or locking an already-validated week) and toggles the **Pin (lock icon)** on individual cells, rows, or date ranges.
  2. System runs instant real-time rule validation on the manual edit, displaying non-blocking or blocking warnings if the manual edit breaches daily rest or creates a double-booking.
  3. Manager clicks **"Re-Optimize Unlocked Cells"**.
  4. CP-SAT solver treats all pinned cells as immutable hard constraints and re-solves only the remaining unlocked slots while minimizing disruption to prior assignments (stability objective).
- **Postconditions**: Manager retains full human control without breaking the rest of the month.

---

### `UC-09` — Inspect Monthly Matrix Grid, Totals & Hour Deltas
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-02`, `NEED-04`, `NEED-10`
- **Preconditions**: A schedule exists (`UC-06` or manual draft).
- **Main Success Scenario**:
  1. UI displays the ERP-familiar monthly grid:
     - **Left sticky columns**: Employee name/pseudonym, `%` *pensum*, monthly target hours, scheduled hours, monthly delta (`+3.5h` / `-2.0h`), and projected cumulative yearly *solde d'heures* (color-coded green/amber/red against the `±10h` rule).
     - **Day columns (`1..31`)**: Weekends shaded distinctly, cantonal public holidays shaded darker, cells displaying ERP shift codes (`MC1`, `V`, `X`, `SDE 9-11`, `POULISTE`), pin icons, and subtle icons showing satisfied vs. unsatisfied soft wishes.
     - **Footer summary rows**: Daily headcount per shift type, total daily staff count, total daily scheduled hours, and green/red coverage-compliance indicators.
  2. Manager can hover any cell to inspect exact shift times, rest hours since previous shift, and wish-satisfaction status, then click **"Finalize / Publish Month"** to lock the period and roll forward ending hour balances into next month.
- **Postconditions**: Schedule is verified, archived, and carry-over balances are updated.

---

### `UC-10` — Export ERP-Compatible Excel (`.xlsx`), CSV, PDF & iCal
- **Primary Actor**: Team Manager (Claire) / SME Owner (Thomas)
- **Linked Needs**: `NEED-01`, `NEED-10`, `NEED-13`
- **Preconditions**: A schedule exists (`UC-09`).
- **Main Success Scenario**:
  1. Manager clicks **"Export"** and selects the output format:
     - **Excel Workbook (`.xlsx`)** *(Primary V1.0.0 ERP bridge)*: Contains (a) a clean ERP-styled monthly matrix sheet using the team's exact custom shift codes (`MC1`, `V`, `X`, `SDE/9/11`, `VIDE`), weekend/holiday shading, and hour-balance columns; (b) a normalized flat-row **Import Sheet** (`Employee_ID, Date, Shift_Code, Start, End, Paid_Hours`) for ERPs supporting tabular import; and (c) a **Pouliste Request List** summarizing open slots.
     - **CSV Export**: Configurable delimiter (`;` / `,`), UTF-8 BOM, and column-mapping profiles (Generic ERP, Bexio, Abacus, Crésus presets on Business tier).
     - **Printable PDF**: Clean landscape monthly poster for the staff breakroom (watermarked on Free tier; branded on paid tiers).
     - **iCal (`.ics`)**: Individual employee calendar feed/file.
  2. Export service generates the file on the Swiss server and streams the download.
  3. Manager either transcribes the clean `.xlsx` into their legacy ERP in minutes or uploads the flat CSV/Excel sheet directly into their ERP import module.
- **Postconditions**: Legacy ERP receives error-free schedule data with zero forced ERP replacement.

---

### `UC-11` — Generate *Pack Direction* & Activate B2B Subscription
- **Primary Actor**: Team Manager (Claire) → Institution Director (Marc) / SME Owner (Thomas)
- **Linked Needs**: `NEED-12`, `NEED-13`, `NEED-14`, `NEED-15`
- **Preconditions**: User has tested the tool (in Sandbox or Free tier) and wishes to upgrade to Starter, Pro, or Business.
- **Main Success Scenario**:
  1. *(Institutional Path)* Manager clicks **"Request Institutional Funding (*Pack Direction*)"**, enters team size and estimated current weekly scheduling hours (e.g., 4h/week), and downloads a 2-page PDF dossier containing:
     - Transparent ROI calculation (e.g., ~12h/month saved ≈ CHF 600/month internal value vs. CHF 39–69/month subscription);
     - Pre-signed Swiss **`nLPD` Art. 9 Data Processing Agreement (DPA)**;
     - Attestation of **100% Swiss ISO 27001 hosting** (Infomaniak Geneva/Zurich, outside US CLOUD Act).
  2. Director (or SME Owner directly) selects a flat-tier plan (`Starter`, `Pro`, or `Business`) and billing cycle (Monthly or Annual with ~2 months free).
  3. Payment is completed via either:
     - **Stripe Switzerland** (Card / TWINT) for instant activation; OR
     - **Swiss QR-Bill** (Annual Business/Institutional plans): System generates a standard ISO 20022 Swiss QR-Invoice PDF with unique QR reference; account activates immediately (with 30-day payment grace) or upon bank reconciliation.
  4. Organization workspace transitions from Anonymous Sandbox to full named tenant with DPA acceptance logged.
- **Postconditions**: Organization is commercially subscribed, tier quotas unlock, and legal compliance artifacts are archived.

---

### `UC-12` — Submit Employee Availability & Preferences *(Pro / Business Tiers)*
- **Primary Actor**: Staff Member (Sophie)
- **Linked Needs**: `NEED-05`, `NEED-16`
- **Preconditions**: Organization is on **Pro** or **Business** tier; Manager has opened the wish-collection window for an upcoming month.
- **Main Success Scenario**:
  1. System sends each staff member an email containing a secure, time-limited, single-purpose **Wish Submission Link** (or lightweight passwordless login).
  2. Employee opens the mobile-friendly monthly calendar view in their browser.
  3. Employee submits hard vacation requests (pending manager approval) and unlimited weighted soft preferences (e.g., *"Prefer not to work Tuesday evening"*, *"Prefer morning shift on May 12"*), plus optional recurring weekly preferences.
  4. System saves submissions directly into the schedule period's request pool and notifies the manager of submission completeness (e.g., *"11/13 staff submitted"*).
  5. Manager reviews/approves hard vacation requests and runs `UC-06`.
- **Alternative Flows**:
  - *A1 — Window Closed*: Once manager locks the submission window, employee sees read-only summary of submitted preferences and must contact manager for late changes.
- **Postconditions**: Manager avoids transcribing paper notes and WhatsApp messages; preferences feed straight into CP-SAT.
