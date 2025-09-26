import os
import re
from datetime import datetime, timezone
from typing import Optional

import psycopg
from psycopg import Connection
from dotenv import load_dotenv

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
# Load local env when running locally; GitHub Actions will use repo secrets/variables
load_dotenv(os.path.join(PROJECT_DIR, ".env.local"))

STATUS_START = "<!-- OFFERS_STATUS:START -->"
STATUS_END = "<!-- OFFERS_STATUS:END -->"


def _validated_table_name(name: Optional[str]) -> str:
    default = "oil_offers_export"
    if not name:
        return default
    name = name.strip()
    if not name:
        return default
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"Invalid table name: {name}")
    return name


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


def build_status_md(conn: Connection, table_name: str) -> str:
    # total rows
    with conn.cursor() as cur:
        cur.execute(f"select count(*) from public.{table_name}")
        total = cur.fetchone()[0]

    # latest update time based on created_at
    with conn.cursor() as cur:
        cur.execute(f"select max(created_at) from public.{table_name}")
        max_created = cur.fetchone()[0]

    last_updated_iso = (
        max_created.astimezone(timezone.utc).isoformat()
        if max_created is not None
        else datetime.now(timezone.utc).isoformat()
    )

    # last 5 recent rows
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select id, company, product, published_at, vigente, created_at
            from public.{table_name}
            order by created_at desc
            limit 5
            """
        )
        recent = cur.fetchall()

    lines = []
    lines.append("### Estado de ofertas (dinámico)")
    lines.append("")
    lines.append(f"- **Última actualización**: {last_updated_iso}")
    lines.append(f"- **Total de registros**: {total}")
    lines.append("")
    lines.append("- **Últimos 5 registros**:")
    if recent:
        for r in recent:
            rid, company, product, published_at, vigente, created_at = r
            pub = published_at.isoformat() if published_at else "-"
            vig = vigente if vigente else "-"
            created = created_at.astimezone(timezone.utc).isoformat() if created_at else "-"
            lines.append(
                f"  - id {rid} | {company} | {product[:60]}{'…' if product and len(product) > 60 else ''} | publ: {pub} | vigente: {vig} | created_at: {created}"
            )
    else:
        lines.append("  - (sin registros)")

    return "\n".join(lines) + "\n"


def update_readme(status_md: str, readme_path: str) -> bool:
    # Replace or append the status block delineated by markers
    if not os.path.exists(readme_path):
        raise FileNotFoundError(f"README not found at {readme_path}")

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    block = f"{STATUS_START}\n\n{status_md}\n{STATUS_END}"

    if STATUS_START in content and STATUS_END in content:
        start_idx = content.index(STATUS_START)
        end_idx = content.index(STATUS_END) + len(STATUS_END)
        new_content = content[:start_idx] + block + content[end_idx:]
    else:
        # append to end with a heading spacer
        new_content = content.rstrip() + "\n\n" + block + "\n"

    if new_content != content:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False


def main():
    table_name = _validated_table_name(os.getenv("OFFERS_TABLE_NAME") or "oil_offers_export")
    with get_db_conn() as conn:
        status_md = build_status_md(conn, table_name)
    readme_path = os.path.join(PROJECT_DIR, "README.md")
    changed = update_readme(status_md, readme_path)
    print("README updated" if changed else "README already up to date")


if __name__ == "__main__":
    main()
