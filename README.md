{{ ... }}

This repository ingests public oil export offer listings from Argentina every 15 minutes and stores new entries in a Supabase Postgres database.

Source URL:
- https://www.se.gob.ar/comercio_exterior_liquidos/oferta_com_ext_expo_store.php
  
## What it does
- Fetches the JSON feed and parses each row (company, product, volume, dates, formula, location, notes, basin, PDF link, etc.).
- Cleans HTML fields (replaces `<br>` and strips tags) and extracts the PDF URL from the `onclick` button.
- Deduplicates by the numeric offer `id` and inserts only new entries into Postgres.
- Runs on a GitHub Actions schedule every 15 minutes.
  
## Estado (dinámico)
Este bloque se actualiza automáticamente con los últimos registros y la fecha de la última actualización.
  
<!-- OFFERS_STATUS:START -->

### Estado de ofertas (dinámico)

- **Última actualización**: 2025-09-26T18:49:04.097025+00:00
- **Total de registros**: 2418

- **Últimos 5 registros**:
  - id 2960 | Pan American Energy (Sucursal Argentina) LLC | GASOLINAS, EXCEPTO LAS DE AVIACIÓN
Sin Plomo, Otras | publ: 2025-09-26T15:09:00+00:00 | vigente: No | created_at: 2025-09-26T18:49:04.097025+00:00
  - id 2959 | REFINERÍA DEL NORTE S.A. | GASOIL | publ: 2025-09-26T15:09:00+00:00 | vigente: No | created_at: 2025-09-26T18:49:04.097025+00:00
  - id 37 | AXION ENERGY ARGENTINA S.A. | GASOLINAS, EXCEPTO LAS DE AVIACIÓN
Sin plomo, de RON inferio… | publ: 2017-10-13T12:10:00+00:00 | vigente: Si | created_at: 2025-09-26T18:36:42.999066+00:00
  - id 39 | Pan American Energy (Sucursal Argentina) LLC | ACEITES CRUDOS DE PETRÓLEO
Otros | publ: 2017-10-25T12:10:00+00:00 | vigente: Si | created_at: 2025-09-26T18:36:42.999066+00:00
  - id 38 | SHELL C.A.P.S.A. | GASOLINAS, EXCEPTO LAS DE AVIACIÓN
Sin plomo, de RON inferio… | publ: 2017-10-13T16:10:00+00:00 | vigente: Si | created_at: 2025-09-26T18:36:42.999066+00:00

<!-- OFFERS_STATUS:END -->
  
## Table schema
The script auto-creates the table `public.oil_offers_export` if it does not exist.

Columns:
- id integer primary key
- published_at timestamptz
- company text
{{ ... }}
- volume text
- delivery_start date
- delivery_end date
- price_formula text
- ncm text
- delivery_location text
- notes text
- basin text
- pdf_url text
- vigente text
- created_at timestamptz default now()

You can override the table name using the env var `OFFERS_TABLE_NAME`.

## Local development

1) Copy `.env` and fill in your DB password (do not commit secrets):

```
SUPABASE_HOST=aws-1-us-east-2.pooler.supabase.com
SUPABASE_PORT=6543
SUPABASE_DB_NAME=postgres
SUPABASE_USER=<your_user>
SUPABASE_PASSWORD=<your_password>
OFFERS_TABLE_NAME=oil_offers_export
```

2) Create a virtual environment and install deps:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3) Run:

```
python ingest.py
```

## GitHub Actions setup

This repo defines `.github/workflows/ingest.yml` that runs every 15 minutes.

Set the following GitHub Actions repository secrets (Settings → Secrets and variables → Actions → Secrets):
- SUPABASE_HOST
- SUPABASE_PORT (e.g., 6543)
- SUPABASE_DB_NAME (e.g., postgres)
- SUPABASE_USER
- SUPABASE_PASSWORD

Optional repository variable (Settings → Secrets and variables → Actions → Variables):
- OFFERS_TABLE_NAME (default `oil_offers_export`)

Once set, the workflow will run on schedule and on manual dispatch.

## Notes
- The parser assumes the feed structure `aaData` is an array of arrays in a fixed column order. If the feed changes, update `parse_row()` in `ingest.py`.
- Insert strategy uses `INSERT ... ON CONFLICT DO NOTHING` on primary key `id` to avoid duplicates.
- The script uses SSL (`sslmode=require`) when connecting to Supabase.
