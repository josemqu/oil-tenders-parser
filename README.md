# Ingesta de Ofertas de Exportación de Petróleo (Argentina)

Este repositorio ingesta el listado público de ofertas de exportación de petróleo de Argentina cada 15 minutos y almacena los registros nuevos en una base de datos Postgres (Supabase).


- Descarga el feed JSON y parsea cada fila (empresa, producto, volumen, fechas, fórmula de precio, ubicación, notas, cuenca, enlace al PDF, etc.).
- Limpia campos HTML (reemplaza `<br>` y remueve etiquetas) y extrae la URL del PDF desde el botón `onclick`.
- Deduplica por el `id` numérico de la oferta e inserta solo registros nuevos en Postgres.
- Se ejecuta mediante GitHub Actions cada 15 minutos.
  
## Estado (dinámico)
 
Este bloque se actualiza automáticamente con los últimos registros, la fecha de la última actualización y un indicador de recencia.

<!-- OFFERS_STATUS:START -->

Última actualización: 26/09/2025 15:49
<!-- badges:start -->
![Total registros](https://img.shields.io/badge/total__registros-2418-blue?style=flat-square) ![Recencia](https://img.shields.io/badge/recencia-hace_168h_3m-red?style=flat-square)
<!-- badges:end -->

### Últimos 5 registros

<table>
  <colgroup>
    <col style="width:8%">
    <col style="width:24%">
    <col style="width:38%">
    <col style="width:12%">
    <col style="width:8%">
    <col style="width:10%">
  </colgroup>
  <thead>
    <tr><th style="text-align:right">ID</th><th>Compañía</th><th>Producto</th><th>Publ.</th><th>Vigente</th><th>Creado</th></tr>
  </thead>
  <tbody>
    <tr><td style="text-align:right">2960</td><td>Pan American Energy (Sucursal Argentina) LLC</td><td>GASOLINAS, EXCEPTO LAS DE AVIACIÓN Sin Plomo, Otras</td><td>26/09/2025 15:09</td><td>No</td><td>26/09/2025 18:49</td></tr>
    <tr><td style="text-align:right">2959</td><td>REFINERÍA DEL NORTE S.A.</td><td>GASOIL</td><td>26/09/2025 15:09</td><td>No</td><td>26/09/2025 18:49</td></tr>
    <tr><td style="text-align:right">2958</td><td>Pan American Energy (Sucursal Argentina) LLC</td><td>GASOLINAS, EXCEPTO LAS DE AVIACIÓN Sin plomo, de RON inferior o igual a 92</td><td>26/09/2025 15:09</td><td>No</td><td>26/09/2025 18:36</td></tr>
    <tr><td style="text-align:right">2957</td><td>Capex S.A.</td><td>ACEITES CRUDOS DE PETRÓLEO Otros</td><td>23/09/2025 17:09</td><td>No</td><td>26/09/2025 18:36</td></tr>
    <tr><td style="text-align:right">2956</td><td>YPF S.A.</td><td>ACEITES CRUDOS DE PETRÓLEO Otros</td><td>23/09/2025 14:09</td><td>No</td><td>26/09/2025 18:36</td></tr>
  </tbody>
</table>

### Ofertas por día (últimos 15 días)

```
03/10 |     0 
02/10 |     0 
01/10 |     0 
30/09 |     0 
29/09 |     0 
28/09 |     0 
27/09 |     0 
26/09 |     3 ██████████████████████████████
25/09 |     0 
24/09 |     0 
23/09 |     2 ████████████████████
22/09 |     0 
21/09 |     0 
20/09 |     1 ██████████
19/09 |     0 
```

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
ORIGIN_URL=<tu_url_de_fuente>
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

### Cómo se calcula la recencia

- La recencia se basa en la diferencia entre la hora actual y la última inserción (`created_at`) registrada.
- Umbrales por defecto (configurables con variables de entorno del workflow):
  - `FRESH_MINUTES` = 30 → se muestra como "al día".
  - `RECENT_MINUTES` = 120 → se muestra como "reciente" si supera 30 y hasta 120 minutos.
  - Más de `RECENT_MINUTES` → se muestra como badge en color rojo con el texto "hace Xh Ym".
