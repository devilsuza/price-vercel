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

The portal sends `print_format: "THERMAL"` for normal label printing and
`print_format: "S3"` for A4(S3) printing when it creates a print job. The local
print bridge receives the same value from `GET /api/print-jobs/next`. The API
also accepts the legacy values `normal` and `a4_s3` and stores them as
`THERMAL` and `S3`, respectively.
