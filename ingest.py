import os
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from dateutil import parser as dateparser
from dotenv import load_dotenv
import psycopg
from psycopg import Connection
import warnings
from tqdm import tqdm

# Load .env explicitly from the project directory when running locally
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR, ".env.local"))

# Source URL (can be overridden via ORIGIN_URL)
URL = os.getenv("ORIGIN_URL")
if not URL or str(URL).strip().lower() in {"", "none"}:
    raise RuntimeError(
        "Missing required environment variable ORIGIN_URL. Set it to the JSON source endpoint (e.g. via .env.local locally or GitHub Actions secrets/variables)."
    )


def html_to_text(value: str) -> str:
    if value is None:
        return ""
    # Replace <br> with line breaks to preserve readability
    value = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    soup = BeautifulSoup(value, "html.parser")
    return soup.get_text("\n").strip()


# Silence noisy BeautifulSoup warning when parsing strings that resemble paths
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


def _validated_table_name(name: Optional[str]) -> str:
    """Return a safe table name with fallback to default if empty or invalid."""
    default = "oil_offers_export"
    if not name:
        return default
    name = name.strip()
    if not name:
        return default
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"Invalid table name: {name}")
    return name


def extract_pdf_url(value: str) -> Optional[str]:
    if not value:
        return None
    # The html contains something like: onclick="window.open('descarga_pdf_oferta.php?hgcd=...')"
    m = re.search(r"window.open\('([^']+descarga_pdf_oferta\\.php\?[^']+)'", value)
    if m:
        path = m.group(1)
        if path.startswith("http"):
            return path
        # Build absolute URL
        return requests.compat.urljoin(URL, path)
    return None


def parse_row(row: List[str]) -> Dict[str, Any]:
    # Order inferred from aaData sample
    # [id, published_at, company, product_html, volume, delivery_start, delivery_end, price_formula,
    #  ncm, delivery_location, notes_html, basin_html, pdf_button_html, vigente]
    def clean(i):
        return row[i] if i < len(row) else None

    raw_id = clean(0)
    raw_published = clean(1)
    raw_company = clean(2)
    raw_product = clean(3)
    raw_volume = clean(4)
    raw_delivery_start = clean(5)
    raw_delivery_end = clean(6)
    raw_price_formula = clean(7)
    raw_ncm = clean(8)
    raw_delivery_location = clean(9)
    raw_notes = clean(10)
    raw_basin = clean(11)
    raw_pdf_btn = clean(12)
    raw_vigente = clean(13)

    # Normalize
    try:
        id_ = int(str(raw_id).strip()) if raw_id is not None else None
    except Exception:
        id_ = None

    def parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return dateparser.parse(s, dayfirst=True)
        except Exception:
            return None

    def parse_d(s: Optional[str]) -> Optional[date]:
        dt = parse_dt(s)
        return dt.date() if dt else None

    published_at = parse_dt(raw_published)
    delivery_start = parse_d(raw_delivery_start)
    delivery_end = parse_d(raw_delivery_end)

    product = html_to_text(raw_product or "")
    notes = html_to_text(raw_notes or "")
    basin = html_to_text(raw_basin or "")

    pdf_url = extract_pdf_url(raw_pdf_btn or "")

    return {
        "id": id_,
        "published_at": published_at,
        "company": (raw_company or "").strip(),
        "product": product,
        "volume": (raw_volume or "").strip(),
        "delivery_start": delivery_start,
        "delivery_end": delivery_end,
        "price_formula": (raw_price_formula or "").strip(),
        "ncm": (raw_ncm or "").strip(),
        "delivery_location": (raw_delivery_location or "").strip(),
        "notes": notes,
        "basin": basin,
        "pdf_url": pdf_url,
        "vigente": (html_to_text(raw_vigente or "").strip() or None),
    }


def fetch_data() -> List[Dict[str, Any]]:
    print(f"Fetching: {URL}")
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("aaData", [])
    parsed = [parse_row(r) for r in tqdm(rows, desc="Parsing rows", unit="row")]
    # only keep those with id
    return [p for p in parsed if p.get("id") is not None]


def get_db_conn() -> Connection:
    host = os.getenv("SUPABASE_HOST")
    port = int(os.getenv("SUPABASE_PORT", "6543"))
    dbname = os.getenv("SUPABASE_DB_NAME", "postgres")
    user = os.getenv("SUPABASE_USER")
    password = os.getenv("SUPABASE_PASSWORD")
    if not all([host, dbname, user, password]):
        raise RuntimeError(
            "Missing required DB environment variables: SUPABASE_HOST, SUPABASE_DB_NAME, SUPABASE_USER, SUPABASE_PASSWORD"
        )

    conn = psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        sslmode="require",
        connect_timeout=15,
    )
    return conn


def ensure_table(conn, table_name: str = "oil_offers_export"):
    table_name = _validated_table_name(table_name)
    ddl = f"""
    create table if not exists public.{table_name} (
        id integer primary key,
        published_at timestamptz,
        company text,
        product text,
        volume text,
        delivery_start date,
        delivery_end date,
        price_formula text,
        ncm text,
        delivery_location text,
        notes text,
        basin text,
        pdf_url text,
        vigente text,
        created_at timestamptz not null default now()
    );
    """
    # Execute DDL in autocommit mode to avoid "read-only transaction" errors
    # when connecting via poolers (e.g., PgBouncer transaction pooling on Supabase).
    # We temporarily enable autocommit for the DDL and then restore the previous setting.
    prev_autocommit = getattr(conn, "autocommit", False)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(ddl)
    finally:
        conn.autocommit = prev_autocommit


def upsert_rows(
    conn, rows: List[Dict[str, Any]], table_name: str = "oil_offers_export"
) -> int:
    if not rows:
        return 0
    table_name = _validated_table_name(table_name)
    cols = [
        "id",
        "published_at",
        "company",
        "product",
        "volume",
        "delivery_start",
        "delivery_end",
        "price_formula",
        "ncm",
        "delivery_location",
        "notes",
        "basin",
        "pdf_url",
        "vigente",
    ]
    # Determine which IDs already exist to avoid counting them as newly inserted
    ids = [r.get("id") for r in rows if r.get("id") is not None]
    existing_ids: set[int] = set()
    if ids:
        with conn.cursor() as cur:
            cur.execute(
                f"select id from public.{table_name} where id = any(%s)",
                (ids,),
            )
            existing_ids = {row[0] for row in cur.fetchall()}

    new_rows = [r for r in rows if r.get("id") not in existing_ids]
    if not new_rows:
        return 0

    records = [[r.get(c) for c in cols] for r in new_rows]

    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"""
        insert into public.{table_name} ({', '.join(cols)})
        values ({placeholders})
        on conflict (id) do nothing
    """
    batch_size = 500
    with conn.cursor() as cur:
        for i in tqdm(range(0, len(records), batch_size), desc="Inserting", unit="row"):
            chunk = records[i : i + batch_size]
            cur.executemany(insert_sql, chunk)
    conn.commit()
    return len(new_rows)


def main():
    table_name = os.getenv("OFFERS_TABLE_NAME") or "oil_offers_export"
    table_name = _validated_table_name(table_name)
    rows = fetch_data()
    # Sort by id ascending to insert old first
    rows.sort(key=lambda r: r["id"])
    with get_db_conn() as conn:
        ensure_table(conn, table_name)
        inserted = upsert_rows(conn, rows, table_name)
        print(
            f"Fetched {len(rows)} offers. Inserted new: {inserted} into table {table_name}."
        )


if __name__ == "__main__":
    main()
