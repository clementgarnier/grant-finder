---
name: find-federal-opportunities
description: Find open federal (or other public) grant opportunities matching an organization's sector, keywords, or eligibility, using the grants-gov connector. Follows federal money down through pass-through entities - state and local agencies that subgrant block/formula funds - to the subaward competitions a nonprofit can actually apply to. Use when the user wants current open funding opportunities/RFPs rather than historical private funders.
---

# Find federal grant opportunities

Uses the `grants-gov` connector's `graphql` tool (backed live by the
Simpler Grants API - see that server's own instructions) for the federal
layer, plus `WebSearch`/`WebFetch` to follow pass-through money down to
state and local subgrant competitions (see "Pass-through opportunities").

## Goal

Given an organization's sector, keywords, and applicant type (e.g.
"nonprofit", "local government"), find currently open opportunities worth
applying to.

## Approach

1. Query `opportunities` with `filter: {query, applicantType, opportunityStatus: POSTED}`
   so results are things the org can actually apply to right now (skip
   `FORECASTED`/`CLOSED` unless the user explicitly wants a heads-up on
   upcoming or a record of past ones). Then run the same `query` again
   *without* `applicantType` - the nonprofit filter hides exactly the
   state-eligible formula and block grants that pass through to nonprofits,
   which is where much of the sector's federal money actually comes from.
2. Order by `CLOSE_DATE_ASC` when the user cares about urgency, or
   `AWARD_CEILING_DESC` when they want to see the largest opportunities
   first.
3. For the most relevant matches, fetch full detail with `opportunity(id)`
   before presenting - the search result already has enough fields for a
   good summary, but confirm award floor/ceiling and close date are current.
4. Triage each hit for **pass-through**: is the org itself eligible, or does
   this money reach it only as a subaward from a state/local agency? See
   "Pass-through opportunities" below. Do this before writing anything up -
   a posting the org can't apply to directly is a lead, not a result.
5. For every pass-through hit that matters, work through steps 3-5 of
   "Pass-through opportunities" to reach the actual subgrant competition,
   and report *that* as the opportunity.
6. Present results as a table (see "Output format" below). Every row
   carries a one-line fit rationale in the required `Fit` column, tied to
   the org's stated mission/keywords.

## Pass-through opportunities

Most federal grant dollars never go straight to a nonprofit. Congress
appropriates them to a federal agency, which awards them by formula to a
**pass-through entity** (usually a state agency), which then runs its own
competition to **subaward** them to local **subrecipients**. The
grants.gov-side posting is the top of that chain, not the thing a nonprofit
applies to. Following the chain down is the whole point of this step.

### 1. Recognize the pass-through case

Signals, strongest first:

- `applicantTypes` contains no nonprofit code
  (`nonprofits_non_higher_education_with_501c3` and its non-501(c)(3)
  variants), no `unrestricted`, and no higher-ed code - only governmental
  ones (`state_governments`,
  `county_governments`, `city_or_township_governments`,
  `special_district_governments`,
  `federally_recognized_native_american_tribal_governments`,
  `public_and_indian_housing_authorities`).
- `applicantTypes` is just `["other"]`. This is what several formula
  programs use for "the single agency the governor designated" - always
  read the posting rather than assuming it means "anyone".
- Title or description contains: `formula`, `block grant`, `allotment`,
  `allocation`, `State Plan`, `State Administering Agency`, `pass-through`,
  `subaward`, `subgrant`, `subrecipient`, `units of local government`.
- The description says the recipient must distribute funds, run a
  competition, or subaward some percentage.

Program families that almost always work this way: CDBG, HOME, ESG and
Continuum of Care (HUD); CSBG, SSBG, LIHEAP, CCDF, MCH Title V, SAPT/CMHS
block grants (HHS); Older Americans Act Titles III/VII (ACL); VOCA, VAWA
STOP, Byrne JAG (DOJ); WIOA (DOL); Title I and IDEA (ED); LSTA (IMLS);
state arts agency and state humanities council partnership funds (NEA/NEH);
EPA Section 319 nonpoint source; USDA CACFP, SNAP-Ed and EFSP.

### 2. Vocabulary to search with

The state layer does not use the word "grant" the way grants.gov does.
Searching for the federal program name plus these terms is what surfaces
the real opportunity:

| Federal side | State/local side |
|---|---|
| prime recipient, pass-through entity (PTE) | grantor, administering agency |
| subaward, subrecipient | subgrant, subgrantee, subrecipient award |
| Notice of Funding Opportunity (NOFO) | NOFA, RFA, RFP, solicitation, "funding announcement" |
| formula / block grant | allocation, allotment, set-aside, State Plan |
| Assistance Listing Number (ALN, ex-CFDA) | same - states cite the ALN in their own postings |
| award | regrant / re-grant (common in arts and humanities) |

Useful designated-agency names to search for by archetype: State
Administering Agency (SAA, used by DOJ and FEMA), State Education Agency
(SEA) and Local Education Agency (LEA), single/sole State agency, State
Unit on Aging and its Area Agencies on Aging (AAA), Community Action
Agency, Continuum of Care lead agency, Local Workforce Development Board,
State Library Administrative Agency, state arts agency, state humanities
council, council of governments / regional planning commission.

### 3. Identify which agency holds the money in this state

1. Get the program's **ALN** (five digits, `XX.XXX`). The connector does not
   carry it - read it off the posting via `additionalInfoUrl` or the
   `url` detail page. The ALN is stable year over year; opportunity numbers
   are not, so use the ALN as the join key everywhere below.
2. `WebFetch` the SAM.gov assistance listing for that ALN
   (`https://sam.gov/assistance-listings`, or search
   `"<ALN>" site:sam.gov`) for who is eligible to receive it, who the
   ultimate beneficiaries are, and whether the listing itself describes a
   pass-through.
3. Find the actual prime recipient in the user's state via USAspending -
   `WebFetch` `https://www.usaspending.gov/search` results or search
   `usaspending "<ALN>" "<state>"`. This names the exact agency, and its
   sub-award tab shows who that agency has already subgranted to - a strong
   peer signal for whether an org like this one is a plausible subrecipient.
4. Failing that, search directly:
   - `"<state>" "<program name>" state administering agency`
   - `site:<state-domain>.gov "<program name>" subgrant`
   - `"<state>" "<ALN>" notice of funding availability`

### 4. Scrape that agency for the live subgrant competition

1. Check the state's central grant portal first, where one exists - search
   `"<state>" grants portal site:*.gov`. California
   (`grants.ca.gov`), New York (`grantsmanagement.ny.gov`) and Minnesota
   (`mn.gov/admin/citizen/grants`) are examples; most states have one, but
   coverage is uneven and agency-level pages are often more current.
2. Then the administering agency's own site: its `Grants`, `Funding
   Opportunities`, `NOFA`, or `Doing Business` section.
3. `WebFetch` and pull: open RFA/NOFA and its deadline, whether nonprofits
   are eligible, the award range, the match/cost-share requirement, the
   application portal link, and the program contact.
4. Two more places worth checking when the agency site is thin: the
   program's **State Plan** or (for HUD money) the **Consolidated Plan /
   Annual Action Plan**, which set out the subrecipient competition
   schedule; and the state legislature's or budget office's appropriation
   tables, which list federal pass-through by agency with the ALN attached.

### 5. Go one hop further where the state is not the end of the chain

Some money passes through twice. CDBG goes to entitlement cities and
counties as well as to the state; Older Americans Act money goes state ->
Area Agency on Aging; CSBG goes state -> Community Action Agency; WIOA goes
state -> Local Workforce Development Board; homelessness money goes HUD ->
Continuum of Care lead agency. When the state agency's page says it
allocates to these bodies rather than running an open competition, identify
the one covering the org's county and check its site the same way.

Stop after two hops. If there's still no open competition to point at, say
so and report where the chain ended - that is a real finding, not a
failure.

## Output format

Whenever the result is two or more opportunities, lead with a markdown
table, one row per opportunity:

| Funder | Program / opportunity | Amount (or range) | Due date | More info | Fit |
|---|---|---|---|---|---|

- **Funder** - `agencyName` for a direct federal posting; for a pass-through
  find, the **administering state or local agency**, since that is who the
  org actually applies to.
- **Program / opportunity** - the opportunity `title`. For a pass-through
  find, the state program's own name, with the federal source and ALN noted
  after it, e.g. `Community Services Subgrant (via CSBG, ALN 93.569)`.
- **Amount (or range)** - `awardFloor`-`awardCeiling` when both are given,
  a single figure when only one is, `Not stated` when neither is. For a
  pass-through find, use the *subgrant* range the state publishes, never the
  federal award ceiling - that is the whole state's allocation, not what a
  subrecipient gets.
- **Due date** - `closeDate`. Use `Rolling` where the posting has no close
  date, and flag anything closing within ~2 weeks so the user sees the
  time pressure. For a pass-through find, the state competition's deadline;
  where the state has not opened its cycle yet, use `Not yet open` plus the
  expected timing if the agency states one - never the federal NOFO's date.
- **More info** - a markdown link on the opportunity `url`, so the user can
  read the full posting and apply. For a pass-through find, link the state
  agency's own RFA/NOFA page, falling back to its grants index page marked
  as such.

- **Fit** - required, one line per row, tying this opportunity to the org's
  own mission, keywords, or eligibility. Not a restatement of what the
  program funds: say why *this* org is or isn't a plausible applicant.
  Where the fit is weak, say that in the cell ("only if the org runs a
  workforce program - it doesn't today") rather than dropping the row or
  writing something bland. Keep longer reasoning in prose under the table.

Use `-` for genuinely unknown values rather than blanks or invented ones -
but never in `Fit`, which is a judgement you can always make. A single
opportunity doesn't need a table; write it up in prose with the same facts,
fit rationale included.

Where a search returned both kinds, keep directly-applicable federal
postings and pass-through subgrant competitions in one table but add a
`Level` column (`Federal` / `State` / `Local`), between `More info` and
`Fit` - they compete for the same grant-writing hours and belong on one
list, but the org needs to see at a glance which door it is knocking on.

## Example queries

Directly-applicable opportunities:

```graphql
{
  opportunities(filter: {query: "food security",
                          applicantType: "nonprofits_non_higher_education_with_501c3",
                          opportunityStatus: POSTED},
                orderBy: CLOSE_DATE_ASC, limit: 10) {
    opportunityId title agencyName closeDate awardFloor awardCeiling url
  }
}
```

The pass-through sweep - same terms, no applicant filter, pulling the
fields the triage in step 4 needs (`applicantTypes` for the eligibility
signal, `additionalInfoUrl` for the agency page carrying the ALN):

```graphql
{
  opportunities(filter: {query: "food security", opportunityStatus: POSTED},
                orderBy: CLOSE_DATE_ASC, limit: 25) {
    title agencyName applicantTypes description closeDate url additionalInfoUrl
  }
}
```

## Pitfalls

- `query` terms are ANDed by the upstream API (every term must match) - if
  a search comes back thin, try a shorter or differently-phrased query
  rather than piling on more keywords.
- `funding_category` and `applicant_type` take the Simpler Grants API's own
  snake_case codes (e.g. `"education"`,
  `"nonprofits_non_higher_education_with_501c3"`), not free text - check
  the field descriptions via introspection if unsure of the exact code.
- Never present a state-eligible-only federal posting as something the org
  can apply to. Either follow it down to the subgrant competition or label
  it plainly as a lead ("this money reaches you through X, whose cycle
  opens in Y").
- The federal close date and the state subgrant deadline are unrelated. The
  state usually opens its competition months *after* the federal award
  lands, so a closed federal posting often means the state opportunity is
  imminent rather than gone. Don't drop `CLOSED` federal formula postings
  from the pass-through analysis for that reason.
- Not every pass-through entity subgrants. Some states run the program with
  their own staff, or allocate by formula to fixed bodies with no open
  competition. Report that as the answer rather than reaching for a
  weaker prospect.
- USAspending's first-tier subaward data is self-reported by prime
  recipients and is patchy - use it to confirm an agency and its grantee
  mix, not to conclude that an agency makes no subawards.
- Subrecipients carry real federal obligations under 2 CFR 200 (SAM.gov UEI
  registration, single audit above the annual threshold, the pass-through
  entity's own monitoring). Flag this for a small org - it can be the
  deciding factor on whether a subgrant is worth pursuing.
- Follow only the pass-through chains that fit the org's mission and
  geography. Chasing every state-eligible posting turns one search into
  dozens of site scrapes; cap it at the handful of strongest hits and say
  which ones you followed.
