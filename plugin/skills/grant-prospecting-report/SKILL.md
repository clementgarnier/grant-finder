---
name: grant-prospecting-report
description: Produce one combined grant-prospecting report for an organization - private foundation grant opportunities (from IRS 990 history plus live funder-website checks) plus open public opportunities at the federal, state, county and city levels (from grants-gov and the jurisdictions' own sites) - in a single pass. Use for a broad "find grant opportunities for this org" ask, not for a narrowly scoped funder or opportunity lookup.
---

# Combined grant-prospecting report

Uses both connectors: `irs990-filings-grants` and `grants-gov`, plus
`WebSearch`/`WebFetch` for the private-foundation half and for the whole
state/local layer. This is the flagship workflow the other four skills feed
into - reach for this one by default when the user's ask is broad ("find
grants for us", "who could fund this project"); reach for
`find-private-foundation-opportunities`, `find-federal-opportunities`,
`find-state-local-opportunities`, or `funder-due-diligence` directly when
the ask is already narrowly scoped.

## Goal

Given a description of an organization (mission, sector/NTEE code,
geography, applicant type), produce one report with two sections:
private-foundation grant opportunities and open public-funding
opportunities across all levels of government, each with a fit rationale,
so the user has a single prioritized list to work from.

## Approach

1. Extract from the org description: a short keyword phrase, an NTEE major
   code if inferable, state/region, and applicant type (usually
   "Nonprofits"). Pin down geography precisely enough to search the local
   layer - city (and whether the address is inside the city limits),
   county, state, and the service area if it differs from the address.
2. Run the `find-private-foundation-opportunities` steps against
   `irs990-filings-grants` (similar orgs -> their historical funders) and
   then `WebSearch`/`WebFetch` those funders' sites to get 5-10 private
   funder opportunities that are plausibly open now, each with a fit
   rationale and a link to the opportunity.
3. Run the `find-federal-opportunities` steps against `grants-gov` to get
   currently-open opportunities matching the same profile - including that
   skill's pass-through step, which follows state-eligible-only federal
   postings down to the state or local agency's own subgrant competition.
   For a typical nonprofit this is where most of the usable public money
   is, so don't stop at the federal layer.
4. Run the `find-state-local-opportunities` steps over the jurisdiction
   stack from step 1 - state agency programs, county health/human services
   and community funds, city arts, neighborhood and community development
   grants, and any regional or special-district body covering the org.
   This is money those governments raise and award themselves, so it does
   not appear in `grants-gov` at all and only turns up by searching each
   jurisdiction's own site. Include closed-but-recurring local cycles,
   marked as such - the reopening date is often the most actionable line in
   the report.
5. Merge into one report - two sections, each led by its own table in the
   shared format below, each sorted by strength of fit rather than by
   amount:
   - **Private foundation opportunities** - plus funder EIN and fit notes
     (mission/eligibility/historical openness to new grantees)
   - **Public opportunities** - direct federal postings, pass-through
     subgrant competitions, and state/local own-source programs together,
     with a `Level` column
     (`Federal`/`State`/`County`/`City`/`Regional`/`Special district`) and a
     one-line fit rationale. The funder is the body the org applies to: the
     federal `agencyName` for a direct posting, the administering state or
     local agency for a subgrant, the jurisdiction's own department for a
     state/local program.
6. Dedupe the public section before writing it up. Steps 3 and 4 converge
   on the same state and county agency websites from opposite directions,
   so the same program can surface twice - once as the bottom of a federal
   pass-through chain and once as a state posting. Keep one row, mark it
   `State (federal pass-through)` with the ALN, and don't count it twice.
7. `irs990-filings-grants` gives the historical signal (most recent
   processed IRS Form 990 filings) that points at *which* foundations to
   check; `WebSearch`/`WebFetch` confirm what's actually open now on each
   funder's own site. `grants-gov` is backed live by the Simpler Grants
   API. Don't present step-2's historical funder list as if it were open
   opportunities without the live website check.

## Output format

Both sections use the same table shape, so the two lists stay comparable at
a glance. One row per opportunity:

| Funder | Program / opportunity | Amount (or range) | Due date | More info |
|---|---|---|---|---|

- **Funder** - the foundation's name (private section), or the body that
  receives the application in the public section: `agencyName` for a direct
  federal posting, the administering state/local agency for a pass-through
  subgrant, the jurisdiction's own named department for a state or local
  program (e.g. `Multnomah County Health Department`, not `the county`).
- **Amount (or range)** - the funder's own stated range, or
  `awardFloor`-`awardCeiling` for federal postings. For a private funder
  with no published range, fall back to the typical range from their 990
  history and label it (e.g. "$25K-$100K (historical)"). For a state/local
  program, use the published per-award range; fall back to the total pool
  only when no per-award figure is given, and label it as the pool.
- **Due date** - the application/LOI deadline or `closeDate`. Use `Rolling`
  for no fixed deadline, `Invitation only` where the funder doesn't take
  unsolicited requests, `Not yet open` for a pass-through cycle the state
  hasn't announced yet, `Closed - reopens <month/season>` for a recurring
  state/local cycle that is currently shut, `Not stated` when the source is
  silent. Never guess a date, reuse a past cycle's deadline as if it were
  current, or put a federal NOFO's close date on a state subgrant row.
- **More info** - a markdown link to the specific grant/application page or
  the grants.gov posting `url`. Fall back to a funder's homepage only when
  no grants page was found, and mark it as such.

Section-specific columns go on the end (EIN and fit notes for private,
`Level` and fit rationale for public) - keep the five core columns
identical across both. Use `-` for genuinely unknown values, and keep longer per-opportunity
reasoning in prose under each table.

## Pitfalls

- Don't skip straight to querying - if the org's sector/geography isn't
  clear from what the user gave you, ask before guessing an NTEE code or
  state filter that could silently narrow out good prospects.
- Keep the two sections clearly separated (private history vs. open
  opportunities) - they answer different questions ("who might fund us"
  vs. "what can we apply to right now") and shouldn't be blended into one
  undifferentiated list.
- A public section made entirely of federal postings the org can't apply to
  directly is a half-finished report. If the `grants-gov` hits are mostly
  state-eligible-only formula and block grants, that's the signal to run
  the pass-through chain, not to hand back a thin list.
- A public section with nothing below the federal level is the other half
  of the same failure. `grants-gov` has no visibility into what a city,
  county, or state funds out of its own revenue, so an empty state/local
  layer means step 4 wasn't run - not that the money isn't there. For a
  small, place-based org it's usually the most winnable money in the
  report.
- Say which jurisdictions the local layer covered and which were skipped.
  Without that, the user can't tell a searched-and-empty county from one
  that was never looked at.
- All three sources converge on the same move - the database says who *has*
  the money, the funder's, agency's, or jurisdiction's own website says
  what's *open*. Budget the web-scraping effort across the whole report
  rather than spending it all on foundations.
