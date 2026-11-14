from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tavily import TavilyClient

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

app = FastAPI(title="Agent Forge 2h Starter", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


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
