import os
import csv
import json
import requests
import yfinance as yf
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
STOCKS_PATH = os.path.join(PROJECT_ROOT, "data", "stock_universe.csv")

# ─────────────────────────────────────────────────────────────
# TOOL 1 — GET PORTFOLIO
# Calls your FastAPI /portfolio/{client_id}
# ─────────────────────────────────────────────────────────────

def get_client_portfolio(client_id):
    try:
        response = requests.get(
            f"{API_BASE}/portfolio/{client_id}",
            timeout=5
        )
        if response.status_code == 404:
            return {
                "error": f"Client '{client_id}' not found.",
                "valid_ids": ["PM_HNI_001", "PM_HNI_002", "PM_HNI_003"]
            }
 
        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}"}
        data = response.json()

        client = data["client"]
        holdings = data["holdings"]
        sector_exposure = data.get("sector_exposure", {})
        holdings_summary = []
        for h in holdings:
            holdings_summary.append({
                "symbol": h["symbol"],
                "company": h["company"],
                "sector": h["sector"],
                "quantity": h["quantity"],
                "avg_buy_price": h["avg_buy_price"],
                "current_price": h["current_price"],
                "invested_value": h["invested_value"],
                "current_value": h["current_value"],
                "unrealised_pnl": h["unrealised_pnl"],
                "unrealised_pnl_pct": h["unrealised_pnl_pct"],
                "portfolio_weight_pct": h["portfolio_weight_pct"],
                "holding_days": h["holding_days"]
            })
        return {
            "client_id": client["client_id"],
            "name": client["name"],
            "risk_profile": client["risk_profile"],
            "cash_available": client["cash_available"],
            "total_invested": client["total_invested"],
            "current_value": client["current_value"],
            "total_pnl": client["total_pnl"],
            "total_pnl_pct": client["total_pnl_pct"],
            "holdings": holdings_summary,
            "sector_exposure": sector_exposure
        }
    except requests.exceptions.ConnectionError:
        return {
            "error": "Portfolio API is not running. Start it with: uvicorn api.trade_execution_api:app --reload"
        }
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
    

# ─────────────────────────────────────────────────────────────
# TOOL 2 — CALCULATE TRADE COST
# Pure formula — 100% accurate, no external dependency
# ─────────────────────────────────────────────────────────────

def calculate_trade_cost(symbol: str,quantity: int,price: float,action: str) -> dict:
    """
    Calculates the exact all-in cost of a trade using Paytm Money's
    charge structure. Returns itemised breakdown + total outflow/inflow.
    """
    # Input validation
    if quantity <= 0:
        return {"error": "Quantity must be greater than 0."}
    if price <= 0:
        return {"error": "Price must be greater than 0."}
    action = action.upper()
    if action not in ("BUY", "SELL"):
        return {"error": "Action must be BUY or SELL."}
 
    symbol = symbol.upper()
    trade_value = round(quantity * price, 2)
 
    # Paytm Money charge structure
    brokerage = round(min(20, trade_value * 0.0003), 2)   # ₹20 flat or 0.03%
    stt = round(trade_value * 0.001, 2)                    # 0.1% both sides delivery
    exchange_charges = round(trade_value * 0.0000345, 2)   # NSE: 0.00345%
    sebi_fee = round(trade_value * 0.000001, 2)            # 0.0001%
    gst = round((brokerage + exchange_charges) * 0.18, 2)  # 18% on brokerage + exchange
    stamp_duty = round(trade_value * 0.00015, 2) if action == "BUY" else 0.0  # 0.015% buy only
 
    total_charges = round(
        brokerage + stt + exchange_charges + sebi_fee + gst + stamp_duty, 2
    )
 
    if action == "BUY":
        total_outflow = round(trade_value + total_charges, 2)
        net_inflow = None
        # Break-even: price must rise enough to cover charges on both sides
        breakeven_pct = round((total_charges * 2 / trade_value) * 100, 4)
        breakeven_price = round(price * (1 + breakeven_pct / 100), 2)
    else:
        total_outflow = None
        net_inflow = round(trade_value - total_charges, 2)
        breakeven_pct = None
        breakeven_price = None
 
    result = {
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price_per_share": price,
        "trade_value": trade_value,
        "charges": {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_charges": exchange_charges,
            "sebi_fee": sebi_fee,
            "gst": gst,
            "stamp_duty": stamp_duty,
            "total_charges": total_charges
        }
    }
 
    if action == "BUY":
        result["total_outflow"] = total_outflow
        result["breakeven_price"] = breakeven_price
        result["breakeven_move_pct"] = breakeven_pct
    else:
        result["net_inflow"] = net_inflow
 
    return result
 
# ─────────────────────────────────────────────────────────────
# TOOL 3 — CHECK EXCHANGE FLAGS
# Reads stocks_universe.csv — ASM / GSM / tradeable status
# ─────────────────────────────────────────────────────────────

def check_exchange_flags(symbol: str) -> dict:
    """
    Checks whether a stock is under ASM, GSM, or trading suspension.
    Must be called before recommending any stock.
    """
    if not symbol or not symbol.strip():
        return {"error": "Symbol cannot be empty."}
 
    symbol = symbol.upper().strip()
 
    try:
        with open(STOCKS_PATH, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Symbol"].upper().strip() == symbol:
                    asm = row.get("ASM", "N").strip().upper()
                    gsm = row.get("GSM", "N").strip().upper()
                    tradeable = row.get("Tradeable", "Y").strip().upper()
 
                    warnings = []
                    if asm == "Y":
                        warnings.append(
                            "⚠️ ASM FLAG: This stock is under Additional Surveillance Measure. "
                            "Higher margin requirements apply. Trade with caution."
                        )
                    if gsm == "Y":
                        warnings.append(
                            "🚫 GSM FLAG: This stock is under Graded Surveillance Measure. "
                            "Trading circuits are restricted."
                        )
                    if tradeable != "Y":
                        warnings.append(
                            "❌ SUSPENDED: This stock is currently not tradeable on the exchange."
                        )
 
                    return {
                        "symbol": symbol,
                        "asm_flag": asm == "Y",
                        "gsm_flag": gsm == "Y",
                        "is_tradeable": tradeable == "Y",
                        "warnings": warnings,
                        "clear": len(warnings) == 0,
                        "status_message": (
                            "✅ No exchange restrictions. Stock is clear to trade."
                            if len(warnings) == 0
                            else " | ".join(warnings)
                        )
                    }
 
        return {
            "error": f"Symbol '{symbol}' not found in the stock universe.",
            "symbol": symbol
        }
 
    except FileNotFoundError:
        return {
            "error": f"stocks_universe.csv not found at {STOCKS_PATH}. "
                     f"Ensure the data directory exists."
        }
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
 
# ─────────────────────────────────────────────────────────────
# TOOL 4 — GET STOCK DATA
# Live market data via yfinance — no API key needed
# ─────────────────────────────────────────────────────────────

def get_stock_data(symbol: str) -> dict:
    """
    Fetches live market data for a stock: current price, 52-week range,
    trend signal (based on 20d vs 50d MA), and volume trend.
    NSE symbols are automatically suffixed with .NS
    """
    if not symbol or not symbol.strip():
        return {"error": "Symbol cannot be empty."}
 
    symbol = symbol.upper().strip()
    yf_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
 
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="1y")
 
        if hist.empty:
            # Fallback mock with clear warning
            return {
                "symbol": symbol,
                "warning": "Live data unavailable. Using mock data for demonstration.",
                "current_price": None,
                "week_52_high": None,
                "week_52_low": None,
                "pct_from_52w_high": None,
                "pct_from_52w_low": None,
                "trend_signal": "Data unavailable",
                "volume_trend": "Data unavailable",
                "data_source": "mock_fallback"
            }
 
        current_price = round(float(hist["Close"].iloc[-1]), 2)
        week_52_high = round(float(hist["High"].max()), 2)
        week_52_low = round(float(hist["Low"].min()), 2)
 
        pct_from_high = round(
            ((current_price - week_52_high) / week_52_high) * 100, 2
        )
        pct_from_low = round(
            ((current_price - week_52_low) / week_52_low) * 100, 2
        )
 
        # Trend: 20-day vs 50-day moving average
        ma20 = hist["Close"].rolling(window=20).mean().iloc[-1]
        ma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
 
        if ma20 > ma50 * 1.02:
            trend = "Uptrend"
        elif ma20 < ma50 * 0.98:
            trend = "Downtrend"
        else:
            trend = "Sideways"
 
        # Volume trend
        avg_vol_50 = hist["Volume"].rolling(window=50).mean().iloc[-1]
        latest_vol = hist["Volume"].iloc[-1]
        volume_trend = (
            "Above average volume" if latest_vol > avg_vol_50
            else "Below average volume"
        )
 
        return {
            "symbol": symbol,
            "current_price": current_price,
            "week_52_high": week_52_high,
            "week_52_low": week_52_low,
            "pct_from_52w_high": pct_from_high,
            "pct_from_52w_low": pct_from_low,
            "trend_signal": trend,
            "volume_trend": volume_trend,
            "data_source": "yfinance_live",
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
 
    except Exception as e:
        return {
            "symbol": symbol,
            "error": f"yfinance error: ⚠ Live data unavailable — showing last known price. Do not trade on this data.",
            "warning": "Could not fetch live data."
        }
    
 
# ─────────────────────────────────────────────────────────────
# TOOL 5 — SEND TRADE CONFIRMATION EMAIL
# Calls mcp_gmail.py — real email via Gmail MCP
# Gated: only callable after a confirmed order in session state
# ─────────────────────────────────────────────────────────────
 
 
def send_trade_confirmation_email(
    session_state: dict,
    client_email: str
) -> dict:
    """
    Sends a trade confirmation email via Gmail MCP.
    Requires a 'pending_confirmed_order' key in session_state.
    Will refuse and log if called without a confirmed order.
    """
    if "pending_confirmed_order" not in session_state:
        return {
            "error": "EMAIL GATE BLOCKED: No confirmed order found in session. "
                     "send_trade_confirmation_email can only be called after "
                     "the client types CONFIRM and an order is executed.",
            "blocked": True
        }
 
    order = session_state["pending_confirmed_order"]
 
    try:
        from agent.mcp_gmail import send_confirmation_email
        result = send_confirmation_email(
            to_email=client_email,
            order=order
        )
        return {
            "success": True,
            "message": f"Confirmation email sent to {client_email}",
            "order_id": order.get("order_id"),
            "mcp_result": result
        }
    except ImportError:
        return {
            "error": "mcp_gmail.py not found or Gmail MCP not configured. "
                     "Complete the Gmail MCP setup (Phase 5 guide) before using this tool.",
            "blocked": False
        }
    except Exception as e:
        return {"error": f"Email send failed: {str(e)}"}
 
# ─────────────────────────────────────────────────────────────
# OPENAI TOOL SCHEMAS
# These tell the LLM what tools exist and how to call them
# ─────────────────────────────────────────────────────────────

 
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_client_portfolio",
            "description": (
                "Fetch the full portfolio for a client: all holdings, sector exposure, "
                "cash balance, invested value, current value, and total P&L. "
                "Call this whenever the user asks about their portfolio, holdings, "
                "performance, exposure, or before making any investment suggestion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "The client ID, e.g. PM_HNI_001"
                    }
                },
                "required": ["client_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_trade_cost",
            "description": (
                "Calculate the exact all-in cost of a trade before execution. "
                "Returns itemised charges: brokerage, STT, exchange charges, SEBI fee, "
                "GST, stamp duty, total charges, and total outflow (BUY) or net inflow (SELL). "
                "Always call this before confirming any trade. Never estimate charges from memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol, e.g. HDFCBANK"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of shares"
                    },
                    "price": {
                        "type": "number",
                        "description": "Price per share in INR"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["BUY", "SELL"],
                        "description": "Trade direction"
                    }
                },
                "required": ["symbol", "quantity", "price", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_exchange_flags",
            "description": (
                "Check whether a stock has exchange surveillance flags: "
                "ASM (Additional Surveillance Measure), GSM (Graded Surveillance Measure), "
                "or trading suspension. Must be called before recommending or trading any stock. "
                "Failure to call this before a recommendation is a safety violation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol to check, e.g. SUZLON"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": (
                "Fetch live market data for a stock: current price, 52-week high/low, "
                "distance from 52-week high and low, trend signal (Uptrend/Downtrend/Sideways), "
                "and volume trend. Use for any question about current price, market position, "
                "or trend. Do not use this instead of check_exchange_flags for safety checks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE stock symbol, e.g. TITAN or RELIANCE"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_trade_confirmation_email",
            "description": (
                "Send a trade confirmation email to the client after a confirmed order. "
                "Only call this after the client has explicitly typed CONFIRM and the order "
                "has been executed. Never call proactively. Requires a confirmed order in session."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_email": {
                        "type": "string",
                        "description": "Client's email address"
                    }
                },
                "required": ["client_email"]
            }
        }
    }
]
 
 
