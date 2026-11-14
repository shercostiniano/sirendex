from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from daytona import Daytona


def verify_source_urls(urls: list[str], client: Any | None = None) -> list[dict]:
    """Probe public report URLs in a disposable Daytona sandbox.

    No application secrets are copied into the sandbox. Failures degrade to an
    empty result so source verification never blocks the incident feed.
    """
    safe_urls = [
        url for url in urls[:5]
        if urlsplit(url).scheme in {"http", "https"} and urlsplit(url).netloc
    ]
    if not safe_urls:
        return []

    daytona = client or Daytona()
    sandbox = None
    try:
        sandbox = daytona.create(timeout=60)
        code = f'''import json
import urllib.request

urls = {json.dumps(safe_urls)}
rows = []
for url in urls:
    try:
        request = urllib.request.Request(
            url,
            headers={{"User-Agent": "SpiderDex-SourceVerifier/0.1", "Range": "bytes=0-2048"}},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            rows.append({{
                "url": url,
                "reachable": True,
                "status": response.status,
                "final_url": response.geturl(),
            }})
    except Exception as exc:
        rows.append({{"url": url, "reachable": False, "error": type(exc).__name__}})
print(json.dumps(rows))
'''
        response = sandbox.process.code_run(code, timeout=20)
        if response.exit_code != 0:
            return []
        parsed = json.loads(response.result.strip())
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []
    finally:
        if sandbox is not None:
            try:
                daytona.delete(sandbox)
            except Exception:
                pass
