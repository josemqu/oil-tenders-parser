# Ingesta de Ofertas de Exportación de Petróleo (Argentina)

Este repositorio ingesta el listado público de ofertas de exportación de petróleo de Argentina cada 15 minutos y almacena los registros nuevos en una base de datos Postgres (Supabase).

Fuente:

- [Listado oficial de ofertas](https://www.se.gob.ar/comercio_exterior_liquidos/oferta_com_ext_expo_store.php)
  
## Qué hace

- Descarga el feed JSON y parsea cada fila (empresa, producto, volumen, fechas, fórmula de precio, ubicación, notas, cuenca, enlace al PDF, etc.).
- Limpia campos HTML (reemplaza `<br>` y remueve etiquetas) y extrae la URL del PDF desde el botón `onclick`.
- Deduplica por el `id` numérico de la oferta e inserta solo registros nuevos en Postgres.
- Se ejecuta mediante GitHub Actions cada 15 minutos.
  
## Estado (dinámico)
Este bloque se actualiza automáticamente con los últimos registros y la fecha de la última actualización.
  
<!-- OFFERS_STATUS:START -->

<!-- badges:start -->
![Última actualización](https://img.shields.io/badge/actualizado-2025--09--26_18%3A49_UTC-red?style=flat-square) ![Total registros](https://img.shields.io/badge/total__registros-2418-blue?style=flat-square) ![Estado](https://img.shields.io/badge/estado-desactualizado-red?style=flat-square)
<!-- badges:end -->

#### Últimos 5 registros

| ID | Compañía | Producto | Publ. | Vigente | Creado |
|---:|---|---|---|---|---|
| 2960 | Pan American Energy (Sucursal Argentina) LLC | GASOLINAS, EXCEPTO LAS DE AVIACIÓN Sin Plomo, Otras | 2025-09-26T15:09:00+00:00 | No | 2025-09-26T18:49:04.097025+00:00 |
| 2959 | REFINERÍA DEL NORTE S.A. | GASOIL | 2025-09-26T15:09:00+00:00 | No | 2025-09-26T18:49:04.097025+00:00 |
| 37 | AXION ENERGY ARGENTINA S.A. | GASOLINAS, EXCEPTO LAS DE AVIACIÓN Sin plomo, de RON inferio… | 2017-10-13T12:10:00+00:00 | Si | 2025-09-26T18:36:42.999066+00:00 |
| 39 | Pan American Energy (Sucursal Argentina) LLC | ACEITES CRUDOS DE PETRÓLEO Otros | 2017-10-25T12:10:00+00:00 | Si | 2025-09-26T18:36:42.999066+00:00 |
| 38 | SHELL C.A.P.S.A. | GASOLINAS, EXCEPTO LAS DE AVIACIÓN Sin plomo, de RON inferio… | 2017-10-13T16:10:00+00:00 | Si | 2025-09-26T18:36:42.999066+00:00 |

#### Evolución (últimos 14 días)

```mermaid
xychart-beta
  title "Registros por día (created_at)"
  x-axis labels [09-26]
  y-axis label "Registros"
  bar [2418]
```

Actualizado (UTC): 2025-09-26T18:49:04.097025+00:00
Total de registros: 2418

<!-- OFFERS_STATUS:END -->
  
## Esquema de tabla

El script crea automáticamente la tabla `public.oil_offers_export` si no existe.

Columnas:
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

Podés cambiar el nombre de la tabla con la variable de entorno `OFFERS_TABLE_NAME`.

## Desarrollo local

1. Copiá `.env.local` y completá tus credenciales (no commitees secretos):

```ini
SUPABASE_HOST=aws-1-us-east-2.pooler.supabase.com
SUPABASE_PORT=6543
SUPABASE_DB_NAME=postgres
SUPABASE_USER=<tu_usuario>
SUPABASE_PASSWORD=<tu_password>
OFFERS_TABLE_NAME=oil_offers_export
ORIGIN_URL=https://www.se.gob.ar/comercio_exterior_liquidos/oferta_com_ext_expo_store.php
```

2. Creá un entorno virtual e instalá dependencias:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Ejecutá el ingestor:

```bash
python ingest.py
```

## GitHub Actions

Workflows incluidos:

- `update-readme.yml`: actualiza la sección dinámica del README cada 15 minutos (y manualmente).

Configurá los Secrets (Settings → Secrets and variables → Actions → Secrets):

- `SUPABASE_HOST`
- `SUPABASE_PORT` (ej.: 6543)
- `SUPABASE_DB_NAME` (ej.: postgres)
- `SUPABASE_USER`
- `SUPABASE_PASSWORD`

Variable opcional (Settings → Secrets and variables → Actions → Variables):

- `OFFERS_TABLE_NAME` (por defecto `oil_offers_export`)

## Notas

- El parser asume que `aaData` es un arreglo de arreglos con un orden de columnas fijo. Si la fuente cambia, actualizá `parse_row()` en `ingest.py`.
- La inserción usa `INSERT ... ON CONFLICT DO NOTHING` sobre la clave primaria `id` para evitar duplicados.
- La conexión a Supabase usa SSL (`sslmode=require`).
