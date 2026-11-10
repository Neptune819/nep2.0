# Deploy NEP on Vercel Hobby

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
