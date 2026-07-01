from stocksense import scraper


def test_clean_drops_short_and_blank():
    raw = ["", "   ", "Too short", "Apple beats earnings expectations for Q3"]
    assert scraper._clean(raw) == ["Apple beats earnings expectations for Q3"]


def test_clean_dedupes_preserving_order():
    headline = "Apple unveils new product lineup at fall event"
    other = "Analysts raise price targets across the tech sector"
    assert scraper._clean([headline, other, headline]) == [headline, other]


def test_clean_handles_none_entries():
    assert scraper._clean([None, "A genuinely long enough headline string"]) == [
        "A genuinely long enough headline string"
    ]
