import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Compress after this many turns (1 turn = 1 user + 1 assistant message)
COMPRESSION_THRESHOLD = 10

# How many recent turns to keep verbatim after compression
RECENT_TURNS_TO_KEEP = 3

logger = logging.getLogger("memory")

# ─────────────────────────────────────────────────────────────
# COUNT TURNS
# A turn = one user message + one assistant message pair
# ─────────────────────────────────────────────────────────────

def count_turns(messages: list) -> int:
    """Count user messages in history (excluding system messages)."""
    return sum(1 for m in messages if m["role"] == "user")


# ─────────────────────────────────────────────────────────────
# SUMMARISE CONVERSATION
# Calls LLM to compress old turns into a brief summary
# ─────────────────────────────────────────────────────────────

def summarise_conversation(messages: list) -> str:
    """
    Takes the conversation history and returns a concise summary
    of what was discussed, decisions made, and trades staged/executed.
    """
    # Filter out system messages — only summarise the actual conversation
    conversation_only = [
        m for m in messages
        if m["role"] in ("user", "assistant")
    ]

    if not conversation_only:
        return ""

    # Build a readable transcript for the summariser
    transcript = ""
    for m in conversation_only:
        role = "Client" if m["role"] == "user" else "Agent"
        content = m.get("content") or ""
        # Skip empty assistant messages (tool-call only turns)
        if content.strip():
            transcript += f"{role}: {content.strip()}\n\n"

    if not transcript.strip():
        return ""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are summarising a conversation between a client and an AI "
                        "Relationship Manager at Paytm Money. "
                        "Produce a concise summary (under 200 words) covering:\n"
                        "- Stocks discussed and any analysis done\n"
                        "- Trades staged, confirmed, or cancelled\n"
                        "- Client preferences or concerns expressed\n"
                        "- Any open items or pending decisions\n"
                        "Write in third person. Be factual and specific."
                    )
                },
                {
                    "role": "user",
                    "content": f"Summarise this conversation:\n\n{transcript}"
                }
            ],
            temperature=0.3,
            max_tokens=300
        )
        summary = response.choices[0].message.content.strip()
        logger.info(f"[Memory] Summary generated: {len(summary)} chars")
        return summary

    except Exception as e:
        logger.error(f"[Memory] Summarisation failed: {str(e)}")
        return ""


# ─────────────────────────────────────────────────────────────
# COMPRESS HISTORY
# Replaces old turns with a summary, keeps recent turns verbatim
# ─────────────────────────────────────────────────────────────

def compress_history(messages: list) -> list:
    """
    Compresses conversation history when it exceeds COMPRESSION_THRESHOLD turns.

    Structure after compression:
    [system prompt] + [summary message] + [last RECENT_TURNS_TO_KEEP turns]

    Returns the compressed message list.
    """
    turn_count = count_turns(messages)

    if turn_count < COMPRESSION_THRESHOLD:
        return messages  # No compression needed yet

    logger.info(
        f"[Memory] Compressing: {turn_count} turns → "
        f"summary + {RECENT_TURNS_TO_KEEP} recent turns"
    )
    print(f"\n[Memory] Compressing conversation: {turn_count} turns → summary block")

    # Separate system messages from conversation
    system_messages = [m for m in messages if m["role"] == "system"]
    conversation_messages = [m for m in messages if m["role"] != "system"]

    # Identify the last RECENT_TURNS_TO_KEEP user+assistant pairs
    # Walk backwards to find the cutoff point
    recent_messages = []
    turns_seen = 0

    for m in reversed(conversation_messages):
        if m["role"] == "tool":
            # Always include tool messages that belong to recent turns
            recent_messages.insert(0, m)
            continue
        recent_messages.insert(0, m)
        if m["role"] == "user":
            turns_seen += 1
            if turns_seen >= RECENT_TURNS_TO_KEEP:
                break

    # Everything before recent_messages gets summarised
    cutoff = len(conversation_messages) - len(recent_messages)
    messages_to_summarise = system_messages + conversation_messages[:cutoff]

    summary_text = summarise_conversation(messages_to_summarise)

    if not summary_text:
        # Summarisation failed — return original to avoid data loss
        logger.warning("[Memory] Summarisation returned empty — keeping original history")
        return messages

    # Build compressed history
    summary_message = {
        "role": "system",
        "content": (
            f"CONVERSATION SUMMARY (earlier turns compressed):\n{summary_text}\n\n"
            f"The conversation continues below from where it left off."
        )
    }

    compressed = system_messages + [summary_message] + recent_messages

    logger.info(
        f"[Memory] Compression complete: "
        f"{len(messages)} messages → {len(compressed)} messages"
    )
    print(
        f"[Memory] Done: {len(messages)} messages → {len(compressed)} messages"
    )

    return compressed


# ─────────────────────────────────────────────────────────────
# SHOULD COMPRESS
# Called each turn to check if compression is needed
# ─────────────────────────────────────────────────────────────

def should_compress(messages: list) -> bool:
    """Returns True if conversation history should be compressed."""
    return count_turns(messages) >= COMPRESSION_THRESHOLD