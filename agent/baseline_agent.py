# agent/baseline_agent.py

import yfinance as yf
from datetime import datetime
import logging
import os

# -----------------------------
# LOGGING SETUP
# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.abspath(
    os.path.join(BASE_DIR, "..")
)

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR,
    "phase2_baseline.log"
)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    encoding="utf-8",
    force=True
)

# -----------------------------
# LOGGER HELPERS
# -----------------------------

def log_chat(role, message):

    logging.info(f"{role}: {message}")

    # force instant write to file
    for handler in logging.getLogger().handlers:
        handler.flush()


def agent_response(message):

    print(f"\nAI RM Agent:\n{message}")

    log_chat("AGENT", message)


# -----------------------------
# MOCK CLIENT PORTFOLIO
# -----------------------------

portfolio = {
    "client_name": "Rajiv Malhotra",
    "risk_profile": "moderate",
    "cash_available": 200000,

    "holdings": {
        "INFY": {
            "quantity": 120,
            "avg_price": 1480,
            "sector": "IT"
        },

        "TATAMOTORS": {
            "quantity": 200,
            "avg_price": 680,
            "sector": "Auto"
        },

        "HDFCBANK": {
            "quantity": 80,
            "avg_price": 1520,
            "sector": "Banking"
        }
    }
}

# -----------------------------
# BASIC STOCK UNIVERSE
# -----------------------------

stock_universe = {
    "INFY": {
        "risk": "low",
        "analyst_rating": "BUY",
        "sector": "IT",
        "asm_flag": False
    },

    "HDFCBANK": {
        "risk": "low",
        "analyst_rating": "BUY",
        "sector": "Banking",
        "asm_flag": False
    },

    "TCS": {
        "risk": "low",
        "analyst_rating": "BUY",
        "sector": "IT",
        "asm_flag": False
    },

    "IREDA": {
        "risk": "high",
        "analyst_rating": "HOLD",
        "sector": "Power",
        "asm_flag": True
    },

    "TATAMOTORS": {
        "risk": "medium",
        "analyst_rating": "HOLD",
        "sector": "Auto",
        "asm_flag": False
    }
}

# -----------------------------
# GLOBAL TRADE STATE
# -----------------------------

pending_trade = None

# -----------------------------
# FETCH LIVE STOCK DATA
# -----------------------------

def get_live_price(symbol):

    try:
        stock = yf.Ticker(symbol + ".NS")
        hist = stock.history(period="1d")

        if hist.empty:
            return None

        latest_price = round(hist["Close"].iloc[-1], 2)

        info = stock.info

        return {
            "price": latest_price,
            "market_cap": info.get("marketCap", "N/A"),
            "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
            "volume": info.get("volume", "N/A")
        }

    except Exception:
        return None


# -----------------------------
# PORTFOLIO REVIEW
# -----------------------------

def review_portfolio():

    greeting = f"Good morning {portfolio['client_name']}."
    agent_response(greeting)

    total_value = 0

    for symbol, data in portfolio["holdings"].items():

        live_data = get_live_price(symbol)

        if live_data:
            current_price = live_data["price"]
        else:
            current_price = data["avg_price"]

        value = current_price * data["quantity"]
        pnl = (current_price - data["avg_price"]) * data["quantity"]

        total_value += value

        response = (
            f"\n{symbol}\n"
            f"Quantity: {data['quantity']}\n"
            f"Avg Buy Price: ₹{data['avg_price']}\n"
            f"Current Price: ₹{current_price}\n"
            f"Unrealised P&L: ₹{round(pnl,2)}\n"
            f"{'-'*40}"
        )

        print(response)
        log_chat("AGENT", response)

    portfolio_value_message = f"Estimated Portfolio Value: ₹{round(total_value,2)}"

    agent_response(portfolio_value_message)


# -----------------------------
# SIMPLE RECOMMENDATION ENGINE
# -----------------------------

def suggest_stocks():

    agent_response(
        "Based on your portfolio diversification and current analyst coverage, here are 3 ideas:"
    )

    suggestions = []

    held_sectors = []

    for stock in portfolio["holdings"].values():
        held_sectors.append(stock["sector"])

    for symbol, data in stock_universe.items():

        if data["asm_flag"]:
            continue

        score = 0

        # analyst rating
        if data["analyst_rating"] == "BUY":
            score += 40

        # risk profile fit
        if portfolio["risk_profile"] == "moderate":

            if data["risk"] == "low":
                score += 30

            elif data["risk"] == "medium":
                score += 15

        # diversification bonus
        if data["sector"] not in held_sectors:
            score += 25

        suggestions.append((symbol, score))

    suggestions.sort(key=lambda x: x[1], reverse=True)

    top_3 = suggestions[:3]

    for symbol, score in top_3:

        live_data = get_live_price(symbol)

        if live_data:
            price = live_data["price"]
        else:
            price = "Unavailable"

        response = (
            f"\n{symbol}\n"
            f"Current Price: ₹{price}\n"
            f"Recommendation Score: {score}/100\n"
            f"Analyst Rating: {stock_universe[symbol]['analyst_rating']}\n"
            f"Risk Level: {stock_universe[symbol]['risk']}\n"
            f"{'-'*40}"
        )

        print(response)
        log_chat("AGENT", response)


# -----------------------------
# TRADE COST CALCULATOR
# -----------------------------

def calculate_trade_cost(symbol, qty):

    global pending_trade

    live_data = get_live_price(symbol)

    if not live_data:
        agent_response("Unable to fetch live price.")
        return

    price = live_data["price"]

    turnover = price * qty

    brokerage = 20
    stt = turnover * 0.001
    gst = brokerage * 0.18
    sebi = turnover * 0.000001
    stamp_duty = turnover * 0.00015

    total_cost = brokerage + stt + gst + sebi + stamp_duty

    total_amount = turnover + total_cost

    response = (
        f"Trade Summary for {symbol}\n\n"
        f"Quantity: {qty}\n"
        f"Market Price: ₹{price}\n\n"
        f"Charges:\n"
        f"Brokerage: ₹{round(brokerage,2)}\n"
        f"STT: ₹{round(stt,2)}\n"
        f"GST: ₹{round(gst,2)}\n"
        f"SEBI Charges: ₹{round(sebi,2)}\n"
        f"Stamp Duty: ₹{round(stamp_duty,2)}\n\n"
        f"Total Estimated Cost: ₹{round(total_amount,2)}\n\n"
        f"Type CONFIRM to place this trade."
    )

    agent_response(response)

    pending_trade = {
        "symbol": symbol,
        "qty": qty,
        "price": price
    }


# -----------------------------
# CONFIRMATION GATE
# -----------------------------

def handle_confirmation(user_input):

    global pending_trade

    if pending_trade is None:
        agent_response("No pending trade found.")
        return

    if user_input == "CONFIRM":

        response = (
            f"Trade confirmed successfully.\n\n"
            f"BUY ORDER PLACED\n"
            f"Stock: {pending_trade['symbol']}\n"
            f"Quantity: {pending_trade['qty']}\n"
            f"Executed Price: ₹{pending_trade['price']}"
        )

        agent_response(response)

        pending_trade = None

    else:

        agent_response(
            "Trade not placed.\n"
            "Please type CONFIRM exactly to proceed."
        )


# -----------------------------
# SELL GUIDANCE
# -----------------------------

def sell_guidance(symbol):

    if symbol not in portfolio["holdings"]:
        agent_response("You do not currently hold this stock.")
        return

    holding = portfolio["holdings"][symbol]

    live_data = get_live_price(symbol)

    if not live_data:
        agent_response("Unable to fetch market data.")
        return

    current_price = live_data["price"]

    pnl_percent = (
        (current_price - holding["avg_price"])
        / holding["avg_price"]
    ) * 100

    response = (
        f"{symbol} Performance Review\n\n"
        f"Average Buy Price: ₹{holding['avg_price']}\n"
        f"Current Price: ₹{current_price}\n"
        f"P&L: {round(pnl_percent,2)}%\n"
    )

    if pnl_percent < -8:

        response += (
            "\nThe position has corrected significantly.\n"
            "You may review whether the original investment thesis still holds.\n"
            "Consider consulting your RM before averaging further."
        )

    elif pnl_percent > 10:

        response += (
            "\nThe stock is in profit.\n"
            "You may consider partial profit booking depending on your allocation goals."
        )

    else:

        response += (
            "\nNo major portfolio action appears necessary right now."
        )

    agent_response(response)


# -----------------------------
# RM ESCALATION
# -----------------------------

def escalate_to_rm():

    response = (
        "Connecting you to your Relationship Manager.\n"
        "A summary of this session will be shared with them."
    )

    agent_response(response)


# -----------------------------
# OUT OF SCOPE CHECK
# -----------------------------

def out_of_scope(query):

    restricted_keywords = [
        "options",
        "futures",
        "fno",
        "derivatives",
        "crypto",
        "tax saving"
    ]

    for word in restricted_keywords:

        if word in query.lower():
            return True

    return False


# -----------------------------
# SESSION START
# -----------------------------

log_chat("SYSTEM", "Session started")
print(f"\nConversation logs will be saved to:\n{LOG_FILE}\n")

# -----------------------------
# MAIN CHAT LOOP
# -----------------------------

print("=" * 60)
print("PAYTM MONEY AI RM AGENT")
print("=" * 60)

print("\nHello. I am your AI Relationship Manager.")
print("I can help with portfolio review, stock suggestions, and trade cost analysis.\n")

while True:

    user_input = input("\nRajiv: ")

    log_chat("USER", user_input)

    if user_input.lower() == "exit":

        log_chat("SYSTEM", "Session ended")

        print("\nEnding session.")
        break

    # confirmation flow
    if user_input == "CONFIRM":
        handle_confirmation(user_input)
        continue

    # out of scope
    if out_of_scope(user_input):

        agent_response(
            "I currently do not provide advice on derivatives, "
            "F&O, crypto, or tax optimisation.\n"
            "Please connect with your RM for specialised guidance."
        )

        continue

    # portfolio review
    if "portfolio" in user_input.lower():

        review_portfolio()

    # recommendations
    elif "buy" in user_input.lower() and "cost" not in user_input.lower():

        suggest_stocks()

    # trade cost
    elif "cost" in user_input.lower():

        try:

            words = user_input.split()

            qty = None
            symbol = None

            for word in words:

                if word.isdigit():
                    qty = int(word)

                if word.isalpha() and word.upper() in stock_universe:
                    symbol = word.upper()

            if qty and symbol:
                calculate_trade_cost(symbol, qty)

            else:
                agent_response(
                    "Please specify quantity and stock symbol."
                )

        except:

            agent_response(
                "Could not process the request."
            )

    # sell guidance
    elif "sell" in user_input.lower():

        found = False

        for symbol in portfolio["holdings"]:

            if symbol.lower() in user_input.lower():
                sell_guidance(symbol)
                found = True

        if not found:

            agent_response(
                "Please specify a stock from your portfolio."
            )

    # RM escalation
    elif "rm" in user_input.lower():

        escalate_to_rm()

    else:

        agent_response(
            "I could not fully understand that request.\n\n"
            "Try asking about:\n"
            "- portfolio review\n"
            "- stock suggestions\n"
            "- trade cost\n"
            "- sell guidance\n"
            "- RM escalation"
        )