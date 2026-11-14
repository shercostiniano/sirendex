from __future__ import annotations

import hashlib
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tavily import TavilyClient

from app.incidents import (
    activity_index,
    classify_category,
    dedupe_results,
    is_incident_report,
    mentions_area,
    source_type,
)

from app.sandbox_probe import verify_source_urls

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

app = FastAPI(title="SirenDex", version="0.2.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _live_snapshot(area: str, days: int) -> list[dict]:
    try:
        payload = json.loads((ROOT / "live_snapshot.json").read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if area.split(",", 1)[0].strip().lower() != payload.get("area", "").split(",", 1)[0].strip().lower():
        return []
    snapshot = payload.get("snapshots", {}).get(str(days), {})
    return [dict(item) for item in snapshot.get("incidents", [])]


DEMO_INCIDENTS = [
    {
        "title": "DEMO FIXTURE — Fire response reported near Shibuya Station",
        "category": "fire",
        "summary": "Demonstration data used when live web research is disabled.",
        "source_url": "https://example.com/demo-fire",
        "source_name": "Demo source",
        "source_type": "news",
        "age_days": 1,
        "lat": 35.6595,
        "lng": 139.7005,
    },
    {
        "title": "DEMO FIXTURE — Burglary investigation in the selected area",
        "category": "burglary",
        "summary": "Demonstration data used to verify filtering and map behavior.",
        "source_url": "https://example.com/demo-burglary",
        "source_name": "Demo source",
        "source_type": "news",
        "age_days": 3,
        "lat": 35.6632,
        "lng": 139.6948,
    },
    {
        "title": "DEMO FIXTURE — Assault response reported in the selected area",
        "category": "assault",
        "summary": "Demonstration data used to verify assault filtering and map behavior.",
        "source_url": "https://example.com/demo-assault",
        "source_name": "Demo source",
        "source_type": "news",
        "age_days": 2,
        "lat": 35.6671,
        "lng": 139.7062,
    },
]


def _area_center(area: str) -> tuple[float, float]:
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": area, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": "SpiderDex-Hackathon/0.1"},
            timeout=8,
        )
        response.raise_for_status()
        rows = response.json()
        if rows:
            return float(rows[0]["lat"]), float(rows[0]["lon"])
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        pass
    return 35.6762, 139.6503


def _reverse_area(lat: float, lng: float) -> str:
    response = httpx.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 12},
        headers={"User-Agent": "SpiderDex-Hackathon/0.1"},
        timeout=8,
    )
    response.raise_for_status()
    address = response.json().get("address", {})
    district = address.get("suburb") or address.get("city_district") or address.get("borough")
    city = address.get("city") or address.get("town") or address.get("state")
    parts = [part for part in (district, city) if part]
    return ", ".join(dict.fromkeys(parts)) or "Nearby area"


def _approximate_point(url: str, center: tuple[float, float]) -> tuple[float, float]:
    digest = hashlib.sha256(url.encode()).digest()
    angle = int.from_bytes(digest[:2], "big") / 65535 * math.tau
    radius = 0.004 + int.from_bytes(digest[2:4], "big") / 65535 * 0.018
    return center[0] + math.sin(angle) * radius, center[1] + math.cos(angle) * radius


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/healthz")
def health() -> dict:
    return {"ok": True, "mode": os.getenv("APP_MODE", "fixture")}


@app.get("/api/partners")
def partners() -> dict:
    return {
        "tavily": configured("TAVILY_API_KEY"),
        "daytona": configured("DAYTONA_API_KEY"),
        "nosana": configured("NOSANA_API_KEY"),
        "model": configured("OPENAI_API_KEY"),
        "fixture_safe": True,
    }


@app.get("/api/search")
def search(q: str = Query(min_length=2, max_length=300)) -> dict:
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        if os.getenv("APP_MODE", "fixture") == "fixture":
            return {
                "query": q,
                "fixture": True,
                "answer": "Fixture result: add TAVILY_API_KEY and set APP_MODE=live for current web data.",
                "results": [],
            }
        raise HTTPException(status_code=503, detail="TAVILY_API_KEY is not configured")
    response = TavilyClient(api_key=key).search(
        q,
        search_depth="advanced",
        max_results=5,
        include_answer="basic",
    )
    return {"query": q, "fixture": False, **response}


@app.get("/api/config")
def public_config() -> dict:
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    valid = token.startswith("pk.") and "replace" not in token.lower()
    return {"mapbox_access_token": token if valid else ""}


@app.get("/api/reverse-geocode")
def reverse_geocode(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
) -> dict:
    try:
        return {"area": _reverse_area(lat, lng)}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=502, detail="Unable to resolve that location") from exc


@app.get("/api/incidents")
def incidents(
    area: str = Query(default="Shibuya, Tokyo", min_length=2, max_length=120),
    days: int = Query(default=7, ge=1, le=30),
) -> dict:
    mode = os.getenv("APP_MODE", "fixture")
    key = os.getenv("TAVILY_API_KEY", "").strip()
    center = _area_center(area)
    snapshot_used = False

    if mode == "fixture" or not key:
        rows = [dict(item) for item in DEMO_INCIDENTS]
        fixture = True
    else:
        primary_area = area.split(",", 1)[0].strip()
        tracks = (
            "murder homicide stabbing police",
            "burglary robbery theft heist police",
            "fire blaze arson fire department",
            "assault attack stabbing shooting police",
        )

        def search_track(terms: str) -> list[dict]:
            try:
                response = TavilyClient(api_key=key).search(
                    f'"{primary_area}" {area} {terms}',
                    topic="news",
                    days=days,
                    search_depth="advanced",
                    max_results=5,
                    include_raw_content=False,
                )
                return response.get("results", [])
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=4) as pool:
            candidates = [row for batch in pool.map(search_track, tracks) for row in batch]
        rows = []
        for result in dedupe_results(candidates):
            url = str(result.get("url", ""))
            title = str(result.get("title", "Untitled report"))
            content = " ".join(str(result.get("content", "")).split())[:420]
            if not is_incident_report(title, content) or not mentions_area(area, title, content):
                continue
            lat, lng = _approximate_point(url, center)
            host = httpx.URL(url).host or "Web source"
            rows.append(
                {
                    "title": title,
                    "category": classify_category(title, content),
                    "summary": content,
                    "source_url": url,
                    "source_name": host.removeprefix("www."),
                    "source_type": source_type(url),
                    "age_days": 0,
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                }
            )
        fixture = False
        if not rows:
            rows = _live_snapshot(area, days)
            snapshot_used = bool(rows)

    normalized = []
    for row in rows:
        item = dict(row)
        item["id"] = hashlib.sha256(item["source_url"].encode()).hexdigest()[:12]
        item["location_accuracy"] = "area-level approximation"
        item["source_verified"] = False
        normalized.append(item)

    daytona_status = "skipped"
    checked_count = 0
    verified_count = 0
    if not fixture and not snapshot_used and configured("DAYTONA_API_KEY") and normalized:
        checks = verify_source_urls([item["source_url"] for item in normalized[:5]])
        checked_count = len(checks)
        by_url = {check.get("url"): check for check in checks}
        for item in normalized:
            check = by_url.get(item["source_url"])
            if check:
                item["source_verified"] = bool(check.get("reachable"))
                item["source_status"] = check.get("status")
                verified_count += int(item["source_verified"])
        daytona_status = "completed" if checks else "unavailable"

    score, label = activity_index(normalized)
    return {
        "area": area,
        "days": days,
        "center": {"lat": center[0], "lng": center[1]},
        "activity": {
            "score": score,
            "label": label,
            "name": "Incident Activity Index",
            "explanation": "Category-weighted count of matching public reports in the selected window; not a crime rate.",
        },
        "incidents": normalized,
        "fixture": fixture,
        "partners": {
            "tavily": {
                "status": "fixture" if fixture else ("snapshot" if snapshot_used else "live"),
                "reports": len(normalized),
            },
            "daytona": {
                "status": daytona_status,
                "checked_sources": checked_count,
                "reachable_sources": verified_count,
            },
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Public web reports may be incomplete or inaccurate. Map markers are area-level "
            "approximations, not exact incident locations. This index is not a prediction of danger."
        ),
    }
