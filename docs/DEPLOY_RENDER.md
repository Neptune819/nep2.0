# Deploy NEP on Render Free

The repository includes `render.yaml` and a compressed public anime snapshot at
`data/anime_cache.json.gz`. The uncompressed `anime_cache.json` is intentionally
ignored by Git. `boot.py` expands the snapshot before Gunicorn starts; it never
needs a live AniList fetch during a cold start.

## Before deploying

1. Confirm that the compressed snapshot is up to date after changes to the
   local anime cache. Rebuild it from the project root with Python:

   ```python
   import gzip
   import shutil

   with open("data/anime_cache.json", "rb") as source:
       with gzip.open("data/anime_cache.json.gz", "wb", compresslevel=6) as target:
           shutil.copyfileobj(source, target)
   ```

2. Commit the deployable code, `render.yaml`, and
   `data/anime_cache.json.gz` to the branch that Render will use. Keep `.env`
   and private tokens out of the repository.
3. In Render, create a **Blueprint** from the connected GitHub repository.
   Render reads the root `render.yaml` and creates a **Free** Python web
   service. Alternatively, create a Web Service manually with build command
   `pip install -r requirements.txt`, start command `python boot.py`, and
   health check `/health`. Set `PYTHON_VERSION` to `3.12.11` if creating it
   manually.
4. Once deployed, check `/health` and then visit `/app`. Try a search and a
   recommendation; a healthy `/health` response alone does not exercise the
   recommender.

## Free-plan limits

Render Free has 512 MB RAM. The recommender uses roughly 312 MB RSS when
initialized locally with the current snapshot, so test recommendations and
exports under actual load. The service sleeps after 15 minutes of inactivity;
the next visitor may wait about a minute while it starts. The local filesystem
is ephemeral, so user-uploaded background images and BGM files disappear
after restarts. Browser `localStorage` belongs to each origin, so visitors
moving from the old IP address to the new HTTPS domain must import a backup
of their personal lists; those records do not migrate automatically.

Sources: [Render Free](https://render.com/docs/free),
[Blueprint spec](https://render.com/docs/blueprint-spec),
[Python version](https://render.com/docs/python-version).
