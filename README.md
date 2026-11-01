# Store Price Portal - Vercel Flask Edition

## Fixed deployment structure

Vercel automatically detects the Flask instance named `app` in the repository-root `app.py`. Do not add a `functions.app.py` pattern to `vercel.json`; `functions` patterns are for file-based Python functions inside `api/`.

## Deploy from GitHub

1. Upload the contents of this folder to the GitHub repository root.
2. Remove the old `vercel.json` from GitHub if it still exists.
3. Confirm these root files exist:
   - `app.py`
   - `requirements.txt`
   - `pyproject.toml`
4. Vercel Project Settings:
   - Framework Preset: Other
   - Root Directory: `./`
   - Build Command: leave blank
   - Output Directory: leave blank
   - Install Command: leave blank/default
5. Redeploy with **Redeploy without cache**.
6. Test `/api/health` after deployment.

## Persistent database on Vercel (Supabase PostgreSQL)

Local development uses SQLite when `DATABASE_URL` is not set. Vercel requires
Supabase PostgreSQL and will refuse to start if `DATABASE_URL` is missing,
instead of silently saving imported data to disposable function storage.

1. Create a Supabase project and open **Connect** (or **Project Settings →
   Database**).
2. Copy the **Transaction pooler** connection string. Use the pooler rather
   than a direct connection for Vercel serverless functions. Keep the password
   private; do not put the URL in source code.
3. In **Vercel → Project → Settings → Environment Variables**, add
   `DATABASE_URL` with that connection string. Add it to every environment
   where the app should use PostgreSQL (Production, Preview, and/or Development).
   The URL should include SSL settings if Supabase's connection screen specifies
   them.
4. Redeploy. On startup, the app creates or updates its `products`,
   `ean_aliases`, and `print_jobs` tables and seeds the bundled master data.
   Imported products, prices, aliases, and print jobs are then saved in
   Supabase and survive Vercel cold starts and redeployments.
5. Visit `/api/health`; it should return HTTP 200 with `"database": "postgres"`
   and `"storage": "external"`. A missing or unreachable database returns an
   error instead of reporting healthy temporary storage.

When `DATABASE_URL` is set but the database connection fails, the app reports
the error rather than silently switching to temporary SQLite.

### Moving existing price data

The bundled master catalog is seeded automatically, but existing price updates
from an old SQLite database are not transferred automatically. Export those
products to Excel or CSV with columns for the article/barcode, name, EAN aliases
(if available), and prices. In the deployed portal, use the Excel import flow
in **master** mode to merge the exported catalog without clearing blank fields.
Keep a backup and verify a few articles and aliases after importing. The old
Vercel `/tmp` database may already have been discarded by a cold start or
redeploy, so export it before changing deployments if it is still available.

Without `DATABASE_URL`, local development continues to use `store_prices.db`.
The original uploaded Excel/CSV file is temporary and is deleted after a
successful import; the records imported from it are persistent in Supabase.

### Print format values

The portal sends `print_format: "THERMAL"` for normal label printing,
`print_format: "NORMAL_QR"` for the Epson bridge's NORMAL_QR layout, and
`print_format: "S3"` for A4(S3) printing when it creates a print job. The local
print bridge receives the same value from `GET /api/print-jobs/next`; configure
the bridge to handle `NORMAL_QR` to print that layout. The API also accepts the
legacy values `normal` and `a4_s3` and stores them as `THERMAL` and `S3`,
respectively.

### Connecting a second printer PC

The print dialog lets you choose **EPSON** (`printer1`) or **HP LaserJet**
(`printer2`). Each PC must run its own local print bridge and have its printer
driver installed. The portal routes each queued job only to the matching
bridge.

EPSON offers `THERMAL`, `NORMAL_QR`, and `S3`. The included
`epson_print_bridge.py` uses the selected job UOM for all three layouts, printing
it as `KZ/<UOM>` (for example `KZ/CX`, `KZ/EMB`, or `KZ/UN`). Configure
`print_bridge_config.json` beside the script by copying
`print_bridge_config.example.json`, then set `portal_url`, `bridge_key`, and the
Windows `printer_name`. Do not commit the real bridge key. Install the bridge
dependencies on the printer PC with `py -m pip install Pillow pywin32
"qrcode[pil]"`, then start it with `run_epson_bridge.bat`.

### Power SKU and KVI articles

Managers can import separate Power SKU and KVI spreadsheets from **1C. Power
SKU / KVI Article List Upload**. These files only replace the article category
membership; map the article code and optionally name/EAN. Prices are read from
the existing Daily Price Update values, which are not overwritten or deleted.
Uploading a replacement file removes prior membership in that same category
while preserving the products and prices. The existing Master upload also
accepts an optional article-category column containing `POWER SKU`, `KVI`, or
`NORMAL`. Scanned products show their category; Power SKU/KVI show the four
daily prices and can only be queued as `NORMAL_QR` to EPSON. The API enforces
that special items print the selected current daily price and rejects other
formats. Ordinary items continue to use Normal/S3.

HP LaserJet offers `DISCOUNT_A4`,
`NORMAL_A4_LANDSCAPE`, `NORMAL_A4_PORTRAIT`, `PROMOTION_A4`, and
`PROMOTION_A4_S3`. The selected ID is included as `print_format` in the
queued job. The HP bridge must implement the matching layouts; this repository
contains the portal/API, not the local bridge's page-layout or printing code.

1. Keep `PRINT_BRIDGE_KEY` configured in Vercel and configure the same key in
   both bridge installations. Do not share or commit the key publicly.
2. On the existing PC, keep the current bridge setup. If its bridge supports
   `X-Print-Bridge-Id`, set it to `printer1`; requests without this header
   continue to be treated as `printer1`.
3. On the second PC, install/configure the print bridge and its printer driver.
   Point it at the deployed portal's `/api/print-jobs/next` endpoint and set
   `X-Print-Bridge-Id: printer2` on its polling requests. Send
   `X-Print-Bridge-Key: <same configured key>` as before.
4. The bridge must send those same two headers when reporting a job to
   `/api/print-jobs/<job_id>/complete`. Start the bridge and verify the
   HP LaserJet is online before selecting it in the portal.

The bridge program itself is not part of this repository. If the bridge on the
second PC cannot set `X-Print-Bridge-Id` on both polling and completion
requests, it needs a configuration update or a compatible bridge client; merely
installing the existing unmodified bridge on both PCs will not separate their
queues.

For the supplied `hp_laserjet_promotion_bridge.py`, this repository includes
`hp_laserjet_bridge_printer2.py` and `run_hp_laserjet_printer2.bat`. Copy both
beside the original bridge and `hp_laserjet_config.json`, then start the bridge
with `run_hp_laserjet_printer2.bat`. The wrapper adds the `printer2` ID to both
polling and completion requests without changing the existing print layouts.
The supplied bridge currently handles Promotion A4 and Promotion A4 (S3);
other HP formats require print-layout code in the original bridge.
