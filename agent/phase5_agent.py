import os
import json
import logging
import time
import requests
from dotenv import load_dotenv
from openai import OpenAI

from agent.rag import get_retriever
from agent.tools import (
    get_client_portfolio,
    calculate_trade_cost,
    check_exchange_flags,
    get_stock_data,
    send_trade_confirmation_email,
    TOOL_SCHEMAS
)
from agent.guardrails import validate_tool_call, log_tool_result

# =====================================================
# LOAD ENV
# =====================================================

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=api_key)


# =====================================================
# LOGGING
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "phase5_improve2_tool_calls.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    encoding="utf-8",
    force=True
)

def log_chat(role, message):
    logging.info(f"{role}: {message}")
    for handler in logging.getLogger().handlers:
        handler.flush()

def agent_response(message):
    print(f"\nAI RM Agent:\n{message}")
    log_chat("AGENT", message)

# Step 1 — define client_id alone first
CLIENT_ID = "PM_HNI_002" # Set the client id

# Step 2 — load client from API (no session_state dependency)
def load_client(client_id: str) -> dict:
    try:
        r = requests.get(f"http://localhost:8000/portfolio/{client_id}", timeout=5)
        if r.status_code == 200:
            return r.json()["client"]
    except Exception:
        pass
    # Fallback — no session_state reference here
    return {
        "client_id": client_id,
        "name": "Client",
        "risk_profile": "moderate",
        "email": "astha.shukla.isg8@gmail.com"
    }

client_profile = load_client(CLIENT_ID)

# Step 3 — now build session_state using client_profile
session_state = {
    "client_id": CLIENT_ID,
    "client_email": client_profile.get("email", "astha.shukla.isg8@gmail.com"),
    "pending_confirmed_order": None,
}



# Per-turn tool call counter (reset each turn)
call_counts = {}

# =====================================================
# SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = f"""
You are an AI Relationship Manager at Paytm Money Limited.
You manage equity portfolios for high-net-worth clients.

Current active client: {client_profile['name']} (ID: {client_profile['client_id']})
Risk profile: Moderate

CRITICAL: Never answer questions about portfolio weights, P&L, or sector exposure 
from memory or RAG context. Always call get_client_portfolio first, even if you 
just called it in the previous turn. The portfolio changes after every trade.
## TOOL USAGE RULES — FOLLOW STRICTLY

1. PORTFOLIO QUESTIONS: Always call get_client_portfolio before answering anything
   about holdings, performance, exposure, or before making suggestions.

2. STOCK RECOMMENDATIONS: Before recommending any stock, you MUST:
   a. Call check_exchange_flags — safety check first, always
   b. Call get_stock_data — current market position
   c. Only then discuss the stock

3. TRADE COST: Always call calculate_trade_cost before confirming any trade.
   Never estimate charges from memory — this tool is 100% accurate.

4. LIVE DATA: Use get_stock_data for current prices and trends.
   RAG context gives analyst opinions; this tool gives current market reality.

5. EMAIL: Only call send_trade_confirmation_email after the client
   explicitly types CONFIRM and the order has been executed.


## Before presenting any trade for confirmation, always:
1. Call get_client_portfolio to get current cash_available
2. Call calculate_trade_cost to get total_outflow
3. If total_outflow > cash_available, tell the client they have insufficient funds.
   Do NOT ask "would you like to proceed?" for unaffordable trades.


   
## TRADE CONFIRMATION FLOW
When client wants to trade:
Step 1 → check_exchange_flags (safety)
Step 2 → get_stock_data (price confirmation)
Step 3 → calculate_trade_cost (exact charges)
Step 4 → Present summary and ask: "Type CONFIRM to proceed or CANCEL to abort."
Step 5 → On CONFIRM: execute via API, then send email

## BEHAVIOUR RULES
- Be professional, concise, and data-driven
- Never guarantee returns
- Never claim certainty about market direction
- Do not provide F&O / derivatives advice
- Flag ASM/GSM stocks clearly before any discussion
- If information is missing, say so honestly
- NIFTY, SENSEX, and other indices are not stocks. Do not call any tool for index queries. Refuse F&O advice immediately.
- "Tell me about X", "what do you think of X", "analyse X", "should I buy X" 
  → call check_exchange_flags + get_stock_data ONLY. 
  → Do NOT call calculate_trade_cost. Do NOT ask for CONFIRM.
  → Only present a trade summary and ask for CONFIRM when the client 
    explicitly says "buy X", "sell X", "place an order for X", or "I want to buy/sell X".

## ABSOLUTE RULES — NEVER VIOLATE
- You CANNOT execute trades. You have no ability to place orders.
- Only the client typing the exact word CONFIRM triggers order execution.
- Never tell the client a trade "has been executed" or "will be executed" 
  or "is being processed" unless you received a tool result confirming it.
- If the client says "just do it" / "I trust you" / "no need to confirm":
  Respond with: "I understand, but for your security I must have your explicit 
  confirmation before any order is placed. Please type CONFIRM to proceed 
  or CANCEL to abort."
- You are an advisory agent. Execution authority belongs to the client alone.

## HARD STOP — these requests must be refused immediately, before any tool call:
- Any F&O, options, futures, or derivatives question → refuse with: 
  "I only advise on equity (cash) trades. I cannot provide F&O advice."
- Any request for guaranteed returns → refuse with:
  "No stock is guaranteed to move in any direction. I cannot make return predictions."
- Do not follow a refusal with suggestions — that undermines the refusal.
"""

# =====================================================
# RAG RETRIEVAL (inherited from Phase 4)
# =====================================================

def get_retrieved_docs(user_input: str) -> str:
    try:
        retriever = get_retriever()
        docs = retriever.invoke(user_input)
        return "\n".join([d.page_content for d in docs])
    except Exception as e:
        return f"[RAG unavailable: {str(e)}]"

# =====================================================
# TOOL DISPATCHER
# Maps tool name → Python function
# =====================================================

def dispatch_tool(tool_name: str, tool_args: dict) -> dict:
    """Execute the tool and return its result as a dict."""

    if tool_name == "get_client_portfolio":
        return get_client_portfolio(**tool_args)

    elif tool_name == "calculate_trade_cost":
        return calculate_trade_cost(**tool_args)

    elif tool_name == "check_exchange_flags":
        return check_exchange_flags(**tool_args)

    elif tool_name == "get_stock_data":
        return get_stock_data(**tool_args)

    elif tool_name == "send_trade_confirmation_email":
        # Inject session_state — not exposed to LLM directly
        return send_trade_confirmation_email(
            session_state=session_state,
            client_email=tool_args.get("client_email", session_state["client_email"])
        )

    else:
        return {"error": f"Unknown tool: {tool_name}"}

# =====================================================
# PLACE ORDER VIA FASTAPI
# Called when user types CONFIRM
# =====================================================

def place_order_via_api(
    symbol: str,
    action: str,
    quantity: int,
    price: float,
    total_charges: float
) -> dict:
    """Executes the trade via the Portfolio API."""
    payload = {
        "client_id": session_state["client_id"],
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price": price,
        "total_charges": total_charges
    }
    try:
        r = requests.post(
            "http://localhost:8000/place-order",
            json=payload,
            timeout=5
        )
        if r.status_code == 400:
                detail = r.json().get("detail", "Order rejected by exchange.")
                return {"error": detail}
            
        if r.status_code == 404:
            return {"error": f"Client or stock not found."}

        if r.status_code != 200:
            return {"error": f"API error {r.status_code}: {r.text}"}

        return r.json()

    except Exception as e:
        return {"error": f"Order API failed: {str(e)}"}

# =====================================================
# TOOL-CALLING LOOP
# Core Phase 5 logic: LLM ↔ tools ↔ LLM
# =====================================================

def run_tool_calling_loop(
    messages: list,
    retrieved_context: str
) -> str:
    """
    Runs the full tool-calling loop:
    1. Ask LLM (with tools)
    2. If LLM calls a tool → validate → execute → feed result back
    3. Repeat until LLM returns a final text response
    Returns the final response string.
    """
    global call_counts
    call_counts = {}  # Reset per turn

    # Inject RAG context as the last system message
    messages_with_rag = messages.copy()
    if retrieved_context and "[RAG unavailable" not in retrieved_context:
        messages_with_rag.append({
            "role": "system",
            "content": f"RETRIEVED ANALYST / MARKET CONTEXT:\n{retrieved_context}"
        })

    loop_messages = messages_with_rag.copy()
    max_iterations = 10  # Safety ceiling

    for iteration in range(max_iterations):

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=loop_messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.7
        )

        choice = response.choices[0]
        message = choice.message

        # ── LLM finished — return text response ──
        if choice.finish_reason == "stop":
            return message.content or ""

        # ── LLM wants to call tools ──
        if choice.finish_reason == "tool_calls" and message.tool_calls:

            # Append the assistant's tool-call message
            loop_messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"\n[Tool Call] {tool_name}({tool_args})")
                log_chat("TOOL_CALL", f"{tool_name} | args={tool_args}")

                # Run guardrails
                check = validate_tool_call(
                    tool_name, tool_args, call_counts, session_state
                )

                if not check["allowed"]:
                    result = {"error": check["reason"], "blocked_by_guardrail": True}
                    print(f"[Guardrail BLOCKED] {check['reason']}")
                else:
                    # Execute
                    result = dispatch_tool(tool_name, tool_args)
                    call_counts[tool_name] = call_counts.get(tool_name, 0) + 1

                    # If a confirmed order comes back, store in session
                    if (
                        tool_name == "calculate_trade_cost"
                        and "error" not in result
                    ):
                        # Store the pending trade details for CONFIRM gate
                        session_state["_pending_trade"] = {
                            "symbol": tool_args.get("symbol"),
                            "action": tool_args.get("action"),
                            "quantity": tool_args.get("quantity"),
                            "price": tool_args.get("price"),
                            "total_charges": result.get("charges", {}).get("total_charges", 0)
                        }

                log_tool_result(tool_name, tool_args, result)
                print(f"[Tool Result] {json.dumps(result, indent=2)[:300]}...")

                # Feed result back to LLM
                loop_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

        else:
            # Unexpected finish reason
            break

    return "I was unable to complete the request after multiple steps. Please try rephrasing."

# =====================================================
# HANDLE CONFIRM / CANCEL
# =====================================================

def handle_confirm(messages: list) -> str:
    """Executes the pending trade when client types CONFIRM."""

    pending = session_state.get("_pending_trade")
    print(f"[DEBUG] _pending_trade = {pending}") 
    if not pending:
        return (
            "I don't have a pending trade to confirm. "
            "Please tell me what you'd like to trade first."
        )

    print(f"\n[CONFIRM] Executing order: {pending}")
    log_chat("SYSTEM", f"CONFIRM received | trade={pending}")

    result = place_order_via_api(
        symbol=pending["symbol"],
        action=pending["action"],
        quantity=pending["quantity"],
        price=pending["price"],
        total_charges=pending["total_charges"]
    )

    if "error" in result:
        return f"Order failed: {result['error']}"

    # Store confirmed order in session for email gate
    session_state["pending_confirmed_order"] = {
        **pending,
        "order_id": result.get("order_id"),
        "updated_cash": result.get("updated_cash"),
        "timestamp": result.get("timestamp", "")
    }
    session_state["_pending_trade"] = None

    confirmation_text = (
        f"✅ Order Executed Successfully!\n\n"
        f"Order ID: {result.get('order_id')}\n"
        f"Trade: {pending['action']} {pending['quantity']} shares of {pending['symbol']} "
        f"@ ₹{pending['price']}\n"
        f"Charges: ₹{pending['total_charges']}\n"
        f"Updated Cash Balance: ₹{result.get('updated_cash'):,.2f}\n\n"
        f"Sending confirmation email to {session_state['client_email']}..."
    )

    # Trigger email
    email_result = send_trade_confirmation_email(
        session_state=session_state,
        client_email=session_state["client_email"]
    )

    if email_result.get("success"):
        confirmation_text += "\n📧 Confirmation email sent successfully."
    elif "not found" in email_result.get("error", "") or "not configured" in email_result.get("error", ""):
        confirmation_text += "\n[Gmail MCP not configured yet — email skipped]"
    else:
        confirmation_text += f"\n[Email error: {email_result.get('error')}]"

    return confirmation_text

# =====================================================
# MAIN RESPONSE FUNCTION
# =====================================================

conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

def get_agent_response(user_input: str) -> str:
    global conversation_history

    start_time = time.time()

    # Handle CONFIRM / CANCEL outside the LLM loop
    user_stripped = user_input.strip().upper()
    if user_stripped == "CONFIRM":
        return handle_confirm(conversation_history)
    if user_stripped == "CANCEL":
        session_state["_pending_trade"] = None
        return "Trade cancelled. Let me know if you'd like to explore other options."\
        
    # Handle soft confirmations - "yes", "sure", "ok", "proceed"
    bypass_phrases = [
    "just buy", "just sell", "just do it", "trust you",
    "no need to confirm", "skip confirmation", "execute it",
    "place it now", "go ahead and buy", "go ahead and sell"
    ]

    if any(phrase in user_input.lower() for phrase in bypass_phrases):
        if session_state.get("_pending_trade"):
            return (
                "For your security, I cannot place orders without explicit confirmation. "
                "Please type CONFIRM to execute this trade or CANCEL to abort."
            )

    # Add user message to history
    conversation_history.append({"role": "user", "content": user_input})
    log_chat("USER", user_input)

    # RAG retrieval
    retrieved_context = get_retrieved_docs(user_input)

    # Run the tool-calling loop
    reply = run_tool_calling_loop(conversation_history, retrieved_context)

    # Add assistant reply to history
    conversation_history.append({"role": "assistant", "content": reply})

    total_time = round(time.time() - start_time, 2)
    print(f"\n[Total Response Time: {total_time}s]")
    log_chat("PERFORMANCE", f"total={total_time}s")

    return reply

# =====================================================
# SESSION START
# =====================================================

log_chat("SYSTEM", "Phase 5 session started")

print("=" * 60)
print("PAYTM MONEY AI RM AGENT — PHASE 5 (Tool Calling)")
print("=" * 60)
print(f"\nActive Client: {client_profile['name']} ({client_profile['client_id']})")
print(f"Logs: {LOG_FILE}\n")
print("Tools available:")
print("  • get_client_portfolio         — live portfolio data")
print("  • calculate_trade_cost  — exact trade charges")
print("  • check_exchange_flags  — ASM/GSM safety check")
print("  • get_stock_data        — live market data (yfinance)")
print("  • send_trade_confirmation_email — Gmail MCP")
print("\nType 'exit' to end. Type CONFIRM/CANCEL during trade flow.\n")

# =====================================================
# MAIN CHAT LOOP
# =====================================================

while True:
    user_input = input(f"\n{client_profile['name']}: ").strip()

    if not user_input:
        continue

    if user_input.lower() == "exit":
        log_chat("SYSTEM", "Session ended.")
        print("\nEnding session.")
        break

    reply = get_agent_response(user_input)
    agent_response(reply)