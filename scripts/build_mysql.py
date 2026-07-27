#!/usr/bin/env python3
"""Build the MySQL irs990 database from raw IRS e-file XML returns plus IRS BMF NTEE codes.

Requires the Docker Compose stack to be up (`docker compose up -d`) and
credentials in `.env` at the repo root.

Usage: .venv/bin/python3 scripts/build_mysql.py
"""
import csv
import multiprocessing
import os
import re
import shutil
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pymysql
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

DATASETS_DIR = REPO_ROOT / "datasets"
BMF_DIR = DATASETS_DIR / "_bmf"
BMF_FILES = ["eo1.csv", "eo2.csv", "eo3.csv", "eo4.csv"]
BMF_BASE_URL = "https://www.irs.gov/pub/irs-soi/"

# (revenue, expenses, assets_eoy, contributions) tag names per form type
SUMMARY_FIELDS = {
    "990": ("CYTotalRevenueAmt", "CYTotalExpensesAmt", "TotalAssetsEOYAmt", "CYContributionsGrantsAmt"),
    "990EZ": ("TotalRevenueAmt", "TotalExpensesAmt", "NetAssetsOrFundBalancesEOYAmt", "ContributionsGiftsGrantsEtcAmt"),
}

NTEE_MAJOR_GROUPS = {
    "A": "Arts, Culture & Humanities",
    "B": "Education",
    "C": "Environment",
    "D": "Animal-Related",
    "E": "Health Care",
    "F": "Mental Health & Crisis Intervention",
    "G": "Diseases, Disorders & Medical Disciplines",
    "H": "Medical Research",
    "I": "Crime & Legal-Related",
    "J": "Employment",
    "K": "Food, Agriculture & Nutrition",
    "L": "Housing & Shelter",
    "M": "Public Safety, Disaster Preparedness & Relief",
    "N": "Recreation & Sports",
    "O": "Youth Development",
    "P": "Human Services",
    "Q": "International, Foreign Affairs & National Security",
    "R": "Civil Rights, Social Action & Advocacy",
    "S": "Community Improvement & Capacity Building",
    "T": "Philanthropy, Voluntarism & Grantmaking Foundations",
    "U": "Science & Technology Research Institutes",
    "V": "Social Science Research Institutes",
    "W": "Public & Societal Benefit",
    "X": "Religion-Related",
    "Y": "Mutual & Membership Benefit",
    "Z": "Unknown / Unclassified",
}


def local(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def find_local(elem, name):
    """Find first descendant with this local tag name, namespace-agnostic."""
    if elem is None:
        return None
    for child in elem.iter():
        if local(child.tag) == name:
            return child
    return None


def text_of(elem, name, default=None):
    e = find_local(elem, name)
    if e is None or e.text is None:
        return default
    return e.text.strip()


def int_of(elem, name):
    v = text_of(elem, name)
    if v is None:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def direct_child(elem, name):
    """Find a direct child with this local tag name (not deep search)."""
    if elem is None:
        return None
    for child in elem:
        if local(child.tag) == name:
            return child
    return None


# IRS filers commonly fill the website field with a placeholder rather than
# leaving it blank; normalize these to NULL instead of storing junk values.
WEBSITE_PLACEHOLDER_VALUES = {"NA", "NONE", "NOTAPPLICABLE", "UNKNOWN", "X", ""}


def clean_website(raw):
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    compact = re.sub(r"[\s.\-/\\]", "", value).upper()
    if compact in WEBSITE_PLACEHOLDER_VALUES:
        return None
    return value


def extract_tax_exempt_subsection(form):
    """Self-reported exemption basis, e.g. '501(c)(3)' or '4947(a)(1)'."""
    ind = find_local(form, "Organization501cInd")
    if ind is not None:
        code = ind.get("organization501cTypeTxt")
        return f"501(c)({code})" if code else "501(c)"
    if find_local(form, "Organization4947a1Ind") is not None:
        return "4947(a)(1)"
    if find_local(form, "Organization527Ind") is not None:
        return "527"
    if find_local(form, "Organization501c3ExemptPFInd") is not None:
        return "501(c)(3) private foundation"
    if find_local(form, "Organization501c3TaxablePFInd") is not None:
        return "501(c)(3) taxable private foundation"
    if find_local(form, "Organization4947a1TrtdPFInd") is not None:
        return "4947(a)(1) trust treated as private foundation"
    return None


def extract_filer_identity(root):
    header = find_local(root, "ReturnHeader")
    filer = find_local(header, "Filer")
    ein = text_of(filer, "EIN")
    biz_name = find_local(filer, "BusinessName")
    org_name = text_of(biz_name, "BusinessNameLine1Txt")
    org_name2 = text_of(biz_name, "BusinessNameLine2Txt")
    addr = find_local(filer, "USAddress")
    address_line1 = text_of(addr, "AddressLine1Txt")
    city = text_of(addr, "CityNm")
    state = text_of(addr, "StateAbbreviationCd")
    zip_cd = text_of(addr, "ZIPCd")
    phone = text_of(filer, "PhoneNum")
    officer = find_local(header, "BusinessOfficerGrp")
    officer_name = text_of(officer, "PersonNm")
    tax_yr = int_of(header, "TaxYr")
    tax_period_end = text_of(header, "TaxPeriodEndDt")
    return_ts = text_of(header, "ReturnTs")
    return {
        "ein": ein,
        "org_name": org_name,
        "org_name2": org_name2,
        "address_line1": address_line1,
        "city": city,
        "state": state,
        "zip": zip_cd,
        "phone": phone,
        "principal_officer_name": officer_name,
        "tax_yr": tax_yr,
        "tax_period_end": tax_period_end,
        "return_ts": return_ts,
    }


def extract_990_or_ez(root, form_type):
    form = find_local(root, "IRS990" if form_type == "990" else "IRS990EZ")
    rev_tag, exp_tag, asset_tag, contrib_tag = SUMMARY_FIELDS[form_type]
    mission = text_of(form, "MissionDesc") or text_of(form, "ActivityOrMissionDesc")
    return {
        "mission_desc": mission,
        "website_url": clean_website(text_of(form, "WebsiteAddressTxt")),
        "formation_year": int_of(form, "FormationYr"),
        "gross_receipts": int_of(form, "GrossReceiptsAmt"),
        "employee_count": int_of(form, "TotalEmployeeCnt"),
        "tax_exempt_subsection": extract_tax_exempt_subsection(form),
        "total_revenue": int_of(form, rev_tag),
        "total_expenses": int_of(form, exp_tag),
        "total_assets_eoy": int_of(form, asset_tag),
        "contributions_grants_received": int_of(form, contrib_tag),
    }


def extract_990pf(root):
    form = find_local(root, "IRS990PF")
    are = direct_child(form, "AnalysisOfRevenueAndExpenses")
    total_revenue = int_of(are, "TotalRevAndExpnssAmt")
    total_expenses = int_of(are, "TotalExpensesRevAndExpnssAmt")
    contributions = int_of(are, "ContriPaidRevAndExpnssAmt")
    assets = int_of(form, "FMVAssetsEOYAmt")
    supp = direct_child(form, "SupplementaryInformationGrp")
    total_grants_paid = int_of(supp, "TotalGrantOrContriPdDurYrAmt")
    return {
        "mission_desc": None,
        "website_url": clean_website(text_of(form, "WebsiteAddressTxt")),
        "tax_exempt_subsection": extract_tax_exempt_subsection(form),
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "total_assets_eoy": assets,
        "contributions_grants_received": contributions,
        "total_grants_paid": total_grants_paid,
    }


def extract_990_schedule_i_grants(root, grantor_ein, grantor_name, tax_yr, rel_path):
    sched = find_local(root, "IRS990ScheduleI")
    if sched is None:
        return []
    rows = []
    for rec in sched:
        if local(rec.tag) != "RecipientTable":
            continue
        biz = direct_child(rec, "RecipientBusinessName")
        recipient_name = text_of(biz, "BusinessNameLine1Txt") if biz is not None else text_of(rec, "RecipientPersonNm")
        addr = direct_child(rec, "USAddress")
        rows.append({
            "grantor_ein": grantor_ein,
            "grantor_name": grantor_name,
            "tax_yr": tax_yr,
            "recipient_name": recipient_name,
            "recipient_ein": text_of(rec, "RecipientEIN"),
            "recipient_city": text_of(addr, "CityNm") if addr is not None else None,
            "recipient_state": text_of(addr, "StateAbbreviationCd") if addr is not None else None,
            "recipient_zip": text_of(addr, "ZIPCd") if addr is not None else None,
            "purpose": text_of(rec, "PurposeOfGrantTxt"),
            "cash_amt": int_of(rec, "CashGrantAmt"),
            "noncash_amt": int_of(rec, "NonCashAssistanceAmt"),
            "total_amt": (int_of(rec, "CashGrantAmt") or 0) + (int_of(rec, "NonCashAssistanceAmt") or 0),
            "source_schedule": "990_schedule_i",
            "source_file": rel_path,
        })
    return rows


def extract_990pf_grants(root, grantor_ein, grantor_name, tax_yr, rel_path):
    form = find_local(root, "IRS990PF")
    supp = direct_child(form, "SupplementaryInformationGrp") if form is not None else None
    if supp is None:
        return []
    rows = []
    for rec in supp:
        if local(rec.tag) != "GrantOrContributionPdDurYrGrp":
            continue
        biz = direct_child(rec, "RecipientBusinessName")
        if biz is not None:
            recipient_name = text_of(biz, "BusinessNameLine1Txt")
        else:
            person = direct_child(rec, "RecipientPersonNm")
            recipient_name = person.text.strip() if person is not None and person.text else None
        addr = direct_child(rec, "RecipientUSAddress")
        amt = int_of(rec, "Amt")
        rows.append({
            "grantor_ein": grantor_ein,
            "grantor_name": grantor_name,
            "tax_yr": tax_yr,
            "recipient_name": recipient_name,
            "recipient_ein": text_of(rec, "RecipientEIN"),
            "recipient_city": text_of(addr, "CityNm") if addr is not None else None,
            "recipient_state": text_of(addr, "StateAbbreviationCd") if addr is not None else None,
            "recipient_zip": text_of(addr, "ZIPCd") if addr is not None else None,
            "purpose": text_of(rec, "GrantOrContributionPurposeTxt"),
            "cash_amt": amt,
            "noncash_amt": 0,
            "total_amt": amt or 0,
            "source_schedule": "990pf_part_xv",
            "source_file": rel_path,
        })
    return rows


def parse_file(path):
    """Parse one XML file. Returns (filing_row_or_None, grant_rows, error_or_None)."""
    rel_path = str(path.relative_to(REPO_ROOT))
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        header = find_local(root, "ReturnHeader")
        form_type = text_of(header, "ReturnTypeCd")
        if form_type not in ("990", "990EZ", "990PF"):
            return None, [], None  # skip 990T and anything else

        identity = extract_filer_identity(root)
        if form_type == "990PF":
            summary = extract_990pf(root)
        else:
            summary = extract_990_or_ez(root, form_type)

        filing = {
            **identity,
            **summary,
            "form_type": form_type,
            "source_file": rel_path,
        }
        filing.setdefault("total_grants_paid", None)

        grants = []
        if form_type == "990":
            grants = extract_990_schedule_i_grants(
                root, identity["ein"], identity["org_name"], identity["tax_yr"], rel_path
            )
        elif form_type == "990PF":
            grants = extract_990pf_grants(
                root, identity["ein"], identity["org_name"], identity["tax_yr"], rel_path
            )

        if form_type in ("990", "990EZ") and filing["total_grants_paid"] is None and grants:
            filing["total_grants_paid"] = sum(g["total_amt"] for g in grants)

        return filing, grants, None
    except Exception as exc:  # noqa: BLE001 - log and skip malformed files
        return None, [], f"{rel_path}: {exc}"


FILING_COLUMNS = [
    "ein", "form_type", "tax_yr", "tax_period_end", "return_ts", "org_name", "org_name2",
    "address_line1", "city", "state", "zip", "phone", "principal_officer_name",
    "mission_desc", "website_url", "formation_year", "gross_receipts", "employee_count",
    "tax_exempt_subsection", "total_revenue", "total_expenses", "total_assets_eoy",
    "contributions_grants_received", "total_grants_paid", "source_file",
]

NTEE_COLUMNS = ["ntee_code", "ntee_major_code", "ntee_major_desc"]

GRANT_COLUMNS = [
    "grantor_ein", "grantor_name", "tax_yr", "recipient_name", "recipient_ein",
    "recipient_city", "recipient_state", "recipient_zip", "purpose",
    "cash_amt", "noncash_amt", "total_amt", "source_schedule", "source_file",
]


def ensure_bmf_files():
    """Download the 4 national IRS EO BMF region CSVs if not already cached."""
    BMF_DIR.mkdir(parents=True, exist_ok=True)
    for name in BMF_FILES:
        dest = BMF_DIR / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[bmf] {name} already cached ({dest.stat().st_size / 1_000_000:.0f}MB)")
            continue
        url = BMF_BASE_URL + name
        print(f"[bmf] downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        tmp = dest.with_suffix(".tmp")
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
            shutil.copyfileobj(resp, f, length=1024 * 1024)
        tmp.rename(dest)
        print(f"  saved {dest.stat().st_size / 1_000_000:.0f}MB -> {dest}")


def read_bmf_ntee_rows():
    """Read EIN -> NTEE_CD from the cached BMF CSVs."""
    rows = {}
    for name in BMF_FILES:
        path = BMF_DIR / name
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ein = (row.get("EIN") or "").strip()
                ntee = (row.get("NTEE_CD") or "").strip()
                if ein and ntee:
                    rows[ein] = ntee
    return rows


# MySQL column type overrides (defaults to VARCHAR(255) for anything not listed)
COLUMN_TYPES = {
    "id": "BIGINT AUTO_INCREMENT PRIMARY KEY",
    "ein": "VARCHAR(9)",
    "grantor_ein": "VARCHAR(9)",
    "recipient_ein": "VARCHAR(9)",
    "form_type": "VARCHAR(10)",
    "tax_yr": "INT",
    "tax_period_end": "VARCHAR(10)",
    "return_ts": "VARCHAR(40)",
    "state": "VARCHAR(2)",
    "recipient_state": "VARCHAR(2)",
    "zip": "VARCHAR(10)",
    "recipient_zip": "VARCHAR(10)",
    "phone": "VARCHAR(20)",
    "mission_desc": "TEXT",
    "purpose": "TEXT",
    "formation_year": "INT",
    "gross_receipts": "BIGINT",
    "employee_count": "INT",
    "tax_exempt_subsection": "VARCHAR(64)",
    "source_file": "VARCHAR(255)",
    "source_schedule": "VARCHAR(20)",
    "ntee_code": "VARCHAR(10)",
    "ntee_major_code": "VARCHAR(1)",
    "ntee_major_desc": "VARCHAR(80)",
    "total_revenue": "BIGINT",
    "total_expenses": "BIGINT",
    "total_assets_eoy": "BIGINT",
    "contributions_grants_received": "BIGINT",
    "total_grants_paid": "BIGINT",
    "cash_amt": "BIGINT",
    "noncash_amt": "BIGINT",
    "total_amt": "BIGINT",
}


def col_def(name):
    return f"{name} {COLUMN_TYPES.get(name, 'VARCHAR(255)')}"


def connect():
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_ADMIN_USER"],
        password=os.environ["MYSQL_ADMIN_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        autocommit=False,
    )


def create_schema(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS grants")
        cur.execute("DROP TABLE IF EXISTS filings")
        cur.execute("DROP TABLE IF EXISTS bmf_ntee")

        filings_cols = ", ".join(col_def(c) for c in ["id"] + FILING_COLUMNS + NTEE_COLUMNS)
        cur.execute(f"""
            CREATE TABLE filings (
                {filings_cols}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        grants_cols = ", ".join(col_def(c) for c in ["id"] + GRANT_COLUMNS)
        cur.execute(f"""
            CREATE TABLE grants (
                {grants_cols}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.commit()


INSERT_CHUNK = 2000  # cap per-statement row count so one grant-heavy filing
                     # (e.g. a corporate matching-gifts program with tens of
                     # thousands of small grants) can't build a single INSERT
                     # that blows past MySQL's max_allowed_packet.


def _insert_chunked(conn, table, columns, rows):
    if not rows:
        return
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        for i in range(0, len(rows), INSERT_CHUNK):
            cur.executemany(sql, rows[i:i + INSERT_CHUNK])


def flush(conn, filings_buf, grants_buf):
    _insert_chunked(conn, "filings", FILING_COLUMNS, filings_buf)
    filings_buf.clear()
    _insert_chunked(conn, "grants", GRANT_COLUMNS, grants_buf)
    grants_buf.clear()
    conn.commit()


def dedup_filings(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM filings")
        before = cur.fetchone()[0]
        cur.execute("""
            DELETE FROM filings WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY ein, tax_period_end, form_type
                        ORDER BY return_ts DESC, id DESC
                    ) AS rn
                    FROM filings
                ) t
                WHERE t.rn = 1
            )
        """)
        cur.execute("""
            DELETE FROM grants WHERE source_file NOT IN (
                SELECT source_file FROM (SELECT source_file FROM filings) t
            )
        """)
        cur.execute("SELECT COUNT(*) FROM filings")
        after = cur.fetchone()[0]
    conn.commit()
    print(f"[dedup] {before} -> {after} filings ({before - after} duplicate returns removed)")


def apply_ntee(conn):
    rows = read_bmf_ntee_rows()
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE bmf_ntee (ein VARCHAR(9) PRIMARY KEY, ntee_code VARCHAR(10)) ENGINE=InnoDB")
        cur.executemany(
            "INSERT INTO bmf_ntee (ein, ntee_code) VALUES (%s, %s)",
            list(rows.items()),
        )
        print(f"[bmf] loaded {len(rows)} EIN -> NTEE_CD mappings")

        cur.execute("""
            UPDATE filings f JOIN bmf_ntee b ON b.ein = f.ein
            SET f.ntee_code = b.ntee_code
        """)
        cur.execute("""
            UPDATE filings SET ntee_major_code = LEFT(ntee_code, 1)
            WHERE ntee_code IS NOT NULL AND ntee_code != ''
        """)
        case_expr = " ".join(f"WHEN '{letter}' THEN '{desc}'" for letter, desc in NTEE_MAJOR_GROUPS.items())
        cur.execute(f"""
            UPDATE filings
            SET ntee_major_desc = CASE ntee_major_code {case_expr} ELSE NULL END
            WHERE ntee_major_code IS NOT NULL
        """)
        cur.execute("DROP TABLE bmf_ntee")
    conn.commit()


def build_indexes_and_fulltext(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE INDEX idx_filings_ein ON filings(ein)")
        cur.execute("CREATE INDEX idx_filings_tax_yr ON filings(tax_yr)")
        cur.execute("CREATE INDEX idx_filings_state ON filings(state)")
        cur.execute("CREATE INDEX idx_filings_form_type ON filings(form_type)")
        cur.execute("CREATE INDEX idx_filings_ntee_major ON filings(ntee_major_code)")

        cur.execute("CREATE INDEX idx_grants_grantor_ein ON grants(grantor_ein)")
        cur.execute("CREATE INDEX idx_grants_recipient_ein ON grants(recipient_ein)")
        cur.execute("CREATE INDEX idx_grants_recipient_state ON grants(recipient_state)")
        cur.execute("CREATE INDEX idx_grants_tax_yr ON grants(tax_yr)")

        cur.execute("CREATE FULLTEXT INDEX ft_filings ON filings(org_name, mission_desc, ntee_major_desc)")
        cur.execute("CREATE FULLTEXT INDEX ft_grants ON grants(recipient_name, purpose)")
    conn.commit()


def main():
    ensure_bmf_files()

    files = sorted(DATASETS_DIR.glob("**/*_public.xml"))
    total = len(files)
    print(f"Found {total} XML files under {DATASETS_DIR}")
    if total == 0:
        sys.exit("No files found, aborting.")

    conn = connect()
    create_schema(conn)

    start = time.time()
    filings_buf, grants_buf = [], []
    n_filings = n_grants = n_errors = 0
    errors_sample = []
    FLUSH_EVERY = 20_000

    with multiprocessing.Pool() as pool:
        for i, (filing, grant_rows, error) in enumerate(pool.imap_unordered(parse_file, files, chunksize=100), 1):
            if error:
                n_errors += 1
                if len(errors_sample) < 10:
                    errors_sample.append(error)
            if filing:
                filings_buf.append(tuple(filing.get(c) for c in FILING_COLUMNS))
                n_filings += 1
            if grant_rows:
                grants_buf.extend(tuple(g.get(c) for c in GRANT_COLUMNS) for g in grant_rows)
                n_grants += len(grant_rows)
            if len(filings_buf) >= FLUSH_EVERY or len(grants_buf) >= FLUSH_EVERY:
                flush(conn, filings_buf, grants_buf)
            if i % 50_000 == 0:
                print(f"  parsed {i}/{total} files...")
    flush(conn, filings_buf, grants_buf)

    elapsed = time.time() - start
    print(f"Parsed {total} files in {elapsed:.1f}s -> {n_filings} filings, {n_grants} grants, {n_errors} errors")

    dedup_filings(conn)
    apply_ntee(conn)
    build_indexes_and_fulltext(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT form_type, COUNT(*) FROM filings GROUP BY form_type ORDER BY 2 DESC")
        print("\nRows per form type:")
        for form_type, count in cur.fetchall():
            print(f"  {form_type}: {count}")

        cur.execute("SELECT COUNT(ntee_code), COUNT(*) FROM filings")
        ntee_count, total_count = cur.fetchone()
        print(f"\nNTEE coverage: {ntee_count}/{total_count} filings ({100 * ntee_count / total_count:.1f}%)")

    if errors_sample:
        print(f"\n{n_errors} files failed to parse (first {len(errors_sample)}):")
        for e in errors_sample:
            print(f"  {e}")

    conn.close()
    print("\nMySQL database 'irs990' built successfully.")


if __name__ == "__main__":
    main()
