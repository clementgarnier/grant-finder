---
name: grant-prospecting-report
description: Produce one combined grant-prospecting report for an organization - private foundation grant opportunities (from IRS 990 history plus live funder-website checks) plus open public/federal opportunities (from grants-gov) - in a single pass. Use for a broad "find grant opportunities for this org" ask, not for a narrowly scoped funder or opportunity lookup.
---

# Combined grant-prospecting report

Uses both connectors: `irs990-filings-grants` and `grants-gov`, plus
`WebSearch`/`WebFetch` for the private-foundation half. This is the
flagship workflow the other three skills feed into - reach for this one by
default when the user's ask is broad ("find grants for us", "who could fund
this project"); reach for `find-private-foundation-opportunities`,
`find-federal-opportunities`, or `funder-due-diligence` directly when the
ask is already narrowly scoped.

## Goal

Given a description of an organization (mission, sector/NTEE code,
geography, applicant type), produce one report with two sections:
private-foundation grant opportunities and open public-funding
opportunities, each with a fit rationale, so the user has a single
prioritized list to work from.

## Approach

1. Extract from the org description: a short keyword phrase, an NTEE major
   code if inferable, state/region, and applicant type (usually
   "Nonprofits").
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
4. Merge into one report - two sections, each led by its own table in the
   shared format below, each sorted by strength of fit rather than by
   amount:
   - **Private foundation opportunities** - plus funder EIN and fit notes
     (mission/eligibility/historical openness to new grantees)
   - **Public opportunities** - direct federal postings and pass-through
     subgrant competitions together, with a `Level` column
     (`Federal`/`State`/`Local`) and a one-line fit rationale. The funder is
     the body the org applies to: the federal `agencyName` for a direct
     posting, the administering state or local agency for a subgrant.
5. `irs990-filings-grants` gives the historical signal (most recent
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
  subgrant.
- **Amount (or range)** - the funder's own stated range, or
  `awardFloor`-`awardCeiling` for federal postings. For a private funder
  with no published range, fall back to the typical range from their 990
  history and label it (e.g. "$25K-$100K (historical)").
- **Due date** - the application/LOI deadline or `closeDate`. Use `Rolling`
  for no fixed deadline, `Invitation only` where the funder doesn't take
  unsolicited requests, `Not yet open` for a pass-through cycle the state
  hasn't announced yet, `Not stated` when the source is silent. Never guess
  a date, reuse a past cycle's deadline as if it were current, or put a
  federal NOFO's close date on a state subgrant row.
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
- Both halves converge on the same move - the database says who *has* the
  money, the funder's or agency's own website says what's *open*. Budget
  the web-scraping effort across both sections rather than spending it all
  on foundations.
