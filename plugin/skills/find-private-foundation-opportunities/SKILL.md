---
name: find-private-foundation-opportunities
description: Find private-foundation grant opportunities a nonprofit can actually apply to now (or soon) - by identifying similar organizations' historical funders via IRS Form 990 data, then checking those funders' own websites for live application windows and fit. Use when the user wants actionable grants to pursue for an org; for a deep profile of one named funder, use `funder-due-diligence` instead.
---

# Find private foundation grants

Uses the `irs990-filings-grants` connector's `graphql` tool for the
historical/peer analysis (steps 1-3), and `WebSearch`/`WebFetch` for the
live opportunity check (step 4). The IRS data only tells you who has
funded whom in the past, not what's open for applications right now, so
step 4 is what turns a list of past funders into a list of things worth
applying to.

## Goal

Given an organization (by EIN, name, or a vague description), produce a
short list of private-foundation grant opportunities that are (a) plausibly
open to new applicants right now or in the near future, (b) aligned with
the org's mission and eligible for it, and (c) backed by evidence the
funder actually takes on grantees like this one - not just a list of the
biggest foundations in the sector.

## Approach

### 1. Identify the organization

- Ask the user for the org's EIN (preferred, unambiguous) or name. If they
  can only describe it loosely ("a small youth literacy nonprofit in
  Ohio"), that's fine - skip the lookup and carry the description straight
  into step 2 as the keyword/NTEE/state signal.
- EIN known: `filing(ein: "...")` for `orgName`, `missionDesc`,
  `nteeMajorCode`, `state`, `totalRevenue`.
- Only a name known: `filings(filter: {keyword: "<name>"}, limit: 5)` and
  confirm the right org by state/mission before proceeding.

### 2. Find similar organizations

There's no built-in "similar orgs" query, so approximate it: same
`nteeMajorCode`, a comparable revenue band, and (optionally) the same
state or region.

```graphql
{
  filings(filter: {nteeMajorCode: "B", state: "OH", minTotalRevenue: 200000},
          orderBy: RELEVANCE_DESC, limit: 20) {
    ein orgName state totalRevenue missionDesc
  }
}
```

- Drop `state` if the org's funders are likely to be regional/national
  (common outside hyper-local causes) - a same-state filter is only a
  useful similarity signal, not a requirement.
- There's no max-revenue filter; skim results and discard peers wildly
  larger than the target org (a $50M hospital system isn't a useful peer
  for a $300K community nonprofit).
- Exclude the org itself by `ein`.

### 3. Identify funders of those similar orgs

For each peer's `ein`, find who has funded them:

```graphql
{
  grants(filter: {recipientEin: "<peer-ein>"}, orderBy: TOTAL_AMT_DESC, limit: 20) {
    grantorEin grantorName totalAmt taxYr purpose
  }
}
```

- `GrantFilter` only supports `recipientEin`, not `recipientName` - resolve
  a peer's EIN first (step 2 already gives you this) before you can look
  up its funders.
- Aggregate `grantorEin` across all peers. A funder that shows up for
  several peers is a much stronger signal than one that funded a single
  peer once.
- Check each candidate funder is actually a foundation/grantmaker, not a
  government pass-through or one-off corporate donor: pull
  `filing(ein: grantorEin)` and confirm `formType` is `990PF` (or a `990`
  with a real, recurring `totalGrantsPaid`).

### 4. Scrape funders' websites for live grant opportunities

The 990 data is historical and often a year or more stale - it has no
concept of an open application window. For each top candidate funder (by
frequency/amount from step 3):

1. `WebSearch` for `"<funder name>" grant application guidelines` or
   `"<funder name>" foundation apply` to find their official grants/apply
   page (not a directory listing or old news article).
2. `WebFetch` that page, asking specifically for: currently open
   programs/cycles, deadlines, whether they accept unsolicited
   applications or LOIs vs. invitation-only, eligibility requirements, and
   the direct URL to the opportunity or application page.
3. If a foundation's site says invitation-only, has no open call, or
   hasn't been updated in years, say so plainly rather than presenting it
   as a live opportunity.

### 5. Assess fit

For each funder/opportunity that clears step 4:

- **Mission alignment** - compare the funder's stated priorities (from the
  scraped page, plus the `purpose`/recipient types seen in step 3) against
  the org's mission.
- **Eligibility** - org type (501(c)(3) status, budget size, geographic
  restrictions) against what the site requires.
- **Historical openness to new grantees** - pull that funder's grants
  across a few tax years (`grants(filter: {grantorEin}, orderBy:
  TAX_YR_DESC, limit: 50)`) and check recipient turnover. If it's
  essentially the same handful of names every year, flag this funder as a
  weak prospect for a new applicant even if their total giving is large.

### 6. Present results

Lead with the summary table (see "Output format" below), sorted by strength
of fit rather than dollar amount, then add any per-funder narrative below
it.

- Call out clearly, per row, if a funder is invitation-only, hasn't
  historically added new grantees, or has no visible open cycle - don't
  quietly drop these, since the user may still want to make a relationship
  overture even without an open RFP.

## Output format

Whenever the result is two or more grant opportunities, lead with a
markdown table. One row per opportunity (not per funder - a funder running
several programs gets several rows):

| Funder | Program / opportunity | Amount (or range) | Due date | More info | Fit |
|---|---|---|---|---|---|

- **Funder** - the grantmaking organization's name.
- **Amount (or range)** - the funder's own stated award range when the site
  gives one. Otherwise fall back to the typical range from their 990 grant
  history and label it as such (e.g. "$25K-$100K (historical)"). Never
  present a single historical grant as if it were an advertised amount.
- **Due date** - the application/LOI deadline. Use `Rolling` for no fixed
  deadline, `Invitation only` where the funder doesn't accept unsolicited
  requests, and `Not stated` when the site simply doesn't say. Don't guess
  a date or carry forward a past cycle's deadline as if it were current.
- **More info** - a markdown link to the funder's own grant/application
  page. Fall back to the funder's homepage only if step 4 found no grants
  page, and mark it (e.g. `[Homepage](...)`) so the user knows the specific
  page wasn't found.

- **Fit** - required, one line per row, carrying the step-5 assessment:
  mission alignment, eligibility, and openness to new grantees. Where a
  funder is invitation-only or has funded the same handful of names for
  years, that goes here ("large giving, but no new grantees since 2019 -
  relationship play, not an application"). Never leave it as a restatement
  of the funder's programs. Keep longer per-funder reasoning in prose under
  the table.

Add further columns only when they earn their place. Use `-` for anything
genuinely unknown rather than leaving a cell blank or inventing a value -
but never in `Fit`, which is a judgement you can always make. A single
opportunity doesn't need a table; write it up in prose with the same facts,
fit rationale included.

## Pitfalls

- Don't skip step 4 and present step-3 output (past funders) as if it were
  a list of open opportunities. A funder having funded similar orgs in the
  past says nothing about whether they're accepting applications today.
- `keyword` filters are ANDed and drop terms under 3 characters - keep
  phrases short and substantive when working from a vague org description.
- No max-revenue filter exists on `filings` - always sanity-check that
  "similar" orgs in step 2 are actually comparable in size, not just the
  same sector/state.
- Foundation websites vary wildly in quality; some publish nothing about
  current cycles at all. Treat an empty/stale result from step 4 as
  signal ("likely not soliciting"), not as a reason to fall back to
  presenting stale 990 data as current.
- A high historical `totalAmt` from a funder doesn't mean they're a good
  prospect for *this* org - always weigh it against the recipient-turnover
  check in step 5.
