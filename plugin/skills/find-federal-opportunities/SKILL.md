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
4. Present results as: title, agency, close date, award range, a one-line
   fit rationale tied to the org's stated mission/keywords, and the `url`
   as a link so the user can read the full posting and apply.

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
