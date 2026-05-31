import logging
import os
 
# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────
 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
 
LOG_FILE = os.path.join(LOG_DIR, "phase5_tool_calls.log")
 
logger = logging.getLogger("guardrails")
logger.setLevel(logging.INFO)
 
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    logger.addHandler(handler)
 
# ─────────────────────────────────────────────────────────────
# ALLOWED TOOLS
# ─────────────────────────────────────────────────────────────
 
ALLOWED_TOOLS = {
    "get_client_portfolio",
    "calculate_trade_cost",
    "check_exchange_flags",
    "get_stock_data",
    "send_trade_confirmation_email"
}
 
# Max times the same tool can be called in one conversation turn
MAX_CALLS_PER_TOOL = 3
 
# ─────────────────────────────────────────────────────────────
# GUARDRAIL: VALIDATE TOOL CALL
# Called before every tool execution
# ─────────────────────────────────────────────────────────────
def validate_tool_call(
    tool_name: str,
    tool_args: dict,
    call_counts: dict,
    session_state: dict
) -> dict:
    """
    Validates a tool call before execution.
    Returns {"allowed": True} or {"allowed": False, "reason": "..."}
 
    Args:
        tool_name:     Name of the tool the LLM wants to call
        tool_args:     Arguments the LLM is passing
        call_counts:   Dict tracking how many times each tool was called this turn
        session_state: Current session state (used for email gate)
    """
 
    # ── 1. Tool must be in the allowed list ──
    if tool_name not in ALLOWED_TOOLS:
        reason = (
            f"Tool '{tool_name}' is not in the allowed tool list. "
            f"Allowed tools: {sorted(ALLOWED_TOOLS)}"
        )
        logger.warning(f"BLOCKED | unknown_tool | {tool_name} | {reason}")
        return {"allowed": False, "reason": reason}
 
    # ── 2. Loop prevention — max 3 calls per tool per turn ──
    current_count = call_counts.get(tool_name, 0)
    if current_count >= MAX_CALLS_PER_TOOL:
        reason = (
            f"Tool '{tool_name}' has already been called {current_count} times "
            f"in this turn. Maximum is {MAX_CALLS_PER_TOOL}. "
            f"Provide an answer with the data already retrieved."
        )
        logger.warning(f"BLOCKED | loop_prevention | {tool_name} | count={current_count}")
        return {"allowed": False, "reason": reason}
 
    # ── 3. Input validation per tool ──
    validation_error = _validate_inputs(tool_name, tool_args)
    if validation_error:
        logger.warning(f"BLOCKED | input_validation | {tool_name} | {validation_error}")
        return {"allowed": False, "reason": validation_error}
 
    # ── 4. Email gate — can only send after a confirmed order ──
    if tool_name == "send_trade_confirmation_email":
        if "pending_confirmed_order" not in session_state:
            reason = (
                "EMAIL GATE: send_trade_confirmation_email called without a confirmed order "
                "in session state. This tool can only be called after the client types CONFIRM "
                "and the order is executed via the API."
            )
            logger.warning(f"BLOCKED | email_gate | no pending_confirmed_order in session")
            return {"allowed": False, "reason": reason}
 
    # ── All checks passed ──
    logger.info(f"ALLOWED | {tool_name} | args={tool_args}")
    return {"allowed": True}

# ─────────────────────────────────────────────────────────────
# INPUT VALIDATION RULES PER TOOL
# ─────────────────────────────────────────────────────────────
 
def _validate_inputs(tool_name: str, args: dict) -> str | None:
    """
    Returns an error string if inputs are invalid, None if valid.
    """
 
    if tool_name == "calculate_trade_cost":
        qty = args.get("quantity", 0)
        price = args.get("price", 0)
        action = str(args.get("action", "")).upper()
        symbol = str(args.get("symbol", "")).strip()
 
        if not symbol:
            return "calculate_trade_cost: symbol cannot be empty."
        if qty <= 0:
            return f"calculate_trade_cost: quantity must be > 0, got {qty}. Ask the client how many shares they want."
        if price <= 0:
            return f"calculate_trade_cost: price must be > 0, got {price}."
        if action not in ("BUY", "SELL"):
            return f"calculate_trade_cost: action must be BUY or SELL, got '{action}'."
 
    elif tool_name == "check_exchange_flags":
        symbol = str(args.get("symbol", "")).strip()
        if not symbol:
            return "check_exchange_flags: symbol cannot be empty."
 
    elif tool_name == "get_stock_data":
        symbol = str(args.get("symbol", "")).strip()
        if not symbol:
            return "get_stock_data: symbol cannot be empty."
 
    elif tool_name == "get_client_portfolio":
        client_id = str(args.get("client_id", "")).strip()
        if not client_id:
            return "get_client_portfolio: client_id cannot be empty."
 
    elif tool_name == "send_trade_confirmation_email":
        email = str(args.get("client_email", "")).strip()
        if not email or "@" not in email:
            return f"send_trade_confirmation_email: invalid email address '{email}'."
 
    return None  # Valid
 
# ─────────────────────────────────────────────────────────────
# LOG TOOL RESULT
# Called after every tool execution for the audit trail
# ─────────────────────────────────────────────────────────────
 
def log_tool_result(tool_name: str, args: dict, result: dict):
    """Logs the result of a tool call to phase5_tool_calls.log"""
    status = "ERROR" if "error" in result else "SUCCESS"
    logger.info(
        f"RESULT | {status} | {tool_name} | "
        f"args={args} | "
        f"result_keys={list(result.keys())}"
    )
    for handler in logger.handlers:
        handler.flush()