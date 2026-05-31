"""
Phase 7: Feedback Engine
AI Relationship Manager — Paytm Money Limited

Stores per-client star ratings to JSON.
Calculates rolling averages per query type.
Signals when a re-answer should be triggered (rating <= 3).
"""

import json
import os
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
FEEDBACK_DIR = os.path.join(PROJECT_ROOT, "data", "feedback")
os.makedirs(FEEDBACK_DIR, exist_ok=True)


def _feedback_path(client_id: str) -> str:
    return os.path.join(FEEDBACK_DIR, f"{client_id}_feedback.json")


def _load(client_id: str) -> dict:
    path = _feedback_path(client_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"client_id": client_id, "ratings": []}


def _save(client_id: str, data: dict):
    with open(_feedback_path(client_id), "w") as f:
        json.dump(data, f, indent=2)


# ── Public API ─────────────────────────────────────────────────

def save_rating(client_id: str, question: str, answer: str, rating: int):
    """
    Save a star rating (1-5) for a question/answer pair.
    Called from Streamlit after user selects a star rating.
    """
    data = _load(client_id)
    data["ratings"].append({
        "timestamp":  datetime.now().isoformat(),
        "question":   question,
        "answer":     answer[:300],   # truncate for storage
        "rating":     rating,
    })
    _save(client_id, data)


def should_reanswer(rating: int) -> bool:
    """Returns True if the rating is low enough to trigger a re-answer."""
    return rating <= 3


def get_reanswer_prompt(question: str, original_answer: str, rating: int) -> str:
    reason_map = {
        1: "completely unhelpful",
        2: "mostly unhelpful", 
        3: "only partially helpful",
    }
    reason = reason_map.get(rating, "unsatisfactory")

    # Detect query type and tailor the improvement request
    q = question.lower()

    if any(w in q for w in ["worst", "best", "performing", "p&l", "loss", "gain"]):
        improvement = (
            "Your improved answer must add:\n"
            "1. WHY this stock is performing this way — business/market reasons\n"
            "2. What the client should consider — hold, average down, or exit\n"
            "3. Specific price levels or events to watch\n"
            "4. Analyst view and target price if available\n"
            "5. Risk factors that could worsen the situation"
        )
    elif any(w in q for w in ["buy", "should i", "recommend", "suggest"]):
        improvement = (
            "Your improved answer must add:\n"
            "1. Detailed rationale — why this stock specifically for this client\n"
            "2. Entry price range and position sizing suggestion\n"
            "3. Target price and holding period\n"
            "4. Stop loss level\n"
            "5. What would invalidate this recommendation"
        )
    elif any(w in q for w in ["cost", "charge", "brokerage", "how much"]):
        improvement = (
            "Your improved answer must add:\n"
            "1. Full itemised charge breakdown\n"
            "2. Break-even price and percentage move needed\n"
            "3. Comparison — is this expensive or cheap relative to trade size?\n"
            "4. Net return needed to profit after all charges"
        )
    elif any(w in q for w in ["portfolio", "exposure", "sector", "overweight"]):
        improvement = (
            "Your improved answer must add:\n"
            "1. Specific overweight/underweight sectors with exact percentages\n"
            "2. Concrete rebalancing suggestion — which stocks to trim/add\n"
            "3. Risk implication of current allocation\n"
            "4. Benchmark comparison — what a balanced moderate-risk portfolio looks like"
        )
    else:
        improvement = (
            "Your improved answer must be more specific, data-driven, and actionable. "
            "Add context, numbers, and a clear recommendation the client can act on."
        )

    return (
        f"The client rated your previous answer {rating}/5 — {reason}.\n\n"
        f"Original question: {question}\n\n"
        f"Your previous answer:\n{original_answer}\n\n"
        f"{improvement}\n\n"
        f"Do not repeat the same content. Every point above must appear in your response."
    )


def get_average_rating(client_id: str) -> float:
    """Returns the rolling average rating for a client. 0.0 if no ratings yet."""
    data = _load(client_id)
    ratings = [r["rating"] for r in data["ratings"]]
    if not ratings:
        return 0.0
    return round(sum(ratings) / len(ratings), 2)


def get_rating_summary(client_id: str) -> dict:
    """Returns a summary of all ratings for a client."""
    data  = _load(client_id)
    ratings = [r["rating"] for r in data["ratings"]]
    if not ratings:
        return {"total": 0, "average": 0.0, "breakdown": {}}

    breakdown = {str(i): ratings.count(i) for i in range(1, 6)}
    return {
        "total":     len(ratings),
        "average":   round(sum(ratings) / len(ratings), 2),
        "breakdown": breakdown,
    }