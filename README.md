# SirenDex — Live Incident Map

SirenDex monitors recent public incident reports around a selected area and displays them through the SpiderDex map UI.

## What it does

- Searches four live incident tracks: murder, burglary/theft, fire/arson, and assault.
- Deduplicates and filters reports to the requested district.
- Classifies reports and plots **area-level approximate markers** on a dark map.
- Calculates an explainable **Incident Activity Index**.
- Refreshes every five minutes and supports browser notifications for newly discovered report IDs.
- Reverse-geocodes the user's location without persisting coordinates.

## Partner integrations

- **Tavily:** four parallel, area-specific news investigations with freshness windows and cited source URLs.
- **Daytona:** checks untrusted report URLs inside a disposable sandbox; no app secrets enter the sandbox.
- **CodeAF:** development harness used during the hackathon build.

## Safety contract

This product reports public-source activity; it does not predict crime or individual behavior. Public reports may be incomplete or inaccurate. Markers are deliberately approximate and must not be interpreted as exact incident locations. Every result links to its source.

## Run locally

```bash
cp .env.example .env
# Add TAVILY_API_KEY, DAYTONA_API_KEY, and a public MAPBOX_ACCESS_TOKEN (pk.…); set APP_MODE=live
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8088
```

Open <http://127.0.0.1:8088>.

## Verify

```bash
uv run pytest -q
uv run ruff check app tests
```

For an offline stage fallback, set `APP_MODE=fixture`. Fixture entries are visibly labeled `DEMO FIXTURE`.

## Daytona live preview deployment

Daytona exposes any HTTP service listening on `0.0.0.0`. This deployment uses port `8000`:

```bash
# Inside the sandbox, after uploading or cloning the repository
cd /home/daytona/sirendex
uv sync --frozen --no-dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expose the port with the Daytona Python SDK:

```python
from daytona import Daytona

sandbox = Daytona().get("YOUR_SANDBOX_ID")
sandbox.set_public(True)              # Public hackathon demo
sandbox.set_auto_pause_interval(0)    # Do not pause during judging
preview = sandbox.get_preview_link(8000)
print(preview.url)
```

Set `TAVILY_API_KEY`, `DAYTONA_API_KEY`, and `MAPBOX_ACCESS_TOKEN` with `sandbox.update_env(...)`; never upload `.env`. For a private preview, leave the sandbox private and use `create_signed_preview_url(8000, expires_in_seconds=...)`.

**Current account limitation:** Daytona Tier 1/2 firewall policy permits essential package registries but blocks arbitrary outbound HTTPS, including Tavily and Nominatim. The hosted demo therefore runs with `APP_MODE=fixture`. On Tier 3/4, set `APP_MODE=live` and restart the server session. Mapbox tiles still work because the visitor's browser requests them directly.

The current demo has auto-pause and TTL disabled. Stop or delete the sandbox after judging to avoid continued credit usage.

## Docker / Railway

The included `Dockerfile` runs the app on Railway's injected `$PORT`.
