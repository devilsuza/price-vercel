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

## Storage warning

Vercel's function filesystem is not permanent. This project writes SQLite and temporary uploaded Excel files under `/tmp`, which allows the portal to run, but price updates, imports, aliases, and print jobs are not guaranteed to remain after a cold start, redeployment, or a different function instance.

For permanent shared data, the SQLite tables must be moved to an external database.
