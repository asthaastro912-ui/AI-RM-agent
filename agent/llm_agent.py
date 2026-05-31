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

# =====================================================
# SIMPLE LLM RESPONSE FUNCTION
# =====================================================

def get_llm_response(user_input):

    try:

        response = client.chat.completions.create(
            model = "gpt-3.5-turbo",
            messages = [
                {
                    "role": "system",
                    "content":(
                        "You are an AI relationship manager"
                    )
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

log_chat("SYSTEM", "Phase 3 session started")

print("=" * 60)
print("PAYTM MONEY AI RM AGENT — PHASE 3")
print("=" * 60)

print(f"\nLogs will be saved to:\n{LOG_FILE}\n")

print("LLM successfully loaded.\n")

print(
    "This version uses GPT-4o-mini for conversational responses.\n"
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
    

    


