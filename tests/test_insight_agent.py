"""Call guidance generation, including the shapes the database can produce."""

import pytest

from src.agents.insight_agent import InsightAgent

FULL_CONTEXT = {
    "customer_id": 1,
    "name": "Ada",
    "company": "Engines",
    "industry": "Technology",
    "engagement_score": 0.85,
    "enrollments": [{"product": "Premium Suite"}, {"product": "Premium Suite"}],
    "recent_engagements": [{"type": "support_ticket"}],
    "feedback_history": [{"sentiment": "positive", "text": "great tool"}],
}


@pytest.fixture
def agent():
    return InsightAgent()


def test_guidance_requires_a_context(agent):
    assert agent.generate_call_guidance(None) is None
    assert agent.generate_call_guidance({}) is None
    assert agent.generate_call_guidance("not a context") is None


def test_guidance_covers_the_full_context(agent):
    guidance = agent.generate_call_guidance(FULL_CONTEXT)
    points = " ".join(guidance["key_talking_points"])
    assert "Technology" in points
    assert points.count("Premium Suite") == 1  # duplicates are collapsed
    assert "high engagement" in points
    assert guidance["tone"] == "collaborative and partnership-focused"
    assert guidance["engagement_strategy"].startswith("Support expansion")


def test_a_bare_context_still_yields_usable_guidance(agent):
    guidance = agent.generate_call_guidance({"customer_id": 2})
    assert guidance["key_talking_points"] == ["Build rapport and understand customer needs"]
    assert guidance["recommended_actions"] == ["Introduce key products/services"]
    assert guidance["engagement_strategy"].startswith("Re-engagement")
    assert guidance["potential_objections"]


def test_null_engagement_type_does_not_crash(agent):
    """`engagement_type` is nullable, and used to raise AttributeError."""
    guidance = agent.generate_call_guidance(
        {"customer_id": 3, "recent_engagements": [{"type": None, "date": None}]}
    )
    assert guidance["engagement_strategy"].startswith("Growth strategy")


def test_null_engagement_score_does_not_crash(agent):
    guidance = agent.generate_call_guidance({"customer_id": 4, "engagement_score": None})
    assert guidance["tone"] == "friendly and consultative"


def test_non_numeric_engagement_score_is_ignored(agent):
    guidance = agent.generate_call_guidance({"customer_id": 5, "engagement_score": "high"})
    assert guidance["tone"] == "friendly and consultative"


@pytest.mark.parametrize("value", [None, "unexpected", 42, [None, "x"], {}])
def test_malformed_related_collections_are_ignored(agent, value):
    guidance = agent.generate_call_guidance(
        {
            "customer_id": 6,
            "enrollments": value,
            "recent_engagements": value,
            "feedback_history": value,
        }
    )
    assert guidance["key_talking_points"]
    assert guidance["potential_objections"]


def test_negative_feedback_drives_the_recommendation(agent):
    guidance = agent.generate_call_guidance(
        {
            "customer_id": 7,
            "engagement_score": 0.2,
            "feedback_history": [{"sentiment": "negative", "text": "too expensive"}],
        }
    )
    assert "Address concerns and offer solutions" in guidance["recommended_actions"]
    assert any("too expensive" in objection for objection in guidance["potential_objections"])


@pytest.mark.parametrize(
    "score,tone",
    [
        (0.95, "collaborative and partnership-focused"),
        (0.6, "professional and solutions-oriented"),
        (0.1, "friendly and consultative"),
    ],
)
def test_tone_follows_engagement(agent, score, tone):
    assert agent.generate_call_guidance({"customer_id": 8, "engagement_score": score})["tone"] == tone
