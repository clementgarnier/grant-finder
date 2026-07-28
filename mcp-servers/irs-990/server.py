#!/usr/bin/env python3
"""GraphQL-backed MCP server (streamable-http transport) for the irs990 grants database.

Runs inside the mcp-server Docker container; connects to MySQL as the
read-only irs990_ro user. Clients no longer send SQL: they send a GraphQL
query against the schema below, which only exposes the filings/grants
tables through typed fields and filters. All filter values are bound as
query parameters - never string-interpolated - so there is no SQL
injection surface, and result sets are always limit-capped.

Exposes:
  - the MCP tool `graphql(query, variables)`, for MCP clients (agents).
  - a plain GraphQL endpoint at /graphql (with GraphiQL) for ad-hoc
    troubleshooting. Not meant to be exposed past localhost/the docker
    network - see docker-compose.yml, which only binds 127.0.0.1.
"""
import asyncio
import enum
import os
import re
from collections import defaultdict
from typing import NewType, Optional

import pymysql
import pymysql.cursors
import strawberry
import uvicorn
from strawberry.dataloader import DataLoader
from strawberry.asgi import GraphQL
from mcp.server.fastmcp import FastMCP

MYSQL_HOST = os.environ.get("MYSQL_HOST", "mysql")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]
MYSQL_RO_USER = os.environ["MYSQL_RO_USER"]
MYSQL_RO_PASSWORD = os.environ["MYSQL_RO_PASSWORD"]

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def connect():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_RO_USER,
        password=MYSQL_RO_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


# GraphQL's built-in Int is 32-bit; dollar amounts in this data (e.g. large
# foundations' total_amt/total_revenue) routinely exceed that.
BigInt = NewType("BigInt", int)
_BIGINT_SCALAR = strawberry.scalar(
    name="BigInt",
    description="A 64-bit integer, serialized as a JSON number.",
    serialize=lambda v: v,
    parse_value=lambda v: int(v),
)


async def _run_query(sql: str, params: list) -> list[dict]:
    def _query():
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    return await asyncio.to_thread(_query)


# ---------------------------------------------------------------------------
# GraphQL types
# ---------------------------------------------------------------------------

@strawberry.type
class Filing:
    ein: Optional[str]
    form_type: Optional[str]
    tax_yr: Optional[int]
    tax_period_end: Optional[str]
    org_name: Optional[str]
    org_name2: Optional[str]
    address_line1: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    phone: Optional[str]
    principal_officer_name: Optional[str]
    mission_desc: Optional[str]
    website_url: Optional[str]
    formation_year: Optional[int]
    gross_receipts: Optional[BigInt]
    employee_count: Optional[int]
    tax_exempt_subsection: Optional[str]
    total_revenue: Optional[BigInt]
    total_expenses: Optional[BigInt]
    total_assets_eoy: Optional[BigInt]
    contributions_grants_received: Optional[BigInt]
    total_grants_paid: Optional[BigInt]
    ntee_code: Optional[str]
    ntee_major_code: Optional[str]
    ntee_major_desc: Optional[str]
    source_file: strawberry.Private[str]

    @strawberry.field(description="Grants paid out under this specific filing (Schedule I / Part XV).")
    async def grants(self, info: strawberry.types.Info) -> list["Grant"]:
        return await info.context["grants_by_source_file"].load(self.source_file)


@strawberry.type
class Grant:
    id: int
    grantor_ein: Optional[str]
    grantor_name: Optional[str]
    tax_yr: Optional[int]
    recipient_name: Optional[str]
    recipient_ein: Optional[str]
    recipient_city: Optional[str]
    recipient_state: Optional[str]
    recipient_zip: Optional[str]
    purpose: Optional[str]
    cash_amt: Optional[BigInt]
    noncash_amt: Optional[BigInt]
    total_amt: Optional[BigInt]
    source_schedule: Optional[str]
    source_file: strawberry.Private[str]

    @strawberry.field(description="The filing this grant was reported on.")
    async def filing(self, info: strawberry.types.Info) -> Optional[Filing]:
        return await info.context["filing_by_source_file"].load(self.source_file)


FILING_COLUMNS = [
    "ein", "form_type", "tax_yr", "tax_period_end", "org_name", "org_name2",
    "address_line1", "city", "state", "zip", "phone", "principal_officer_name",
    "mission_desc", "website_url", "formation_year", "gross_receipts", "employee_count",
    "tax_exempt_subsection", "total_revenue", "total_expenses", "total_assets_eoy",
    "contributions_grants_received", "total_grants_paid", "source_file",
    "ntee_code", "ntee_major_code", "ntee_major_desc",
]

GRANT_COLUMNS = [
    "id", "grantor_ein", "grantor_name", "tax_yr", "recipient_name", "recipient_ein",
    "recipient_city", "recipient_state", "recipient_zip", "purpose",
    "cash_amt", "noncash_amt", "total_amt", "source_schedule", "source_file",
]


def _row_to_filing(row: dict) -> Filing:
    return Filing(**{c: row.get(c) for c in FILING_COLUMNS})


def _row_to_grant(row: dict) -> Grant:
    return Grant(**{c: row.get(c) for c in GRANT_COLUMNS})


# ---------------------------------------------------------------------------
# Dataloaders (batch the Filing<->Grant relations to avoid N+1 queries)
# ---------------------------------------------------------------------------

async def _batch_filings_by_source_file(keys: list[str]) -> list[Optional[Filing]]:
    placeholders = ", ".join(["%s"] * len(keys))
    rows = await _run_query(
        f"SELECT {', '.join(FILING_COLUMNS)} FROM filings WHERE source_file IN ({placeholders})",
        keys,
    )
    by_key = {row["source_file"]: _row_to_filing(row) for row in rows}
    return [by_key.get(k) for k in keys]


async def _batch_grants_by_source_file(keys: list[str]) -> list[list[Grant]]:
    placeholders = ", ".join(["%s"] * len(keys))
    rows = await _run_query(
        f"SELECT {', '.join(GRANT_COLUMNS)} FROM grants WHERE source_file IN ({placeholders}) LIMIT %s",
        [*keys, MAX_LIMIT * max(len(keys), 1)],
    )
    by_key = defaultdict(list)
    for row in rows:
        by_key[row["source_file"]].append(_row_to_grant(row))
    return [by_key.get(k, []) for k in keys]


def make_context() -> dict:
    """Fresh per-request dataloaders, so batching is scoped to one GraphQL execution."""
    return {
        "filing_by_source_file": DataLoader(load_fn=_batch_filings_by_source_file),
        "grants_by_source_file": DataLoader(load_fn=_batch_grants_by_source_file),
    }


# ---------------------------------------------------------------------------
# Filters / ordering (whitelisted columns only - never client-supplied SQL)
# ---------------------------------------------------------------------------

# MySQL boolean-mode fulltext operators. Stripped from user input so a
# keyword can't be turned into unintended search syntax (e.g. a bare "-"
# excluding a term, or an unbalanced quote).
_BOOLEAN_MODE_OPERATORS = re.compile(r'[+\-()<>~*"@]')

# Matches InnoDB's default innodb_ft_min_token_size: words shorter than this
# are never indexed, so requiring one (+term) would make the whole boolean
# query unsatisfiable. Drop them instead - see the `keyword` field docs.
_FT_MIN_TOKEN_SIZE = 3


def _boolean_mode_query(keyword: str) -> Optional[str]:
    """Build an AGAINST(... IN BOOLEAN MODE) query string that requires every
    (indexable) term in `keyword` to be present (AND, not the OR-of-tokens
    that NATURAL LANGUAGE MODE does), with an extra unanchored phrase clause
    so exact/near-exact phrase matches score higher for relevance ordering.
    Returns None if nothing searchable remains after sanitizing and dropping
    too-short terms, in which case callers should skip the keyword clause
    entirely.
    """
    all_terms = _BOOLEAN_MODE_OPERATORS.sub(" ", keyword).split()
    terms = [t for t in all_terms if len(t) >= _FT_MIN_TOKEN_SIZE]
    if not terms:
        return None
    required = " ".join(f"+{t}" for t in terms)
    if len(terms) == 1:
        return required
    return f'{required} "{" ".join(terms)}"'


@strawberry.input
class FilingFilter:
    ein: Optional[str] = None
    state: Optional[str] = None
    form_type: Optional[str] = None
    tax_yr: Optional[int] = None
    ntee_major_code: Optional[str] = None
    min_total_revenue: Optional[BigInt] = None
    min_total_grants_paid: Optional[BigInt] = None
    keyword: Optional[str] = strawberry.field(
        default=None,
        description="Full-text search over org_name, mission_desc, ntee_major_desc. "
        "All whitespace-separated terms must be present (AND, not OR) - a row "
        "must match every term to be returned. Terms under 3 characters are "
        "dropped (MySQL fulltext's minimum indexed token length). Use "
        "RELEVANCE_DESC ordering to rank exact/near-exact phrase matches first.",
    )


@strawberry.enum
class FilingOrderBy(enum.Enum):
    TAX_YR_DESC = "tax_yr_desc"
    TAX_YR_ASC = "tax_yr_asc"
    TOTAL_REVENUE_DESC = "total_revenue_desc"
    TOTAL_GRANTS_PAID_DESC = "total_grants_paid_desc"
    ORG_NAME_ASC = "org_name_asc"
    RELEVANCE_DESC = "relevance_desc"


_FILING_ORDER_SQL = {
    FilingOrderBy.TAX_YR_DESC: "tax_yr DESC",
    FilingOrderBy.TAX_YR_ASC: "tax_yr ASC",
    FilingOrderBy.TOTAL_REVENUE_DESC: "total_revenue DESC",
    FilingOrderBy.TOTAL_GRANTS_PAID_DESC: "total_grants_paid DESC",
    FilingOrderBy.ORG_NAME_ASC: "org_name ASC",
}


_FILING_FT_EXPR = "MATCH(org_name, mission_desc, ntee_major_desc) AGAINST (%s IN BOOLEAN MODE)"


def _build_filing_where(f: Optional[FilingFilter]) -> tuple[str, list, Optional[str]]:
    """Returns (where_sql, params, keyword_query). keyword_query is the
    sanitized boolean-mode query string (or None if no keyword filter was
    given), for reuse in relevance ordering."""
    clauses, params = [], []
    keyword_query = None
    if f:
        if f.ein:
            clauses.append("ein = %s"); params.append(f.ein)
        if f.state:
            clauses.append("state = %s"); params.append(f.state)
        if f.form_type:
            clauses.append("form_type = %s"); params.append(f.form_type)
        if f.tax_yr is not None:
            clauses.append("tax_yr = %s"); params.append(f.tax_yr)
        if f.ntee_major_code:
            clauses.append("ntee_major_code = %s"); params.append(f.ntee_major_code)
        if f.min_total_revenue is not None:
            clauses.append("total_revenue >= %s"); params.append(f.min_total_revenue)
        if f.min_total_grants_paid is not None:
            clauses.append("total_grants_paid >= %s"); params.append(f.min_total_grants_paid)
        if f.keyword:
            keyword_query = _boolean_mode_query(f.keyword)
            if keyword_query:
                clauses.append(_FILING_FT_EXPR)
                params.append(keyword_query)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params, keyword_query


def _resolve_filing_order(
    order_by: Optional["FilingOrderBy"], keyword_query: Optional[str]
) -> tuple[str, list]:
    """Returns (order_sql, extra_params). Defaults to relevance ordering when
    a keyword filter is present and the caller didn't request a specific
    order; RELEVANCE_DESC without a keyword falls back to the default."""
    resolved = order_by or (FilingOrderBy.RELEVANCE_DESC if keyword_query else FilingOrderBy.TAX_YR_DESC)
    if resolved == FilingOrderBy.RELEVANCE_DESC:
        if keyword_query:
            return f"{_FILING_FT_EXPR} DESC", [keyword_query]
        resolved = FilingOrderBy.TAX_YR_DESC
    return _FILING_ORDER_SQL[resolved], []


@strawberry.input
class GrantFilter:
    grantor_ein: Optional[str] = None
    recipient_ein: Optional[str] = None
    recipient_state: Optional[str] = None
    tax_yr: Optional[int] = None
    min_total_amt: Optional[BigInt] = None
    keyword: Optional[str] = strawberry.field(
        default=None,
        description="Full-text search over recipient_name, purpose. All "
        "whitespace-separated terms must be present (AND, not OR) - a row "
        "must match every term to be returned. Terms under 3 characters are "
        "dropped (MySQL fulltext's minimum indexed token length). Use "
        "RELEVANCE_DESC ordering to rank exact/near-exact phrase matches "
        "first. If you already know the recipient's EIN, prefer the "
        "recipientEin filter - it's an exact, reliable match with no "
        "tokenization quirks.",
    )


@strawberry.enum
class GrantOrderBy(enum.Enum):
    TOTAL_AMT_DESC = "total_amt_desc"
    TAX_YR_DESC = "tax_yr_desc"
    RECIPIENT_NAME_ASC = "recipient_name_asc"
    RELEVANCE_DESC = "relevance_desc"


_GRANT_ORDER_SQL = {
    GrantOrderBy.TOTAL_AMT_DESC: "total_amt DESC",
    GrantOrderBy.TAX_YR_DESC: "tax_yr DESC",
    GrantOrderBy.RECIPIENT_NAME_ASC: "recipient_name ASC",
}


_GRANT_FT_EXPR = "MATCH(recipient_name, purpose) AGAINST (%s IN BOOLEAN MODE)"


def _build_grant_where(f: Optional[GrantFilter]) -> tuple[str, list, Optional[str]]:
    """Returns (where_sql, params, keyword_query); see _build_filing_where."""
    clauses, params = [], []
    keyword_query = None
    if f:
        if f.grantor_ein:
            clauses.append("grantor_ein = %s"); params.append(f.grantor_ein)
        if f.recipient_ein:
            clauses.append("recipient_ein = %s"); params.append(f.recipient_ein)
        if f.recipient_state:
            clauses.append("recipient_state = %s"); params.append(f.recipient_state)
        if f.tax_yr is not None:
            clauses.append("tax_yr = %s"); params.append(f.tax_yr)
        if f.min_total_amt is not None:
            clauses.append("total_amt >= %s"); params.append(f.min_total_amt)
        if f.keyword:
            keyword_query = _boolean_mode_query(f.keyword)
            if keyword_query:
                clauses.append(_GRANT_FT_EXPR)
                params.append(keyword_query)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params, keyword_query


def _resolve_grant_order(
    order_by: Optional["GrantOrderBy"], keyword_query: Optional[str]
) -> tuple[str, list]:
    """See _resolve_filing_order."""
    resolved = order_by or (GrantOrderBy.RELEVANCE_DESC if keyword_query else GrantOrderBy.TOTAL_AMT_DESC)
    if resolved == GrantOrderBy.RELEVANCE_DESC:
        if keyword_query:
            return f"{_GRANT_FT_EXPR} DESC", [keyword_query]
        resolved = GrantOrderBy.TOTAL_AMT_DESC
    return _GRANT_ORDER_SQL[resolved], []


# ---------------------------------------------------------------------------
# Query root
# ---------------------------------------------------------------------------

@strawberry.type
class Query:
    @strawberry.field(
        description="Look up one organization's filing by EIN (its IRS Employer "
        "Identification Number). If taxYr is omitted, returns its most recent filing."
    )
    async def filing(self, ein: str, tax_yr: Optional[int] = None) -> Optional[Filing]:
        clauses, params = ["ein = %s"], [ein]
        if tax_yr is not None:
            clauses.append("tax_yr = %s")
            params.append(tax_yr)
        rows = await _run_query(
            f"SELECT {', '.join(FILING_COLUMNS)} FROM filings WHERE {' AND '.join(clauses)} "
            f"ORDER BY tax_yr DESC LIMIT 1",
            params,
        )
        return _row_to_filing(rows[0]) if rows else None

    @strawberry.field
    async def filings(
        self,
        filter: Optional[FilingFilter] = None,
        order_by: Optional[FilingOrderBy] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Filing]:
        where_sql, params, keyword_query = _build_filing_where(filter)
        order_sql, order_params = _resolve_filing_order(order_by, keyword_query)
        params = [*params, *order_params, _clamp_limit(limit), max(0, offset)]
        rows = await _run_query(
            f"SELECT {', '.join(FILING_COLUMNS)} FROM filings {where_sql} "
            f"ORDER BY {order_sql} LIMIT %s OFFSET %s",
            params,
        )
        return [_row_to_filing(r) for r in rows]

    @strawberry.field
    async def grant(self, id: int) -> Optional[Grant]:
        rows = await _run_query(
            f"SELECT {', '.join(GRANT_COLUMNS)} FROM grants WHERE id = %s LIMIT 1",
            [id],
        )
        return _row_to_grant(rows[0]) if rows else None

    @strawberry.field
    async def grants(
        self,
        filter: Optional[GrantFilter] = None,
        order_by: Optional[GrantOrderBy] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Grant]:
        where_sql, params, keyword_query = _build_grant_where(filter)
        order_sql, order_params = _resolve_grant_order(order_by, keyword_query)
        params = [*params, *order_params, _clamp_limit(limit), max(0, offset)]
        rows = await _run_query(
            f"SELECT {', '.join(GRANT_COLUMNS)} FROM grants {where_sql} "
            f"ORDER BY {order_sql} LIMIT %s OFFSET %s",
            params,
        )
        return [_row_to_grant(r) for r in rows]


schema = strawberry.Schema(
    query=Query,
    config=strawberry.schema.config.StrawberryConfig(scalar_map={BigInt: _BIGINT_SCALAR}),
)


# ---------------------------------------------------------------------------
# MCP server (tool-calling interface) + troubleshooting-only /graphql mount
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "irs990-filings-grants",
    instructions="""\
IRS Form 990 nonprofit filings and grants database (read-only, GraphQL).

WHAT IS FORM 990? It's the annual information return that virtually every
U.S. tax-exempt organization - public charities, private foundations,
hospitals, universities, trade associations, community groups, etc. - must
file with the IRS to keep its tax-exempt status. Unlike an ordinary tax
return, Form 990 (and its variants 990-EZ for smaller orgs, 990-PF for
private foundations) is a *public* disclosure: it reports the org's
mission, address, officers, a financial summary (revenue, expenses,
assets, contributions received), and - most usefully for research - the
full list of grants it paid out to other organizations and individuals
that year (Schedule I on Form 990; Part XV on Form 990-PF).

WHAT'S IN THIS SERVER: two record types, joined 1:1 per return:
  - Filing: one per tax return - org identity/address/mission, tax year,
    financial summary, and NTEE category (the IRS's activity/sector
    classification for exempt organizations).
  - Grant: one per grant disbursement reported on that filing's Schedule I
    / Part XV - recipient, amount, purpose.

WHAT IT'S FOR: researching nonprofits and the philanthropic funders behind
them. Typical questions this can answer: which foundations fund a given
cause or region; who has a specific funder given to historically (grant
prospecting and due diligence before applying, or building a fundraising
target list); what is an organization's mission and financial profile by
name, EIN, or state; how do grantmaking patterns compare across an NTEE
sector (e.g. education vs. health).

The only tool is `graphql`. It runs a read-only, filtered query against
this data - result sizes are capped, so don't try to fetch entire tables.
Read the `graphql` tool's own description for the full field list,
available filters, and example queries before writing your first
query.""",
)


@mcp.tool(title="Search IRS 990 data")
async def graphql(query: str, variables: Optional[dict] = None) -> dict:
    """Query the IRS Form 990 nonprofit filings & grants database via GraphQL.

    Form 990 is the public annual return that U.S. tax-exempt nonprofits
    and foundations file with the IRS; it discloses their mission,
    finances, and every grant they paid out. Use this tool to research
    nonprofits and grantmakers: find funders for a cause/region, see a
    funder's historical grant recipients, look up an org's mission and
    financial profile, or analyze giving patterns by sector - see this
    server's `instructions` for the full picture.

    Every list field is capped at 500 rows (default 50), so do not try to
    fetch entire tables - use the filters below to narrow your request.
    Pass a standard GraphQL document as `query` and, optionally, a dict of
    GraphQL variables as `variables` (for `$var`-style placeholders). The
    return value is `{"data": ..., "errors": ...}`, mirroring a normal
    GraphQL response.

    SCHEMA SUMMARY (fields are camelCase in GraphQL; use standard
    introspection, e.g. `{ __schema { types { name } } }`, for the
    authoritative/current version):

      type Filing {
        ein, formType ("990"|"990EZ"|"990PF"), taxYr, taxPeriodEnd,
        orgName, orgName2, addressLine1, city, state, zip, phone,
        principalOfficerName, missionDesc, websiteUrl,
        formationYear, employeeCount,                    # Int; 990 only, null on 990EZ/990PF
        grossReceipts,                                    # BigInt (USD); 990/990EZ only
        taxExemptSubsection,          # self-reported, e.g. "501(c)(3)", "4947(a)(1)"
        totalRevenue, totalExpenses, totalAssetsEoy,
        contributionsGrantsReceived, totalGrantsPaid,   # all BigInt (USD)
        nteeCode, nteeMajorCode, nteeMajorDesc,          # activity category
        grants: [Grant!]!                                # this filing's grants
      }

      type Grant {
        id, grantorEin, grantorName, taxYr,
        recipientName, recipientEin, recipientCity, recipientState,
        recipientZip, purpose,
        cashAmt, noncashAmt, totalAmt,                   # all BigInt (USD)
        sourceSchedule,                                  # "990_schedule_i"|"990pf_part_xv"
        filing: Filing                                   # the filing this grant is from
      }

      type Query {
        filing(ein: String!, taxYr: Int): Filing   # taxYr omitted -> most recent
        filings(filter: FilingFilter, orderBy: FilingOrderBy,
                limit: Int = 50, offset: Int = 0): [Filing!]!
        grant(id: Int!): Grant
        grants(filter: GrantFilter, orderBy: GrantOrderBy,
               limit: Int = 50, offset: Int = 0): [Grant!]!
      }

      input FilingFilter { ein, state, formType, taxYr, nteeMajorCode,
        minTotalRevenue, minTotalGrantsPaid,
        keyword }  # full-text search over orgName + missionDesc + nteeMajorDesc

      input GrantFilter { grantorEin, recipientEin, recipientState, taxYr,
        minTotalAmt,
        keyword }  # full-text search over recipientName + purpose

      enum FilingOrderBy { TAX_YR_DESC TAX_YR_ASC TOTAL_REVENUE_DESC
                           TOTAL_GRANTS_PAID_DESC ORG_NAME_ASC RELEVANCE_DESC }
      enum GrantOrderBy  { TOTAL_AMT_DESC TAX_YR_DESC RECIPIENT_NAME_ASC RELEVANCE_DESC }

    Note: nested `Filing.grants` and `Grant.filing` take no arguments (no
    per-field limit/filter) - filter/order/limit only at the top-level
    `filings`/`grants` query fields.

    KEYWORD SEARCH SEMANTICS: `keyword` on either filter requires EVERY
    whitespace-separated term to be present in the matched columns - it is
    an AND of terms, not an OR, so adding more words narrows results (e.g.
    `keyword: "SF-Marin Food Bank"` only returns rows containing "SF" and
    "Marin" and "Food" and "Bank", not rows matching any one of them).
    Caveats: (1) terms under 3 characters are dropped entirely (MySQL
    fulltext's minimum indexed token length), so very short abbreviations
    won't narrow anything - prefer a fuller name/word when possible; (2)
    if you already know an exact identifier (an EIN), use the dedicated
    `ein`/`grantorEin`/`recipientEin` filters instead of `keyword` - they're
    exact matches with none of fulltext's quirks. `orderBy` defaults to
    `RELEVANCE_DESC` automatically whenever `keyword` is set (ranking
    exact/near-exact phrase matches first) unless you explicitly choose a
    different order; with no `keyword`, it defaults to `TAX_YR_DESC` for
    filings and `TOTAL_AMT_DESC` for grants.

    EXAMPLES

    1. Foundations funding literacy programs in California, with a few of
       each one's grants:
         { filings(filter: {state: "CA", keyword: "literacy"}, limit: 5) {
             orgName taxYr missionDesc totalGrantsPaid
             grants { recipientName purpose totalAmt }
         } }

    2. Largest grants a specific funder (by EIN) has made, for prospect
       research / due diligence before applying to them:
         { grants(filter: {grantorEin: "123456789"},
                  orderBy: TOTAL_AMT_DESC, limit: 20) {
             recipientName recipientState purpose totalAmt taxYr
         } }

    3. Health-sector (NTEE major code "E") foundations with at least $1M
       in grants paid, using variables:
         query($minGrants: BigInt!) {
           filings(filter: {nteeMajorCode: "E", minTotalGrantsPaid: $minGrants},
                   orderBy: TOTAL_GRANTS_PAID_DESC, limit: 10) {
             orgName state totalGrantsPaid totalAssetsEoy
           }
         }
         # variables: {"minGrants": 1000000}

    4. Look up one organization's most recent filing directly by EIN:
         { filing(ein: "123456789") {
             orgName missionDesc taxYr totalRevenue totalGrantsPaid
         } }

    5. Who has funded a specific organization historically, when you know
       its EIN - far more reliable than name/keyword matching:
         { grants(filter: {recipientEin: "941156621"},
                  orderBy: TOTAL_AMT_DESC, limit: 20) {
             grantorName totalAmt taxYr purpose
         } }
    """
    result = await schema.execute(query, variable_values=variables, context_value=make_context())
    return {
        "data": result.data,
        "errors": [str(e) for e in result.errors] if result.errors else None,
    }


def main():
    app = mcp.streamable_http_app()
    # Troubleshooting only: not meant to be reachable outside localhost/the
    # docker network. docker-compose.yml binds this service to 127.0.0.1.
    app.mount("/graphql", GraphQL(schema, graphql_ide="graphiql"))
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
