from typing import Any

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def classify_compound(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def classify_average(average: float) -> str:
    if average >= 0.15:
        return "strongly positive"
    if average >= 0.05:
        return "moderately positive"
    if average <= -0.15:
        return "strongly negative"
    if average <= -0.05:
        return "moderately negative"
    return "neutral"


def analyze_headlines(headlines: list[str]) -> dict[str, Any]:
    if not headlines:
        return {
            "label": "neutral",
            "average_compound": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "items": [],
        }

    items = []
    positive = negative = neutral = 0
    compounds: list[float] = []

    for title in headlines:
        scores = _analyzer.polarity_scores(title)
        compound = scores["compound"]
        compounds.append(compound)
        sentiment = classify_compound(compound)
        if sentiment == "positive":
            positive += 1
        elif sentiment == "negative":
            negative += 1
        else:
            neutral += 1
        items.append(
            {
                "title": title,
                "compound_score": round(compound, 4),
                "sentiment": sentiment,
            }
        )

    average = sum(compounds) / len(compounds)
    return {
        "label": classify_average(average),
        "average_compound": round(average, 4),
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "items": items,
    }
