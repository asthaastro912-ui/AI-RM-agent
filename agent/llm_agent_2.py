from openai import OpenAI
from dotenv import load_dotenv
import os 
import logging

# =====================================================
# LOAD ENV VARIABLES
# =====================================================

load_dotenv()


api_key = os.getenv("OPENAI_API_KEY")

print("Loaded key:", api_key)

if not api_key:
    raise ValueError(
        "OpenAI key not found"
    )
# =====================================================
# INITIALISE OPENAI CLIENT
# =====================================================

client = OpenAI(
    api_key = api_key
)

# =====================================================
# LOGGING SETUP
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.abspath(
    os.path.join(BASE_DIR, "..")
)

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR,
    "phase3_part2_context.log"
)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    encoding="utf-8",
    force=True
)

# =====================================================
# LOGGER HELPERS
# =====================================================

def log_chat(role, message):

    logging.info(f"{role}: {message}")

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
# BUILD PORTFOLIO CONTEXT
# -----------------------------

def build_portfolio_context():

    holdings_text=""

    for symbol,data in portfolio["holdings"].items():

        holdings_text+=(
            f"-{symbol}: "
            f"{data['quantity']} shares"
            f"at Rupees {data['avg_price']}"
            f"in {data['sector']} sector\n"

        )

    context = f"""
    Client name: {portfolio['client_name']}
    Risk Profile: {portfolio['risk_profile']}
    Cash Available: ₹{portfolio['cash_available']}
    Current Holdings:
    {holdings_text}
    
    """
    return context

# =====================================================
# SIMPLE LLM RESPONSE FUNCTION
# =====================================================

def get_llm_response(user_input):

    portfolio_context = build_portfolio_context()

    system_prompt = f"""
    You are an AI relationship Manager at Paytm Money Limited.
    You are working with high net worth client with equity protfolio discussions.

    Client Portfolio Context:
    {portfolio_context}

    Behaviour rules:
    -Use portfolio context in your answers
    -Be professional and concise
    -Explain reasoning clearly
    -Never guarantee returns
    -Never claim certainity
    -Do not provide derivatives F&O advice
    -Do not encourage illegal activity
    -If information is missing say so honestly

    """

    try:

        response = client.chat.completions.create(
            model = "gpt-3.5-turbo",
            messages = [
                {
                    "role": "system",
                    "content":system_prompt
                },
                {
                    "role":"user",
                    "content": user_input
                }
            ],
            temperature = 0.7
        )
        return response.choices[0].message.content
    
    except Exception as e:
        return f"LLM error: {str(e)}"
    

# =====================================================
# SESSION START
# =====================================================

log_chat("SYSTEM", "Phase 3 Part 2 session started")

print("=" * 60)
print("PAYTM MONEY AI RM AGENT — PHASE 3")
print("=" * 60)

print(f"\nLogs will be saved to:\n{LOG_FILE}\n")

print("LLM successfully loaded.\n")

print(
    "This version uses gpt-3.5-turbo for conversational responses.\n"
)

print("Type 'exit' to end the session.\n")

# =====================================================
# MAIN CHAT LOOP
# =====================================================

while True:

    user_input = input("\nRajiv: ")
    log_chat("USER", user_input)

    if user_input.lower() == "exit":

        log_chat("SYSTEM","Session ended.")
        print("\nEnding session.")
        break
    llm_reply = get_llm_response(user_input)
    agent_response(llm_reply)
    

    


