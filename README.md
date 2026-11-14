# Agent Forge — two-hour starter

A deliberately small, offline-first FastAPI app with a visible sponsor readiness panel and a Tavily search endpoint.

## Start

```bash
cp .env.example .env
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8088
```

Open <http://127.0.0.1:8088>. Run tests with `uv run pytest -q`.

## Key rule

Keep `APP_MODE=fixture` until the full UI path works. Add one sponsor integration at a time, make one real smoke call, then bake the successful response into a fixture for the stage demo.

## Partner roles

- **Tavily:** real-time search/extract/crawl/research. Core integration candidate.
- **Daytona:** isolate untrusted or generated code. Use only if sandbox execution is part of the product story.
- **Nosana:** GPU deployment or OpenAI-compatible open-model inference. Use only if the idea actually needs compute.
- **CodeAF:** coding harness for building the project; it need not be embedded in the app.

Reference material is in `../reference/60s-Pulse`, `../reference/CodeAF`, and `../winning-playbook.txt`.
