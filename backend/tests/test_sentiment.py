from app.services.sentiment import analyze_headlines, classify_compound


def test_positive_headline():
    assert classify_compound(0.5) == "positive"
    assert classify_compound(-0.5) == "negative"
    assert classify_compound(0.0) == "neutral"


def test_analyze_headlines_empty():
    result = analyze_headlines([])
    assert result["label"] == "neutral"
    assert result["positive_count"] == 0


def test_analyze_headlines_mixed():
    headlines = [
        "Company reports record earnings and strong growth",
        "Stock plunges on disappointing guidance and layoffs",
    ]
    result = analyze_headlines(headlines)
    assert result["positive_count"] >= 1
    assert result["negative_count"] >= 1
    assert len(result["items"]) == 2
