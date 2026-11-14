from __future__ import annotations

import math
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CATEGORY_KEYWORDS = {
    "murder": ("murder", "homicide", "killed", "fatal stabbing", "dead body", "殺人", "死亡"),
    "burglary": (
        "burglary", "robbery", "break-in", "theft", "heist", "stolen", "shoplifting", "強盗", "窃盗", "侵入"
    ),
    "fire": ("fire", "blaze", "arson", "fire crews", "火災", "放火"),
    "assault": ("assault", "attack", "battery", "shooting", "stabbing", "暴行", "襲撃"),
}
GENERIC_TITLE_KEYWORDS = (
    "assault", "attack", "arrested", "police investigate", "crime ring", "shooting", "stabbing", "事故", "逮捕"
)
SOCIAL_DOMAINS = ("x.com", "twitter.com", "reddit.com", "facebook.com", "instagram.com", "tiktok.com")
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}


def classify_category(title: str, content: str) -> str:
    text = f"{title} {content}".lower()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in text for word in words):
            return category
    return "assault"


def is_incident_report(title: str, content: str) -> bool:
    title_text = title.lower()
    specific = tuple(word for words in CATEGORY_KEYWORDS.values() for word in words)
    if any(word in title_text for word in specific + GENERIC_TITLE_KEYWORDS):
        return True
    content_text = content.lower()[:300]
    matches = sum(1 for word in specific if word in content_text)
    return matches >= 2


def mentions_area(area: str, title: str, content: str) -> bool:
    primary = area.split(",", 1)[0].strip().lower()
    if len(primary) < 3:
        return True
    return primary in f"{title} {content[:500]}".lower()


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMS])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def dedupe_results(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        key = canonical_url(str(row.get("url", "")))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def source_type(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return "social" if any(host == d or host.endswith(f".{d}") for d in SOCIAL_DOMAINS) else "news"


def activity_index(incidents: list[dict]) -> tuple[int, str]:
    weights = {"murder": 30, "burglary": 16, "fire": 14, "assault": 8}
    raw = 0.0
    for incident in incidents:
        age = max(0.0, float(incident.get("age_days", 0)))
        freshness = math.exp(-age / 5)
        raw += weights.get(str(incident.get("category")), 8) * freshness
    score = min(100, round(raw))
    label = "LOW" if score < 20 else "MODERATE" if score < 45 else "ELEVATED" if score < 70 else "HIGH"
    return score, label
