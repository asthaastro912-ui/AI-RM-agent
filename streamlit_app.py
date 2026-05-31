"""
Streamlit Chat UI
AI Relationship Manager — Paytm Money Limited

Features:
- Chat interface connected to phase7_agent.py
- Star rating (1-5) appears after every agent response
- Rating <= 3 triggers automatic re-answer with more detail
- Ratings saved to data/feedback/{client_id}_feedback.json
- Sidebar shows session stats and average rating
"""

import streamlit as st
import sys
import os

# ── Path setup — must happen before any agent imports ──────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ── Agent imports ───────────────────────────────────────────────
from agent.phase7_agent import (
    get_agent_response,
    session_state,
    client_profile,
    CLIENT_ID,
)
from agent.feedback import (
    save_rating,
    should_reanswer,
    get_reanswer_prompt,
    get_average_rating,
    get_rating_summary,
)

# ── Page config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Paytm Money — AI RM Agent",
    page_icon="💹",
    layout="wide",
)

# ── Custom CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f0f0f; }
    .stChatMessage { border-radius: 12px; margin-bottom: 8px; }
    .rating-label { font-size: 13px; color: #888; margin-top: 4px; }
    .reanswer-badge {
        background: #1a3a1a;
        border: 1px solid #2d6a2d;
        border-radius: 8px;
        padding: 4px 10px;
        font-size: 12px;
        color: #4caf50;
        display: inline-block;
        margin-bottom: 6px;
    }
    .stat-box {
        background: #1a1a1a;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 8px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state init ──────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []               # chat history for display
if "pending_rating" not in st.session_state:
    st.session_state.pending_rating = None       # tracks which message needs rating
if "total_responses" not in st.session_state:
    st.session_state.total_responses = 0
if "reanswer_count" not in st.session_state:
    st.session_state.reanswer_count = 0

# ── Sidebar ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💹 Paytm Money")
    st.markdown("### AI Relationship Manager")
    st.divider()

    # Client info
    st.markdown(f"**Client:** {client_profile.get('name', 'Unknown')}")
    st.markdown(f"**ID:** `{CLIENT_ID}`")
    st.markdown(f"**Risk:** {client_profile.get('risk_profile', 'moderate').title()}")
    st.divider()

    # Session stats
    st.markdown("### Session Stats")
    summary = get_rating_summary(CLIENT_ID)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Responses", st.session_state.total_responses)
    with col2:
        st.metric("Re-answers", st.session_state.reanswer_count)

    avg = get_average_rating(CLIENT_ID)
    if avg > 0:
        stars = "⭐" * round(avg)
        st.markdown(f"**Avg Rating:** {stars} ({avg}/5)")
        st.markdown(f"**Total rated:** {summary['total']}")

        # Rating breakdown
        if summary["total"] > 0:
            st.markdown("**Rating breakdown:**")
            for star in range(5, 0, -1):
                count = summary["breakdown"].get(str(star), 0)
                pct   = int((count / summary["total"]) * 100) if summary["total"] else 0
                st.markdown(f"{star}⭐ {'█' * (pct // 10)}{'░' * (10 - pct // 10)} {count}")
    else:
        st.markdown("*No ratings yet*")

    st.divider()

    # Tools info
    st.markdown("### Tools Active")
    st.markdown("✅ Portfolio API")
    st.markdown("✅ Trade Cost Calculator")
    st.markdown("✅ Exchange Flags")
    st.markdown("✅ Live Market Data")
    st.markdown("✅ Gmail Confirmation")

    st.divider()
    st.markdown("**Phase 7** — Adaptive Feedback")

# ── Header ──────────────────────────────────────────────────────
st.markdown("## 💹 Paytm Money — AI Relationship Manager")
st.markdown(
    f"Chatting as **{client_profile.get('name', 'Client')}** · "
    f"Risk profile: *{client_profile.get('risk_profile', 'moderate')}*"
)
st.divider()

# ── Render chat history ─────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    role    = msg["role"]
    content = msg["content"]
    is_reanswer = msg.get("is_reanswer", False)

    with st.chat_message("user" if role == "user" else "assistant"):
        if is_reanswer:
            st.markdown(
                '<div class="reanswer-badge">🔄 Improved answer based on your feedback</div>',
                unsafe_allow_html=True
            )
        st.markdown(content)

        # Show star rating widget for agent messages that haven't been rated yet
        if (
            role == "assistant"
            and not msg.get("rated", False)
            and i == len(st.session_state.messages) - 1
            and not is_reanswer  # don't rate re-answers inline — show below
        ):
            st.markdown('<p class="rating-label">Rate this response:</p>', unsafe_allow_html=True)
            rating = st.feedback("stars", key=f"rating_{i}")

            if rating is not None:
                # st.feedback returns 0-4, convert to 1-5
                star_rating = rating + 1
                msg["rated"]  = True
                msg["rating"] = star_rating

                # Find the question this answer belongs to
                question = ""
                for prev in reversed(st.session_state.messages[:i]):
                    if prev["role"] == "user":
                        question = prev["content"]
                        break

                # Save to feedback store
                save_rating(
                    client_id=CLIENT_ID,
                    question=question,
                    answer=content,
                    rating=star_rating,
                )

                if should_reanswer(star_rating):
                    # Trigger re-answer automatically
                    st.session_state.pending_rating = {
                        "question":        question,
                        "original_answer": content,
                        "rating":          star_rating,
                    }
                    st.rerun()
                else:
                    st.toast(f"Thanks for the {star_rating}⭐ rating!", icon="✅")
                    st.rerun()

# ── Process pending re-answer ────────────────────────────────────
if st.session_state.pending_rating:
    pending = st.session_state.pending_rating
    st.session_state.pending_rating = None

    reanswer_prompt = get_reanswer_prompt(
        question=pending["question"],
        original_answer=pending["original_answer"],
        rating=pending["rating"],
    )

    with st.chat_message("assistant"):
        st.markdown(
            '<div class="reanswer-badge">🔄 Improving answer based on your feedback...</div>',
            unsafe_allow_html=True
        )
        with st.spinner("Generating better response..."):
            improved = get_agent_response(reanswer_prompt)

        st.markdown(improved)

        # Show rating for the re-answer too
        st.markdown('<p class="rating-label">Rate this improved response:</p>', unsafe_allow_html=True)
        rerating = st.feedback("stars", key=f"rerating_{len(st.session_state.messages)}")

        if rerating is not None:
            star_rating = rerating + 1
            save_rating(
                client_id=CLIENT_ID,
                question=pending["question"],
                answer=improved,
                rating=star_rating,
            )
            st.toast(f"Thanks! Rated {star_rating}⭐", icon="✅")

    # Add improved answer to chat history
    st.session_state.messages.append({
        "role":       "assistant",
        "content":    improved,
        "rated":      False,
        "is_reanswer": True,
    })
    st.session_state.reanswer_count += 1
    st.rerun()

# ── Chat input ──────────────────────────────────────────────────
user_input = st.chat_input(
    f"Ask {client_profile.get('name', 'me')} anything about your portfolio..."
)

if user_input:
    # Add user message to display
    st.session_state.messages.append({
        "role":    "user",
        "content": user_input,
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = get_agent_response(user_input)
        st.markdown(response)

    # Add agent response to display history
    st.session_state.messages.append({
        "role":    "assistant",
        "content": response,
        "rated":   False,
    })
    st.session_state.total_responses += 1
    st.rerun()