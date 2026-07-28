#!/usr/bin/env python3
"""GraphQL-backed MCP server (streamable-http transport) for grant opportunities.

Wraps the Simpler Grants API (https://api.simpler.grants.gov) - the newer
replacement for legacy grants.gov search - behind the same kind of typed
GraphQL schema the `irs990-filings-grants` connector puts in front of its
MySQL data, so both connectors present one consistent `graphql(query,
variables)` tool to callers instead of two different tool-calling styles.

Requires a Simpler Grants API key (see "Getting an API key" at
https://wiki.simpler.grants.gov/product/api) passed as SIMPLER_GRANTS_API_KEY.
That key lives on the deployed server, not handed out to individual plugin
installers - see mcp.config.release.json.
"""
import enum
import os
from typing import NewType, Optional

import httpx
import strawberry
import uvicorn
from strawberry.asgi import GraphQL
from mcp.server.fastmcp import FastMCP

BigInt = NewType("BigInt", int)
_BIGINT_SCALAR = strawberry.scalar(
    name="BigInt",
    description="A 64-bit integer, serialized as a JSON number.",
    serialize=lambda v: v,
    parse_value=lambda v: int(v),
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


# ---------------------------------------------------------------------------
# Simpler Grants API client
# ---------------------------------------------------------------------------

_API_BASE_URL = os.environ.get("SIMPLER_GRANTS_API_BASE_URL", "https://api.simpler.grants.gov")
_API_KEY = os.environ["SIMPLER_GRANTS_API_KEY"]

_http_client = httpx.AsyncClient(
    base_url=_API_BASE_URL,
    headers={"X-API-Key": _API_KEY, "Content-Type": "application/json"},
    timeout=20.0,
)


async def _api_get(path: str) -> Optional[dict]:
    resp = await _http_client.get(path)
    if resp.status_code == 404:
        return None
    if resp.is_error:
        raise RuntimeError(f"Simpler Grants API error {resp.status_code} on GET {path}: {resp.text[:500]}")
    return resp.json()


async def _api_post(path: str, json_body: dict) -> dict:
    resp = await _http_client.post(path, json=json_body)
    if resp.is_error:
        raise RuntimeError(f"Simpler Grants API error {resp.status_code} on POST {path}: {resp.text[:500]}")
    return resp.json()


# ---------------------------------------------------------------------------
# GraphQL types
# ---------------------------------------------------------------------------

@strawberry.enum
class OpportunityStatus(enum.Enum):
    FORECASTED = "forecasted"
    POSTED = "posted"
    CLOSED = "closed"
    ARCHIVED = "archived"


_SIMPLER_GRANTS_UI_BASE_URL = os.environ.get(
    "SIMPLER_GRANTS_UI_BASE_URL", "https://simpler.grants.gov"
)


@strawberry.type
class Opportunity:
    opportunity_id: str
    opportunity_number: str
    title: str
    agency_code: str
    agency_name: str
    description: str
    opportunity_status: OpportunityStatus
    award_ceiling: Optional[BigInt]
    award_floor: Optional[BigInt]
    post_date: Optional[str]
    close_date: Optional[str]
    funding_category: list[str]
    funding_instrument: list[str]
    applicant_types: list[str]
    url: str = strawberry.field(
        description="Link to this opportunity's detail/apply page on simpler.grants.gov."
    )
    additional_info_url: Optional[str] = strawberry.field(
        description="Agency-provided link with more information about this opportunity, "
        "if one was given (may point to an application portal, agency site, etc.)."
    )


def _row_to_opportunity(row: dict) -> Opportunity:
    summary = row.get("summary") or {}
    return Opportunity(
        opportunity_id=row["opportunity_id"],
        opportunity_number=row.get("opportunity_number") or "",
        title=row.get("opportunity_title") or "",
        agency_code=row.get("agency_code") or "",
        agency_name=row.get("agency_name") or "",
        description=summary.get("summary_description") or "",
        opportunity_status=OpportunityStatus(row["opportunity_status"]),
        award_ceiling=summary.get("award_ceiling"),
        award_floor=summary.get("award_floor"),
        post_date=summary.get("post_date"),
        close_date=summary.get("close_date"),
        funding_category=summary.get("funding_categories") or [],
        funding_instrument=summary.get("funding_instruments") or [],
        applicant_types=summary.get("applicant_types") or [],
        url=f"{_SIMPLER_GRANTS_UI_BASE_URL}/opportunity/{row['opportunity_id']}",
        additional_info_url=summary.get("additional_info_url") or None,
    )


# ---------------------------------------------------------------------------
# Filters / ordering
# ---------------------------------------------------------------------------

@strawberry.input
class OpportunityFilter:
    query: Optional[str] = strawberry.field(
        default=None,
        description="Free-text search over title and description, ANDed "
        "across search terms (every term must match).",
    )
    agency_code: Optional[str] = None
    opportunity_status: Optional[OpportunityStatus] = None
    funding_category: Optional[str] = strawberry.field(
        default=None,
        description='One of the Simpler Grants API funding-category codes, '
        'e.g. "education", "health", "environment", "arts", '
        '"food_and_nutrition", "community_development". See the API\'s '
        "FundingCategory enum for the full list.",
    )
    applicant_type: Optional[str] = strawberry.field(
        default=None,
        description='One of the Simpler Grants API applicant-type codes, '
        'e.g. "nonprofits_non_higher_education_with_501c3", '
        '"state_governments", "individuals", "small_businesses", '
        '"unrestricted". See the API\'s ApplicantType enum for the full list.',
    )
    min_award_ceiling: Optional[BigInt] = None


@strawberry.enum
class OpportunityOrderBy(enum.Enum):
    CLOSE_DATE_ASC = "close_date_asc"
    POST_DATE_DESC = "post_date_desc"
    AWARD_CEILING_DESC = "award_ceiling_desc"


_ORDER_BY_API = {
    OpportunityOrderBy.CLOSE_DATE_ASC: ("close_date", "ascending"),
    OpportunityOrderBy.POST_DATE_DESC: ("post_date", "descending"),
    OpportunityOrderBy.AWARD_CEILING_DESC: ("award_ceiling", "descending"),
}


def _build_search_body(
    f: Optional[OpportunityFilter],
    order_by: Optional[OpportunityOrderBy],
    limit: int,
    offset: int,
) -> dict:
    limit = _clamp_limit(limit)
    # The upstream API paginates by page number, not row offset. Assumes
    # `offset` is a multiple of `limit` (the normal incremental-paging
    # pattern of offset=0, limit, 2*limit, ...); other offsets get rounded
    # down to the nearest page boundary.
    page_offset = max(0, offset) // limit + 1

    sort_order = None
    if order_by is not None:
        field, direction = _ORDER_BY_API[order_by]
        sort_order = [{"order_by": field, "sort_direction": direction}]
    elif f and f.query:
        sort_order = [{"order_by": "relevancy", "sort_direction": "descending"}]

    pagination = {"page_offset": page_offset, "page_size": limit}
    if sort_order:
        pagination["sort_order"] = sort_order

    body: dict = {"pagination": pagination}
    if f is None:
        return body

    if f.query:
        body["query"] = f.query

    filters: dict = {}
    if f.agency_code:
        filters["agency"] = {"one_of": [f.agency_code]}
    if f.opportunity_status:
        filters["opportunity_status"] = {"one_of": [f.opportunity_status.value]}
    if f.funding_category:
        filters["funding_category"] = {"one_of": [f.funding_category]}
    if f.applicant_type:
        filters["applicant_type"] = {"one_of": [f.applicant_type]}
    if f.min_award_ceiling is not None:
        filters["award_ceiling"] = {"min": f.min_award_ceiling}
    if filters:
        body["filters"] = filters
    return body


# ---------------------------------------------------------------------------
# Query root
# ---------------------------------------------------------------------------

@strawberry.type
class Query:
    @strawberry.field(description="Look up a single opportunity by its opportunity ID.")
    async def opportunity(self, id: str) -> Optional[Opportunity]:
        result = await _api_get(f"/v1/opportunities/{id}")
        return _row_to_opportunity(result["data"]) if result else None

    @strawberry.field
    async def opportunities(
        self,
        filter: Optional[OpportunityFilter] = None,
        order_by: Optional[OpportunityOrderBy] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Opportunity]:
        body = _build_search_body(filter, order_by, limit, offset)
        result = await _api_post("/v1/opportunities/search", body)
        return [_row_to_opportunity(row) for row in result["data"]]


schema = strawberry.Schema(
    query=Query,
    config=strawberry.schema.config.StrawberryConfig(scalar_map={BigInt: _BIGINT_SCALAR}),
)


# ---------------------------------------------------------------------------
# MCP server (tool-calling interface) + troubleshooting-only /graphql mount
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "grants-gov",
    instructions="""\
Grant opportunity search (read-only, GraphQL) - backed live by the Simpler
Grants API (api.simpler.grants.gov).

WHAT'S IN THIS SERVER: Opportunity records from the Simpler Grants API, the
newer replacement for legacy grants.gov search: title, issuing agency,
description, status (forecasted/posted/closed/archived), award
ceiling/floor, post/close dates, funding category and instrument, and
eligible applicant types.

WHAT IT'S FOR: finding open federal grant opportunities that match an
organization's sector, keywords, or eligibility - the public-funding
counterpart to the `irs990-filings-grants` connector's private-foundation
grant history.

The only tool is `graphql`. Read the `graphql` tool's own description for
the full field list, available filters, and example queries before writing
your first query.""",
)


@mcp.tool(title="Search grants.gov")
async def graphql(query: str, variables: Optional[dict] = None) -> dict:
    """Query grant opportunities via GraphQL, backed live by api.simpler.grants.gov.

    Pass a standard GraphQL document as `query` and, optionally, a dict of
    GraphQL variables as `variables` (for `$var`-style placeholders). The
    return value is `{"data": ..., "errors": ...}`, mirroring a normal
    GraphQL response.

    SCHEMA SUMMARY (fields are camelCase in GraphQL; use standard
    introspection, e.g. `{ __schema { types { name } } }`, for the
    authoritative/current version):

      type Opportunity {
        opportunityId, opportunityNumber, title,
        agencyCode, agencyName, description,
        opportunityStatus,   # FORECASTED | POSTED | CLOSED | ARCHIVED
        awardCeiling, awardFloor,   # BigInt (USD)
        postDate, closeDate,        # ISO date strings, nullable
        fundingCategory, fundingInstrument, applicantTypes,   # [String!]
        url,                  # this opportunity's detail/apply page on simpler.grants.gov
        additionalInfoUrl      # agency-provided link, nullable
      }

      type Query {
        opportunity(id: String!): Opportunity
        opportunities(filter: OpportunityFilter, orderBy: OpportunityOrderBy,
                      limit: Int = 50, offset: Int = 0): [Opportunity!]!
      }

      input OpportunityFilter { query, agencyCode, opportunityStatus,
        fundingCategory, applicantType, minAwardCeiling }

      enum OpportunityOrderBy { CLOSE_DATE_ASC POST_DATE_DESC AWARD_CEILING_DESC }

    `fundingCategory` and `applicantType` take the Simpler Grants API's own
    snake_case codes (e.g. `"education"`, `"nonprofits_non_higher_education_with_501c3"`)
    - see each field's description via introspection for example values.

    PAGINATION NOTE: the upstream API paginates by page number, not row
    offset - `offset` is expected to be a multiple of `limit` (i.e. page
    through with offset=0, limit, 2*limit, ...); other offsets are rounded
    down to the nearest page boundary.

    EXAMPLES

    1. Open opportunities mentioning "literacy", soonest-closing first:
         { opportunities(filter: {query: "literacy", opportunityStatus: POSTED},
                          orderBy: CLOSE_DATE_ASC, limit: 10) {
             title agencyName closeDate awardCeiling url
         } }

    2. Environment-category opportunities open to nonprofits with at least
       a $100k ceiling:
         { opportunities(filter: {fundingCategory: "environment",
                                  applicantType: "nonprofits_non_higher_education_with_501c3",
                                  minAwardCeiling: 100000}) {
             title agencyName awardCeiling closeDate url
         } }

    3. Look up one opportunity directly by ID:
         { opportunity(id: "123e4567-e89b-12d3-a456-426614174000") {
             title description awardCeiling awardFloor closeDate url additionalInfoUrl
         } }
    """
    result = await schema.execute(query, variable_values=variables)
    return {
        "data": result.data,
        "errors": [str(e) for e in result.errors] if result.errors else None,
    }


def main():
    app = mcp.streamable_http_app()
    # Troubleshooting only: not meant to be reachable outside localhost/the
    # docker network, same convention as irs-990's server.py.
    app.mount("/graphql", GraphQL(schema, graphql_ide="graphiql"))
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
