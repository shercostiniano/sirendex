from app.incidents import (
    activity_index,
    classify_category,
    dedupe_results,
    is_incident_report,
    mentions_area,
    source_type,
)


def test_classifies_supported_categories() -> None:
    assert classify_category("Police investigate homicide downtown", "") == "murder"
    assert classify_category("Apartment burglary reported", "") == "burglary"
    assert classify_category("Warehouse fire contained", "") == "fire"
    assert classify_category("Police report an assault downtown", "") == "assault"
    assert classify_category("Police respond to public safety report", "") == "assault"


def test_deduplicates_canonical_urls() -> None:
    rows = [
        {"url": "https://news.example/story?utm_source=x", "title": "A"},
        {"url": "https://news.example/story", "title": "A duplicate"},
    ]
    assert len(dedupe_results(rows)) == 1


def test_social_sources_are_labeled() -> None:
    assert source_type("https://www.reddit.com/r/tokyo/comments/1") == "social"
    assert source_type("https://x.com/example/status/1") == "social"
    assert source_type("https://example.com/news/1") == "news"


def test_rejects_generic_pages_that_only_mention_incidents_in_recommendations() -> None:
    assert is_incident_report("Apartment heist investigated in Shibuya", "")
    assert is_incident_report("Local update", "Fire crews contained a warehouse blaze.")
    assert not is_incident_report("Shibuya culture never stands still", "Recommended: police launch unrelated raid")
    assert not is_incident_report("Shibuya crossing comes to Singapore", "Travel and culture story")


def test_requires_the_specific_requested_area() -> None:
    assert mentions_area("Shibuya, Tokyo", "Tokyo report", "Police investigated an incident in Shibuya Ward")
    assert not mentions_area("Shibuya, Tokyo", "France supermarket attack", "Unrelated international report")


def test_activity_index_is_bounded_and_explainable() -> None:
    incidents = [
        {"category": "murder", "age_days": 0},
        {"category": "burglary", "age_days": 2},
        {"category": "fire", "age_days": 8},
    ]
    score, label = activity_index(incidents)
    assert 0 <= score <= 100
    assert label in {"LOW", "MODERATE", "ELEVATED", "HIGH"}
    assert score > activity_index([])[0]
