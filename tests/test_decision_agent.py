"""Scoring, sentiment and follow-up selection."""

import pytest

from src.agents.decision_agent import DecisionAgent
from src.database import CallStatus, OutreachRepository

TRANSCRIPT = (
    "Agent: Hi Ada, thanks for taking my call.\n"
    "User: Sure, this sounds excellent and really helpful.\n"
    "Agent: Great, I will follow up by email.\n"
    "User: Yes please, thanks.\n"
)

NEGATIVE_TRANSCRIPT = (
    "Agent: Hi, do you have a moment?\n"
    "User: Honestly this is too expensive and I am frustrated. Stop calling.\n"
)


@pytest.fixture
def agent():
    return DecisionAgent()


def test_sentiment_only_counts_customer_turns(agent):
    # The agent's own line contains "great"; only the customer's words count.
    sentiment = agent._analyze_sentiment({"transcript": TRANSCRIPT})
    assert sentiment["overall"] == "positive"
    assert sentiment["positive_signals"] >= 2
    assert sentiment["negative_signals"] == 0


def test_negative_transcript_is_detected(agent):
    sentiment = agent._analyze_sentiment({"transcript": NEGATIVE_TRANSCRIPT})
    assert sentiment["overall"] == "negative"
    assert sentiment["confidence"] > 0.5


def test_missing_transcript_is_unknown_not_neutral(agent):
    sentiment = agent._analyze_sentiment({})
    assert sentiment == {
        "overall": "unknown",
        "confidence": 0.0,
        "positive_signals": 0,
        "negative_signals": 0,
        "key_phrases": [],
    }


def test_transcript_without_role_prefixes_is_still_scored(agent):
    sentiment = agent._analyze_sentiment({"transcript": "this is excellent, thanks"})
    assert sentiment["overall"] == "positive"


def test_confidence_is_capped(agent):
    speech = "User: " + " ".join(["great", "love", "excellent", "perfect", "interested", "helpful"])
    assert agent._analyze_sentiment({"transcript": speech})["confidence"] <= 0.95


@pytest.mark.parametrize(
    "call_data,expected_score,successful",
    [
        ({"status": "failed", "duration": 0}, 0, False),
        ({"status": "completed", "duration": 20}, 30, False),
        ({"status": "completed", "duration": 60}, 50, False),
        ({"status": "completed", "duration": 120}, 70, True),
        (
            {
                "status": "completed",
                "duration": 168,
                "customer_engaged": True,
                "call_successful": "success",
            },
            100,
            True,
        ),
    ],
)
def test_success_scoring_thresholds(agent, call_data, expected_score, successful):
    success = agent._assess_success(call_data)
    assert success["success_score"] == expected_score
    assert success["successful"] is successful


def test_score_never_exceeds_one_hundred(agent):
    success = agent._assess_success(
        {
            "status": "completed",
            "duration": 10_000,
            "customer_engaged": True,
            "call_successful": "success",
        }
    )
    assert success["success_score"] == 100


def test_failed_call_is_recommended_for_retry(agent):
    analysis = agent.analyze_call_outcome({"status": "failed", "duration": 0})
    assert analysis["follow_up_recommendation"]["type"] == "retry"
    assert analysis["next_action"] == "Schedule call retry within 24 hours"
    assert analysis["priority_level"] == "high"


def test_strong_call_is_recommended_for_a_meeting(agent):
    analysis = agent.analyze_call_outcome(
        {
            "status": "completed",
            "duration": 168,
            "customer_engaged": True,
            "transcript": TRANSCRIPT,
            "engagement_score": 0.9,
        }
    )
    assert analysis["follow_up_recommendation"]["type"] == "follow_meeting"
    assert analysis["sentiment_analysis"]["overall"] == "positive"
    assert analysis["success_indicator"]["successful"] is True


def test_analyze_survives_an_empty_outcome(agent):
    analysis = agent.analyze_call_outcome(None)
    assert analysis["success_indicator"]["success_score"] == 0
    assert analysis["sentiment_analysis"]["overall"] == "unknown"
    # An unknown status is not a confirmed failure, so it gets an email, not a retry.
    assert analysis["next_action"] == "Send personalized follow-up email"


@pytest.mark.parametrize(
    "duration,expected",
    [("168", 168), (168.9, 168), (None, 0), ("n/a", 0), (True, 0), (-5, 0), ([], 0)],
)
def test_durations_from_providers_are_coerced(agent, duration, expected):
    analysis = agent.analyze_call_outcome({"status": "completed", "duration": duration})
    assert analysis["duration"] == expected


def test_a_string_duration_still_scores_the_call(agent):
    assert agent._assess_success({"status": "completed", "duration": "150"})["success_score"] == 70


def test_a_non_string_transcript_does_not_crash(agent):
    sentiment = agent._analyze_sentiment({"transcript": ["User: excellent"]})
    assert sentiment["overall"] == "positive"


def test_a_non_numeric_engagement_score_does_not_crash(agent):
    analysis = agent.analyze_call_outcome(
        {"status": "completed", "duration": 168, "customer_engaged": True, "engagement_score": "high"}
    )
    assert analysis["priority_level"] == "medium"


def test_key_phrases_are_the_longest_sentences(agent):
    phrases = agent._extract_key_phrases(TRANSCRIPT)
    assert len(phrases) <= 3
    assert all(len(phrase) > 10 for phrase in phrases)
    assert not any(phrase.startswith("Agent:") for phrase in phrases)


def test_log_decision_persists_the_analysis(db, customer_factory):
    repository = OutreachRepository(db)
    customer_id = customer_factory()
    call_id = repository.create_call_record(customer_id=customer_id)
    agent = DecisionAgent(db, repository=repository)

    analysis = agent.analyze_call_outcome(
        {
            "call_id": "sim_1",
            "customer_id": customer_id,
            "status": "completed",
            "duration": 168,
            "customer_engaged": True,
            "transcript": TRANSCRIPT,
        }
    )
    assert agent.log_decision(call_id, analysis) is True

    stored = repository.get_call_record(call_id)
    assert stored["status"] == CallStatus.COMPLETED.value
    assert stored["duration_seconds"] == 168
    assert stored["sentiment"] == "positive"
    assert stored["success_score"] == analysis["success_indicator"]["success_score"]
    assert stored["priority"] == analysis["priority_level"]


def test_log_decision_without_a_record_is_a_no_op(db):
    agent = DecisionAgent(db)
    assert agent.log_decision(None, {"call_status": "completed"}) is False
    assert agent.log_decision(1, None) is False
