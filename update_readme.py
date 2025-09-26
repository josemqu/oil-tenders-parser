import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import psycopg
from psycopg import Connection
from dotenv import load_dotenv
from urllib.parse import quote
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

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

    now_utc = datetime.now(timezone.utc)
    if max_created is not None and max_created.tzinfo is None:
        # assume UTC if naive
        max_created = max_created.replace(tzinfo=timezone.utc)
    last_updated_dt = max_created or now_utc
    # Build AR timezone
    if ZoneInfo is not None:
        tz_ar = ZoneInfo("America/Argentina/Buenos_Aires")
    else:
        tz_ar = timezone(timedelta(hours=-3))

    # Considerar timestamps locales de Argentina cuando sean naive
    if last_updated_dt.tzinfo is None:
        last_updated_dt = last_updated_dt.replace(tzinfo=tz_ar)
    last_updated_ar = last_updated_dt.astimezone(tz_ar)
    def fmt_ar(dt: datetime) -> str:
        # Mostrar fecha/hora natural en horario AR sin sufijos
        return dt.strftime("%d/%m/%Y %H:%M")

    # status color based on recency (comparar en horario AR)
    now_ar = now_utc.astimezone(tz_ar)
    age_minutes = (now_ar - last_updated_ar).total_seconds() / 60.0
    # Umbrales configurables: FRESH_MINUTES (por defecto 30), RECENT_MINUTES (por defecto 120)
    fresh_minutes = int(os.getenv("FRESH_MINUTES", "30"))
    recent_minutes = int(os.getenv("RECENT_MINUTES", "120"))
    if age_minutes <= fresh_minutes:
        status_color = "brightgreen"
        status_text = "al_dia"
    elif age_minutes <= recent_minutes:
        status_color = "yellow"
        status_text = "reciente"
    else:
        status_color = "red"
        status_text = "desactualizado"

    # Humanize age, e.g., "hace 12m" or "hace 2h 5m"
    age_m = int(round(age_minutes)) if age_minutes >= 0 else 0
    if age_m < 60:
        age_human = f"hace {age_m}m"
    else:
        h = age_m // 60
        m = age_m % 60
        age_human = f"hace {h}h {m}m" if m else f"hace {h}h"

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

    # daily evolution last 14 days (group by AR local date)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select cast(created_at at time zone 'America/Argentina/Buenos_Aires' as date) as d, count(*)
            from public.{table_name}
            where created_at >= (now() at time zone 'utc') - interval '14 days'
            group by d
            order by d
            """
        )
        evolution = cur.fetchall()  # list of (date, count)

    # Build badges (Shields.io) — NOTE: mostramos la fecha como texto para evitar roturas del badge
    badge_total = f"https://img.shields.io/badge/total__registros-{total}-blue?style=flat-square"

    lines = []
    lines.append(f"Última actualización: {fmt_ar(last_updated_ar)}")
    lines.append("<!-- badges:start -->")
    # Recency badge shows humanized age; use label 'recencia'
    recency_badge = f"https://img.shields.io/badge/recencia-{quote(age_human.replace(' ', '_'))}-{status_color}?style=flat-square"
    lines.append(
        f"![Total registros]({badge_total}) "
        f"![Recencia]({recency_badge})"
    )
    lines.append("<!-- badges:end -->")
    lines.append("")
    lines.append("### Últimos 5 registros")
    lines.append("")
    if recent:
        # HTML table to control column widths
        lines.append("<table>")
        lines.append("  <colgroup>")
        lines.append("    <col style=\"width:8%\">")
        lines.append("    <col style=\"width:24%\">")
        lines.append("    <col style=\"width:38%\">")
        lines.append("    <col style=\"width:12%\">")
        lines.append("    <col style=\"width:8%\">")
        lines.append("    <col style=\"width:10%\">")
        lines.append("  </colgroup>")
        lines.append("  <thead>")
        lines.append("    <tr><th style=\"text-align:right\">ID</th><th>Compañía</th><th>Producto</th><th>Publ.</th><th>Vigente</th><th>Creado</th></tr>")
        lines.append("  </thead>")
        lines.append("  <tbody>")
        for r in recent:
            rid, company, product, published_at, vigente, created_at = r
            prod = (product or "").replace("\n", " ")
            # allow more content without truncation, but avoid extremely long cells
            if len(prod) > 120:
                prod = prod[:120] + "…"
            # Mostrar published_at tal como está almacenado (sin convertir tz)
            if published_at:
                pub = published_at.strftime("%d/%m/%Y %H:%M")
            else:
                pub = "-"
            vig = vigente if vigente else "-"
            # Mostrar created_at tal como está almacenado (sin convertir tz)
            if created_at:
                creado = created_at.strftime("%d/%m/%Y %H:%M")
            else:
                creado = "-"
            lines.append(
                f"    <tr><td style=\"text-align:right\">{rid}</td><td>{company}</td><td>{prod}</td><td>{pub}</td><td>{vig}</td><td>{creado}</td></tr>"
            )
        lines.append("  </tbody>")
        lines.append("</table>")
    else:
        lines.append("(sin registros)")

    lines.append("")
    lines.append("### Evolución (últimos 14 días)")
    lines.append("")

    # Reemplazo del gráfico Mermaid por una tabla Markdown para compatibilidad
    if evolution:
        lines.append("| Día | Registros |")
        lines.append("|:---:|---:|")
        for d, c in evolution:
            dia = d.strftime('%d/%m')
            lines.append(f"| {dia} | {c} |")
    else:
        lines.append("(sin datos suficientes para mostrar evolución)")

    # No agregar totales/actualización nuevamente para evitar duplicados visuales

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
