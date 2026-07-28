---
name: find-federal-opportunities
description: Find open federal (or other public) grant opportunities matching an organization's sector, keywords, or eligibility, using the grants-gov connector. Use when the user wants current open funding opportunities/RFPs rather than historical private funders.
---

# Find federal grant opportunities

Uses only the `grants-gov` connector's `graphql` tool (backed live by the
Simpler Grants API - see that server's own instructions).

## Goal

Given an organization's sector, keywords, and applicant type (e.g.
"nonprofit", "local government"), find currently open opportunities worth
applying to.

## Approach

1. Query `opportunities` with `filter: {query, applicantType, opportunityStatus: POSTED}`
   so results are things the org can actually apply to right now (skip
   `FORECASTED`/`CLOSED` unless the user explicitly wants a heads-up on
   upcoming or a record of past ones).
2. Order by `CLOSE_DATE_ASC` when the user cares about urgency, or
   `AWARD_CEILING_DESC` when they want to see the largest opportunities
   first.
3. For the most relevant matches, fetch full detail with `opportunity(id)`
   before presenting - the search result already has enough fields for a
   good summary, but confirm award floor/ceiling and close date are current.
4. Present results as a table (see "Output format" below), with a one-line
   fit rationale per row tied to the org's stated mission/keywords.

## Output format

Whenever the result is two or more opportunities, lead with a markdown
table, one row per opportunity:

| Funder | Program / opportunity | Amount (or range) | Due date | More info |
|---|---|---|---|---|

- **Funder** - `agencyName` (the agency is the funder here).
- **Program / opportunity** - the opportunity `title`.
- **Amount (or range)** - `awardFloor`-`awardCeiling` when both are given,
  a single figure when only one is, `Not stated` when neither is.
- **Due date** - `closeDate`. Use `Rolling` where the posting has no close
  date, and flag anything closing within ~2 weeks so the user sees the
  time pressure.
- **More info** - a markdown link on the opportunity `url`, so the user can
  read the full posting and apply.

A `Fit` column for the one-line rationale is usually worth adding; keep
longer reasoning in prose under the table. Use `-` for genuinely unknown
values rather than blanks or invented ones. A single opportunity doesn't
need a table; write it up in prose with the same facts.

## Example query

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

## Pitfalls

- `query` terms are ANDed by the upstream API (every term must match) - if
  a search comes back thin, try a shorter or differently-phrased query
  rather than piling on more keywords.
- `funding_category` and `applicant_type` take the Simpler Grants API's own
  snake_case codes (e.g. `"education"`,
  `"nonprofits_non_higher_education_with_501c3"`), not free text - check
  the field descriptions via introspection if unsure of the exact code.
