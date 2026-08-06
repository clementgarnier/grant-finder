---
name: find-state-local-opportunities
description: Find grant opportunities a nonprofit's own state, county, city, and regional/special-district governments fund and award themselves - state agency programs, county health and human services funds, city arts, neighborhood and community development grants, and dedicated-revenue programs. Driven by web search rather than a connector. Use when the user wants public funding close to home, or asks what their state/county/city funds.
---

# Find state and local grant opportunities

Driven by `WebSearch` and `WebFetch`. No connector covers this layer -
there is no grants.gov for the ~90,000 state, county, municipal, and
special-district governments in the US, so each jurisdiction's own site is
the source of truth and every finding has to be read off a live page.

**Scope boundary.** This skill covers money a state or local government
raises and awards on its *own* authority. Federal money that merely passes
*through* a state or local agency belongs to `find-federal-opportunities`
and its pass-through section - start there when the trail begins with a
federal program. The two meet on the same agency websites in practice: when
you are already on one, note both kinds and label which is which (a state
posting that cites an ALN is federal pass-through).

## Goal

Given where the organization is located and where it actually delivers
services, produce a short list of state, county, city, and
regional/special-district grant programs that are open now or on a known
annual cycle, that the org is eligible for, and that align with its
mission - each verified against the awarding body's own page.

## Approach

### 1. Pin down the jurisdiction stack

Start from the org's street address and its **service area** - they are
often not the same, and eligibility usually keys off the service area.
Establish, in order:

1. **City / town / village**, and whether the address is actually inside
   the city limits. An address with a city name in it is frequently in
   *unincorporated* county territory, which means no city programs and a
   different set of county ones.
2. **County**, plus any county-level special bodies (county office of
   education, county health department, behavioral health authority,
   first-5 / children's commission, flood or conservation district).
3. **State**.
4. **Regional and special districts** whose boundaries cover the org:
   council of governments (COG), metropolitan planning organization (MPO),
   air quality management district, transit authority, water/watershed or
   resource conservation district, park district, library district, school
   district, local workforce development board.

Watch for the naming quirks that make a plain "<place> county grants"
search fail: consolidated city-counties (San Francisco, Denver,
Philadelphia, Nashville, Indianapolis, Honolulu) where city and county are
one government, not two funders; Virginia's independent cities, which sit
in no county; Louisiana parishes and Alaska boroughs; New England towns and
Midwest townships, which hold powers that elsewhere sit with the county.

If the org serves several counties or a metro area spanning a state line,
build the stack for each jurisdiction it serves, then say plainly which
ones you searched - covering every one of them is usually not worth the
time, so cap it and be explicit about the cap.

### 2. Know what each level funds

| Level | Typical awarding bodies | Typical programs | Where postings live |
|---|---|---|---|
| State | Agencies (health, human services, education, housing, commerce, natural resources, public safety), state arts agency, state humanities council, the legislature itself | Sector programs, capacity building, capital/facility, planning, legislative earmarks | Central state grant portal; agency "Funding Opportunities"/"NOFA" pages; state register/bulletin |
| County | Health, behavioral health, human/social services, community development, parks, sheriff/probation, board of supervisors or commissioners | Service contracts and subgrants, community benefit funds, discretionary district funds | County grants page; procurement/bid portal; board agendas |
| City | City manager's office, community development, arts commission, parks and rec, sustainability office, neighborhood services, council offices | Neighborhood/mini-grants, arts and culture, events, façade and placemaking, homelessness and youth services, participatory budgeting | City grants page; bid/eProcurement portal; council agendas |
| Regional / special district | COG, MPO, air district, transit authority, water/conservation district, library or park district, workforce board | Transportation and active-mobility, air quality and clean-vehicle, watershed and habitat, literacy and outreach, workforce | The district's own site - rarely indexed anywhere central |

Dedicated revenue streams are the strongest tell that a jurisdiction has
money to grant out, and each has its own searchable vocabulary:
**opioid settlement funds** (every state plus many counties and cities,
with their own advisory councils and application rounds), **cannabis
excise tax** community reinvestment grants, **tobacco MSA** funds,
**transient occupancy / hotel tax** for arts, culture and tourism,
voter-approved **sales tax measures and bond funds** (children's, parks,
libraries, transportation, housing), **lottery and gaming revenue**,
**cap-and-trade / climate** funds, and **utility public-benefit or
franchise fee** funds. Search these by name - they are often awarded
through a program whose title never contains the word "grant".

ARPA State and Local Fiscal Recovery Funds are at the end of their life
(funds had to be obligated by the end of 2024 and spent by the end of
2026). Treat any SLFRF-funded program you find as almost certainly closed,
and check whether the jurisdiction has replaced it with a general-fund
successor rather than reporting the original.

### 3. Search each level

Local governments do not say "grant" consistently. Run both a
funder-first sweep (what does this jurisdiction fund at all?) and a
need-first sweep (who funds this kind of work near here?), using the
vocabulary these bodies actually use: NOFA, NOFO, RFA, RFP, RFQ,
solicitation, "funding opportunity", "notice of funding availability",
"community funding", "mini-grant", "sponsorship", "allocation process".

Funder-first, per jurisdiction:

- `"<city>" grants nonprofit organizations site:<city>.gov`
- `"<county> county" "notice of funding availability" OR "request for proposals" nonprofit`
- `"<state>" grants portal site:*.gov`
- `"<city or county>" "mini-grant" OR "community grant" application`
- `"<county>" opioid settlement funds application` (repeat for the other
  dedicated revenue streams above)

Need-first, across levels:

- `"<state>" "<program area>" grant nonprofit application deadline`
- `"<metro or region>" "<program area>" funding opportunity nonprofit`
- `site:<state-domain>.gov "<program area>" "notice of funding availability"`

Two places worth checking when the grants page is thin or missing:

- **The procurement / bid portal.** Many jurisdictions publish grant
  competitions only alongside contracts, on Bonfire, OpenGov Procurement,
  BidNet, DemandStar, Ionwave, Periscope, or a homegrown eProcurement
  site. Registering as a vendor is often a precondition for applying.
- **Council and board agendas.** A city council or board of supervisors
  approves a grant program's guidelines weeks before the NOFA appears.
  Searching agendas (`"<city>" council agenda "grant program" <program
  area>`) surfaces cycles that have not opened yet, and confirms whether a
  program still exists and at what funding level.

### 4. Verify on the source page

`WebFetch` the actual program page (and its guidelines PDF, which is
usually where the real rules are) and pull:

- Eligibility: org type, 501(c)(3) status, years in operation, budget
  floor or ceiling, and any requirement for a fiscal sponsor.
- **Geographic restriction** - stated two ways that are not the same:
  where the org must be located, and where the funded work and spending
  must occur.
- Deadline, and whether this is a one-off or a recurring annual cycle.
- Award range, total pool size, and expected number of awards.
- Match or cost-share: how much, and whether in-kind counts or it must be
  cash.
- Payment mechanics: **reimbursement vs. advance**, and the invoicing
  cadence.
- Prerequisites that take time to satisfy: vendor/supplier registration,
  state charitable-solicitation registration, business license, insurance
  and indemnification limits, W-9, a UEI if the money is federally
  sourced.
- Whether it is a grant at all, or a services contract dressed as an RFP -
  see "Pitfalls".
- The program contact, which at this level is usually a named person who
  will answer an email.

### 5. Apply the standard checks

Same triage as the other grant skills, with the local specifics that
decide most of these:

- **Mission alignment** - the org's work against the program's stated
  priorities, and against what the jurisdiction has funded in past rounds
  (past awardee lists are usually published and are the honest signal).
- **Eligibility** - every item from step 4, with the geographic
  restriction checked against the org's actual service area rather than
  its mailing address.
- **Capacity to carry the grant** - a reimbursement-only award with a cash
  match is a cash-flow commitment, not just a funding win. For capital or
  construction work, check whether it triggers prevailing-wage,
  competitive-bidding, or public-works rules.
- **Realistic competitiveness** - local pools are small ($1K-$50K is
  common) but often far less competitive than federal or foundation money,
  and incumbents recur. Weigh effort against award size and say so.
- **Timing** - if the cycle is closed, establish when it reopens. A closed
  annual cycle with a known window is a genuinely useful result here, not
  a miss.

### 6. Present results

Lead with the table below, sorted by strength of fit rather than amount,
then per-program notes in prose. Include closed-but-recurring programs,
clearly marked - at this level, knowing that the city's arts cycle opens
each February is often the most actionable thing in the report.

## Output format

Whenever the result is two or more opportunities, lead with a markdown
table, one row per opportunity:

| Funder | Program / opportunity | Amount (or range) | Due date | More info | Level |
|---|---|---|---|---|---|

The five core columns are shared with the other grant skills so lists stay
comparable; `Level` and any `Fit` column go on the end.

- **Funder** - the body that receives the application, named as it calls
  itself (e.g. `Multnomah County Health Department`, not `the county`).
- **Level** - `State`, `County`, `City`, `Regional`, or `Special district`.
  Where the program is state- or locally-administered federal money, mark
  it `State (federal pass-through)` and note the ALN, so it is not double
  counted against the federal section of a combined report.
- **Amount (or range)** - the published per-award range. Use the total
  pool only when no per-award figure is given, and label it as the pool.
  `Not stated` when the source is silent.
- **Due date** - the application deadline. `Rolling` where there is none,
  `Closed - reopens <month/season>` for a recurring cycle that is
  currently shut (state the year the cycle information came from), `Not
  yet open` where the body has announced a program but no dates. Never
  carry a prior year's deadline forward as if it were current.
- **More info** - a markdown link to the program page or its guidelines.
  Fall back to the jurisdiction's grants index or procurement portal only
  when no program page exists, and mark it as such.

A `Fit` column for the one-line rationale is usually worth adding; keep
longer reasoning in prose under the table. Use `-` for genuinely unknown
values rather than blanks or invented ones. A single opportunity doesn't
need a table; write it up in prose with the same facts.

Say explicitly which jurisdictions you searched and which you skipped. A
jurisdiction with no grant programs at all is a finding worth one line -
it stops the user re-searching it later.

## Pitfalls

- **A procurement RFP is not a grant.** Local bodies buy services from
  nonprofits constantly, and those postings sit next to grants on the same
  portal. Contracts are usually reimbursement-only, carry insurance and
  indemnification requirements, and pay for deliverables rather than
  supporting the org's own program. They can still be good money - just
  label them accurately rather than listing them as grants.
- **Stale pages are the norm.** Small jurisdictions leave last year's NOFA
  up indefinitely. Confirm the cycle year on the page itself, and if the
  page shows a deadline that has already passed, treat it as closed and
  find the next cycle rather than reporting the old date.
- **Boundary traps.** City limits vs. "greater metro", unincorporated
  county areas, and special-district boundaries that follow none of the
  above. Verify the org's address falls inside the awarding body's
  boundary before listing a program.
- **Don't double-count consolidated city-counties** as two separate
  funders, and don't report the same program twice because a county and
  its cities each describe it.
- **Match and cash flow sink small orgs.** Flag any required cash match and
  any reimbursement-only structure in the row itself, not just in prose -
  for a small nonprofit these decide whether the grant is worth pursuing.
- **Null results are real results.** Plenty of small cities and rural
  counties run no grant programs at all. Report that rather than stretching
  to present a regional or state program as if it were local.
- **Don't invent a program from a budget line.** A line item in an adopted
  budget or a council resolution is evidence money exists, not evidence
  there is an open application. Say which of the two you found.
- **Relationships matter more here than anywhere else.** Council district
  offices, county commissioners, and program staff at this level often have
  discretionary funds and will discuss fit directly. Where a program has no
  open cycle, a named contact is the useful deliverable.
- **Cross-check against the federal section** before reporting. If the
  state program you found is the subgrant end of a federal pass-through
  chain, it may already be covered by `find-federal-opportunities` -
  dedupe on program name and ALN.
