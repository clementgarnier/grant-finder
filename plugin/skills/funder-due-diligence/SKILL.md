---
name: funder-due-diligence
description: Build a profile of one specific funder (foundation or grantmaking nonprofit) - their mission, financials, and full grant-making history - before applying to them. Use when the user names a specific funder by name or EIN, not when searching broadly for prospects.
---

# Funder due diligence

Uses only the `irs990-filings-grants` connector's `graphql` tool.

## Goal

Given one funder's name or EIN, produce a profile useful for deciding
whether and how to approach them: what they fund, how much, and who
they've funded historically.

## Approach

1. If only a name is known, find the EIN first via
   `filings(filter: {keyword: "<name>"}, limit: 5)` and confirm the right
   org by state/mission before proceeding - names are not unique and
   keyword search can return near-matches.
2. Pull their latest filing directly: `filing(ein: "...")` for mission,
   total revenue/assets, and total grants paid.
3. Pull their full grant history: `grants(filter: {grantorEin: "..."},
   orderBy: TOTAL_AMT_DESC, limit: 50)` to see recipients, amounts, and
   purposes - this is the core of the profile.
4. Summarize: typical grant size (range, not just the max), recurring
   themes in `purpose`/`recipientName`, and geographic concentration of
   recipients (`recipientState`). Flag anything that suggests they don't
   fund the requester's kind of work (e.g. exclusively funds a different
   sector or only funds outside the requester's state).

## Example query

```graphql
{
  filing(ein: "941156621") { orgName missionDesc totalRevenue totalGrantsPaid }
  grants(filter: {grantorEin: "941156621"}, orderBy: TOTAL_AMT_DESC, limit: 30) {
    recipientName recipientState purpose totalAmt taxYr
  }
}
```

## Pitfalls

- Always prefer `grantorEin`/`ein` over `keyword` once the EIN is known -
  keyword search is a fallback for the initial name lookup only.
- A funder's most recent filing may lag a year or two behind the current
  date (990s are filed annually, often months after the tax year ends) -
  note the `taxYr` on the data you're presenting.
