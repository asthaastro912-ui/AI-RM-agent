import os
from dotenv import load_dotenv
from openai import OpenAI
import logging
from agent.rag import get_retriever
import time

# =====================================================
# LOAD ENV VARIABLES
# =====================================================

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError(
        "No api key present"
    )


client = OpenAI(
    api_key=api_key
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
    "phase4_part1_context.log"
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
# RAG Retrieval
# =====================================================

def get_retrieved_docs(user_input):
    retirever = get_retriever()

    query = user_input

    docs = retirever.invoke(query)

    formatted_docs = "\n".join(
        [d.page_content for d in docs]
    )
    return formatted_docs
    


# =====================================================
# SIMPLE LLM RESPONSE FUNCTION
# =====================================================

def get_llm_response(user_input):
    start_time = time.time()

    portfolio_context = build_portfolio_context()
    retrieval_start = time.time()
    retrieved_context = get_retrieved_docs(user_input=user_input)
    retrieval_end = time.time()

    system_prompt = f"""
    You are an AI relationship Manager at Paytm Money Limited.
    You are working with high net worth client with equity protfolio discussions.

    Client Portfolio Context:
    {portfolio_context}

    RETRIEVED MARKET / ANALYST CONTEXT:
    {retrieved_context}

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
        llm_start = time.time()
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
        llm_end = time.time()

        total_time = time.time() - start_time

        retrieval_time = retrieval_end - retrieval_start
        llm_time = llm_end - llm_start

        print(f"\nRetrieval Time: {retrieval_time:.2f} sec")
        print(f"LLM Time: {llm_time:.2f} sec")
        print(f"Total Response Time: {total_time:.2f} sec")

        log_chat(
            "PERFORMANCE",
            f"retrieval={retrieval_time:.2f}s | "
            f"llm={llm_time:.2f}s | "
            f"total={total_time:.2f}s"
        )
        return response.choices[0].message.content
    
    except Exception as e:
        return f"LLM error: {str(e)}"


# =====================================================
# SESSION START
# =====================================================

log_chat("SYSTEM", "Phase 4 part 1")

print("=" * 60)
print("PAYTM MONEY AI RM AGENT — PHASE 4 part 1")
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