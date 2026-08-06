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
geography, applicant type) and agreement on which funding layers are worth
searching, produce one report with two sections: private-foundation grant
opportunities and open public-funding opportunities across the chosen
levels of government, each with a fit rationale, so the user has a single
prioritized list to work from.

## Approach

1. **Agree the scope before searching anything.** Four layers are
   available and each costs real work - the private layer is a connector
   query plus a website check per candidate funder; the federal, state and
   local layers are mostly web fetches, and the local one multiplies with
   every jurisdiction in the stack. Running all four for an org that only
   wants one is slow and buries the answer. Ask as a single multi-select
   question (`AskUserQuestion` where available), not four separate ones:
   - **Private foundations** - historical 990 evidence, then live funder
     sites. Widest reach, least tied to geography.
   - **Federal** - direct `grants-gov` postings, plus the pass-through
     chains down to state subgrant competitions.
   - **State** - state agency programs and dedicated-revenue funds.
   - **County, city and regional** - local own-source money. Smallest
     awards, usually the least competitive, and the most work per hit.

   Recommend a default in the question rather than making the user choose
   blind. A small place-based org is usually best served by foundations
   plus state and local; a national, research, or infrastructure-heavy org
   by foundations plus federal. Say which you'd start with and why.

   Skip the question when the ask already carries its own scope ("what
   federal money can we get?", "we've worked the foundations, look at
   public funding") - that is the answer; act on it. Likewise run all four
   when the user asks for the full picture or says "everything".

   Ask this together with any org details still missing from step 2, so
   the user is interrupted once rather than twice.

   If the answer comes back as a single layer, use that layer's dedicated
   skill instead - this skill's value is the merge, and it has nothing to
   merge from one source.

   Run only the selected layers, and don't half-run an excluded one to
   "check" it. Step 3 is the private layer, step 4 the federal layer, and
   step 5 covers both state and county/city/regional - run the part that
   was selected.
2. Extract from the org description: a short keyword phrase, an NTEE major
   code if inferable, state/region, and applicant type (usually
   "Nonprofits"). Pin down geography precisely enough to search the local
   layer - city (and whether the address is inside the city limits),
   county, state, and the service area if it differs from the address.
   Geography only needs this much precision if step 1 selected the state or
   local layers.
3. Run the `find-private-foundation-opportunities` steps against
   `irs990-filings-grants` (similar orgs -> their historical funders) and
   then `WebSearch`/`WebFetch` those funders' sites to get 5-10 private
   funder opportunities that are plausibly open now, each with a fit
   rationale and a link to the opportunity.
4. Run the `find-federal-opportunities` steps against `grants-gov` to get
   currently-open opportunities matching the same profile - including that
   skill's pass-through step, which follows state-eligible-only federal
   postings down to the state or local agency's own subgrant competition.
   For a typical nonprofit this is where most of the usable public money
   is, so don't stop at the federal layer.
5. Run the `find-state-local-opportunities` steps over the jurisdiction
   stack from step 2 - state agency programs, county health/human services
   and community funds, city arts, neighborhood and community development
   grants, and any regional or special-district body covering the org.
   This is money those governments raise and award themselves, so it does
   not appear in `grants-gov` at all and only turns up by searching each
   jurisdiction's own site. Include closed-but-recurring local cycles,
   marked as such - the reopening date is often the most actionable line in
   the report. Where step 1 selected only one of state or local, hold to
   that - the two sit on adjacent pages of the same agency sites, so the
   excluded one is easy to drift into.
6. Merge into one report - two sections, each led by its own table in the
   shared format below, each sorted by strength of fit rather than by
   amount. Drop a section entirely if step 1 excluded everything that
   would have filled it, and note in a line what wasn't searched:
   - **Private foundation opportunities** - plus funder EIN, and a `Fit`
     entry covering mission alignment, eligibility, and historical
     openness to new grantees
   - **Public opportunities** - direct federal postings, pass-through
     subgrant competitions, and state/local own-source programs together,
     with a `Level` column
     (`Federal`/`State`/`County`/`City`/`Regional`/`Special district`). The
     funder is the body the org applies to: the
     federal `agencyName` for a direct posting, the administering state or
     local agency for a subgrant, the jurisdiction's own department for a
     state/local program.
7. Dedupe the public section before writing it up. Steps 4 and 5 converge
   on the same state and county agency websites from opposite directions,
   so the same program can surface twice - once as the bottom of a federal
   pass-through chain and once as a state posting. Keep one row, mark it
   `State (federal pass-through)` with the ALN, and don't count it twice.
8. `irs990-filings-grants` gives the historical signal (most recent
   processed IRS Form 990 filings) that points at *which* foundations to
   check; `WebSearch`/`WebFetch` confirm what's actually open now on each
   funder's own site. `grants-gov` is backed live by the Simpler Grants
   API. Don't present step-3's historical funder list as if it were open
   opportunities without the live website check.

## Output format

Both sections use the same table shape, so the two lists stay comparable at
a glance. One row per opportunity:

| Funder | Program / opportunity | Amount (or range) | Due date | More info | Fit |
|---|---|---|---|---|---|

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
- **Fit** - required in both sections, one line per row, and the column the
  user actually reads the report by. It carries a different judgement in
  each: for a private funder, mission alignment plus openness to new
  grantees; for a public opportunity, eligibility and whether the org can
  carry the award (match, reimbursement, subrecipient obligations). Say
  why *this* org is or isn't a plausible applicant - never restate what the
  program funds. Weak fits stay in the table with the weakness named.

Section-specific columns go between `More info` and `Fit` (EIN for private,
`Level` for public) - keep the five core columns identical across both, and
`Fit` last in both. Use `-` for genuinely unknown values, though never in
`Fit`, which is a judgement you can always make. Keep longer
per-opportunity reasoning in prose under each table.

## Pitfalls

- Don't skip straight to querying - if the org's sector/geography isn't
  clear from what the user gave you, ask before guessing an NTEE code or
  state filter that could silently narrow out good prospects. Fold that
  into the step-1 scope question; two rounds of questions before any
  results is worse than one.
- Ask the scope question once, then commit. Re-confirming a layer
  mid-search, or quietly adding one the user declined, defeats the point of
  asking. If a search turns up a strong reason to widen ("nothing federal
  fits, but the county funds exactly this"), finish what was agreed and
  raise it at the end as a recommendation.
- Keep the two sections clearly separated (private history vs. open
  opportunities) - they answer different questions ("who might fund us"
  vs. "what can we apply to right now") and shouldn't be blended into one
  undifferentiated list.
- A public section made entirely of federal postings the org can't apply to
  directly is a half-finished report. If the `grants-gov` hits are mostly
  state-eligible-only formula and block grants, that's the signal to run
  the pass-through chain, not to hand back a thin list.
- A public section with nothing below the federal level, where step 1
  selected those layers, is the other half of the same failure.
  `grants-gov` has no visibility into what a city, county, or state funds
  out of its own revenue, so an empty state/local layer means step 5 wasn't
  run - not that the money isn't there. For a small, place-based org it's
  usually the most winnable money in the report.
- Never let a scoped-out layer look like a searched-and-empty one. Say
  which layers the report covers and which the user excluded, and within
  the local layer, which jurisdictions were searched and which were
  skipped.
- All three sources converge on the same move - the database says who *has*
  the money, the funder's, agency's, or jurisdiction's own website says
  what's *open*. Budget the web-scraping effort across the whole report
  rather than spending it all on foundations.
