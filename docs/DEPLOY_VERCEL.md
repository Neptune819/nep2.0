# Deploy NEP on Vercel Hobby

## Current live deployment (verified 2026-11-10)

- Public URL: https://nep-anime-recommend.vercel.app
- Main application: https://nep-anime-recommend.vercel.app/app
- Vercel project: https://vercel.com/lium83089-3989/nep-anime-recommend
- Source: https://github.com/Neptune819/nep2.0 (main)
- Account plan verified through Vercel's API: `hobby`.
- Deployment status: `Ready`; function region: Singapore (`sin1`).

The project was published through the official Vercel CLI, without a GitHub
integration. Pushing to GitHub alone does not update the live website. To update
the linked source directory after editing, run:

```powershell
npx --yes vercel@48.12.1 deploy --prod --yes
```

The source project and the deployment checkout both have an ignored
`.vercel/project.json` linking them to this same Vercel project. CLI login is
stored in Vercel's normal user configuration directory, not in the repository.
If the CLI cannot reach Vercel, use the machine's configured network proxy for
that shell; do not disable HTTPS verification.

Read-only live verification is available at `.code/test_live.py`. It checked
Chinese/Japanese/English search, seed and history recommendations, watched/year/
tag exclusions, media listing endpoints, and a public Bangumi collection import.
The deployed source file list was also checked: no `.env` files were uploaded.

## Setup on another account

Select the personal **Hobby** plan and import the deployment branch. Vercel
detects Flask from `requirements.txt` and `app.py`. The included `vercel.json`
sets Singapore (`sin1`), a 300-second function duration, and a build command
that copies `static/` to `public/static/` for the CDN. Python is pinned to 3.12.

The app can read `data/anime_cache.json.gz` directly. It does not fetch the
catalogue from AniList or write beside the source on a cold start. The large
uncompressed cache and private `.env` are excluded from uploads.

After deployment, test `/health`, `/app`, a Chinese-title search, and a real
recommendation. Also test `/api/bgm/list` and `/api/background/list`, because
serverless bundles are read-only.

## Storage and platform limits

Personal ratings, watched lists, and recommendation filters remain in the
visitor's browser. A new domain has separate browser storage: export a backup
from the old domain and import it into the new one.

Custom BGM/background uploads use the function instance's temporary directory.
They can disappear on instance restart or be absent on another instance. They
are not cloud-synced personal storage. Vercel also limits function request and
response payloads to 4.5 MB; large uploads or exports may exceed that limit.

Hobby is intended for personal, non-commercial projects and includes usage
limits. Check the dashboard before promoting the site to a large audience.

References:
- https://vercel.com/docs/frameworks/backend/flask
- https://vercel.com/docs/functions/runtimes/python
- https://vercel.com/docs/functions/limitations
- https://vercel.com/docs/plans/hobby
