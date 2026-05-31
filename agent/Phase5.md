# Phase 5: Tool Calling
## AI Relationship Manager Agent — Paytm Money Limited

---

## What This Phase Adds

Phase 4 gave the agent a brain — it can reason using analyst reports, sector summaries, and macro events via RAG. But it still cannot fetch live data, calculate real charges, or take any action in the world.

Phase 5 gives the agent **hands**. It can now:

- Look up a client's portfolio on demand
- Calculate exact trade charges before any order
- Check if a stock has exchange restrictions
- Fetch live market data for any stock
- Send a real trade confirmation email via Gmail MCP

The LLM decides which tool to call based on what the user asks. You write the functions. The LLM orchestrates them.

---

## How Tool Calling Works in This Project

```
User sends a message
        ↓
LLM reads message + system prompt + tool schemas
        ↓
LLM decides: "I need live data to answer this"
        ↓
LLM calls a tool (like calling a function) with arguments
        ↓
Python executes the function, returns real data
        ↓
LLM reads the result and forms a grounded response
        ↓
User gets an accurate, data-backed answer
```

The key difference from Phase 4: RAG retrieves from static documents. Tools fetch live or computed data at the moment the user asks.

---

## Tools Built in This Phase

### Tool 1 — `get_portfolio`
**Type:** Internal function reading mock JSON (replaces Paytm Money Portfolio API)

**Why it exists:** The agent needs to know what Rajiv actually holds before making any suggestion. Without this, every recommendation is generic.

**What it returns:**
- All holdings: symbol, quantity, average buy price, current price, unrealised P&L, portfolio weight
- Sector exposure percentages
- Overall portfolio P&L

**When the LLM calls it:**
- "Show me my portfolio"
- "How am I doing?"
- "Where am I overexposed?"
- Any suggestion request — agent always checks portfolio first

**In production:** Replace the JSON file read with a call to Paytm Money's Portfolio API endpoint. The function signature stays identical — only the data source changes.

**Mock API we build:** A local function that reads `data/portfolio_mock.json` and returns structured portfolio data. The JSON is structured to mirror what a real REST API response would look like so the swap is seamless later.

---

### Tool 2 — `calculate_trade_cost`
**Type:** Deterministic calculation function — no external dependency

**Why it exists:** One of Rajiv's biggest frustrations is not knowing the true cost of a trade upfront. This tool calculates every charge before the order is confirmed.

**Inputs:** Stock symbol, quantity, price per share, action (BUY or SELL)

**What it returns — itemised:**
- Brokerage (₹20 flat or 0.03% whichever is lower — Paytm Money structure)
- STT — Securities Transaction Tax (0.1% on delivery, both sides)
- Exchange transaction charges (NSE rate: 0.00345%)
- SEBI turnover fee (0.0001%)
- GST at 18% on brokerage + exchange charges
- Stamp duty (0.015% on buy side only)
- Total charges
- Total outflow (BUY) or net inflow (SELL)
- Break-even price movement percentage

**When the LLM calls it:**
- "What will it cost me to buy 50 shares of HDFCBANK?"
- "How much will I get if I sell my TATAMOTORS?"
- Automatically before every CONFIRM gate

**Note:** This tool has 100% accuracy — it is a formula, not an LLM output. This is why cost calculations must always go through this tool, never be answered from LLM memory.

---

### Tool 3 — `check_exchange_flags`
**Type:** Internal function reading `stocks_universe.csv` (replaces exchange surveillance API)

**Why it exists:** Before recommending any stock, the agent must check whether it is under exchange surveillance or trading restrictions. Recommending an ASM stock without flagging it would be a safety failure.

**What it checks:**
- ASM flag — Additional Surveillance Measure (SEBI-imposed, heightened scrutiny)
- GSM flag — Graded Surveillance Measure (restricted trading circuits)
- Tradeable status — is the stock currently active or suspended

**What it returns:**
- All three flag statuses
- A plain-language warning if any flag is active
- Clear confirmation if the stock has no restrictions

**When the LLM calls it:**
- Before including any stock in a recommendation
- When user asks about a specific stock they want to buy
- "Is SUZLON okay to buy?"

**In production:** Replace with a call to the NSE/BSE surveillance API or Paytm Money's internal exchange flag feed, which is updated daily.

---

### Tool 4 — `get_stock_data`
**Type:** Live market data via yfinance (free, no API key needed)

**Why it exists:** The agent needs current price, 52-week range, and trend direction to give market-aware recommendations. RAG gives analyst opinions — this tool gives current market reality.

**What it returns:**
- Current trading price
- 52-week high and low
- Percentage from 52-week high and low
- Trend signal: Uptrend / Downtrend / Sideways (based on 20-day vs 50-day moving average)
- Volume trend: above or below 50-day average

**When the LLM calls it:**
- "What is TITAN trading at right now?"
- "How far is RELIANCE from its 52-week high?"
- Any suggestion flow — agent checks market data for each candidate stock

**Fallback:** If yfinance is unavailable or the symbol is not found, the tool returns a mock data response with a clear warning rather than failing silently.

**Setup:**
```bash
pip install yfinance
```
No API key needed. NSE symbols use `.NS` suffix internally (e.g. `HDFCBANK.NS`).

---

### Tool 5 — `send_trade_confirmation_email` via Gmail MCP
**Type:** External action via Gmail MCP server (real email sent)

**Why it exists:** After Rajiv types CONFIRM, the trade is simulated. But a real email lands in his inbox with the complete order details. This makes the demo tangible and integrates a real production-grade technology (MCP) that most capstone projects do not touch.

**What the email contains:**
- Order ID (simulated)
- Stock, quantity, action, price
- Complete charges breakdown (same as Tool 2 output)
- Break-even price
- What the agent is monitoring post-trade (alerts it will send)
- RM contact details if Rajiv wants to follow up with a human

**When the LLM calls it:**
- Only after the client types CONFIRM and the order is simulated
- Never called proactively or without an explicit trade confirmation

**MCP Architecture:**

```
Python agent
    ↓
mcp_gmail.py (our wrapper)
    ↓
Gmail MCP Server (Google's official server, runs locally via Node.js)
    ↓
Gmail API (OAuth authenticated)
    ↓
Real email delivered to client inbox
```

---

## Gmail MCP — Setup Guide

### What is MCP?

Model Context Protocol (MCP) is an open standard that lets AI agents connect to external services through pre-built servers. Instead of writing your own Gmail API integration from scratch, you connect to Google's official MCP server which handles authentication, rate limiting, and API calls for you.

In this project we wrap the MCP server in a Python function so OpenAI can call it as a regular tool — the same pattern as the other four tools.

### Step 1 — Install Node.js
The Gmail MCP server runs on Node.js.

Download from: https://nodejs.org (LTS version)

Verify:
```bash
node --version   # should be v18 or higher
npm --version
```

### Step 2 — Install the Gmail MCP Server
```bash
npx @google-labs/gmail-mcp
```

### Step 3 — Google Cloud Setup

1. Go to https://console.cloud.google.com
2. Create a new project (name it `rm-agent` or anything)
3. In the left menu → APIs & Services → Enable APIs
4. Search for **Gmail API** → Enable it
5. Go to APIs & Services → Credentials
6. Click **Create Credentials** → OAuth 2.0 Client ID
7. Application type: **Desktop App**
8. Download the JSON file → rename it to `credentials.json`
9. Place `credentials.json` in the project root (never commit this file)

### Step 4 — First Run OAuth Flow
```bash
python agent/mcp_gmail.py
```
A browser window opens. Sign in with your Gmail account. Grant permissions. A `token.json` file is saved locally. All future runs use this token automatically.

### Step 5 — Add to .env
```
SENDER_EMAIL=your.gmail@gmail.com
CLIENT_EMAIL=rajiv.malhotra@gmail.com
```

### Step 6 — Add to .gitignore
```
credentials.json
token.json
.env
```
Never commit credentials to GitHub.

---

## What We Are Mocking (and Why)

Since we do not have access to Paytm Money's internal APIs, we build realistic mocks that mirror what the real APIs would return. The architecture is designed so swapping mock → real requires changing only the data source, not the agent logic.

| What We Mock | How We Mock It | Real Version |
|---|---|---|
| Client portfolio | `data/portfolio_mock.json` — structured like a REST API response | Paytm Money Portfolio API |
| Exchange flags | `data/stocks_universe.csv` — ASM/GSM columns | NSE surveillance feed / internal API |
| Order placement | `place_order_mock()` — generates a fake order ID, logs the call | Paytm Money Trade API |
| Client email address | Hardcoded in `.env` as `CLIENT_EMAIL` | Pulled from client profile in production |

What is **not** mocked:
- Stock market data (`get_stock_data`) — real live data via yfinance
- The email itself (`send_trade_confirmation_email`) — real email sent via Gmail MCP

---

## Guardrails Added in This Phase

Tool calling introduces new failure modes. These guardrails prevent them:

**Loop prevention**
The agent cannot call the same tool more than 3 times in a single conversation turn. If it tries, the guardrail intercepts and returns a warning instead of executing.

**Input validation on every tool**
- `calculate_trade_cost`: quantity must be > 0, price must be > 0, action must be BUY or SELL
- `check_exchange_flags`: symbol must exist in the universe, empty string rejected
- `get_stock_data`: symbol validated before yfinance call
- `send_trade_confirmation_email`: only callable after a confirmed order exists in session state

**Email gate**
`send_trade_confirmation_email` checks for a `pending_confirmed_order` in session state before sending. If no confirmed order exists, it refuses and logs the attempt. This prevents the LLM from sending emails without a real trade confirmation.

**Out-of-scope tool requests**
If the LLM attempts to call a tool not in the defined schema (e.g. tries to access calendar, contacts, or other Gmail tools beyond send), the dispatcher rejects the call and logs it.

---

## Demonstrating Correct vs Incorrect Tool Usage

The capstone requires showing at least one failed or incorrect tool call. Here are the cases we demonstrate:

**Correct tool call:**
```
User: "What will it cost to buy 30 shares of TCS?"
LLM selects: calculate_trade_cost(symbol="TCS", quantity=30, price=3578, action="BUY")
Result: Full cost breakdown returned correctly
```

**Incorrect tool call (caught by guardrail):**
```
User: "Buy me some stocks"
LLM attempts: calculate_trade_cost(symbol="TCS", quantity=0, price=3578, action="BUY")
Guardrail: Rejects — quantity must be > 0
Result: "Please specify how many shares you want to buy."
```

**Wrong tool selected (LLM error):**
```
User: "Is SUZLON safe to trade?"
LLM incorrectly selects: get_stock_data("SUZLON")
Expected: check_exchange_flags("SUZLON")
Demonstrated in logs — agent gives price data but misses the ASM flag warning
Fix: Updated system prompt to clarify when check_exchange_flags must be called
```

**Email sent without confirmation (blocked):**
```
LLM attempts to call send_trade_confirmation_email without a confirmed order
Guardrail: No pending_confirmed_order in session state
Result: Call blocked, attempt logged to phase5_tool_calls.log
```

---

## File Structure After Phase 5

```
rm-agent/
│
├── agent/
│   ├── baseline_agent.py     # Phase 2
│   ├── llm_agent.py          # Phase 3
│   ├── rag.py                # Phase 4
│   ├── tools.py              # Phase 5 — all 4 internal tools + schemas
│   ├── mcp_gmail.py          # Phase 5 — Gmail MCP wrapper
│   ├── guardrails.py         # Phase 5 — loop prevention + input validation
│   └── phase5_agent.py       # Phase 5 — updated agent combining everything
│
├── data/
│   ├── portfolio_mock.json   # Mock Paytm Money Portfolio API response
│   ├── stocks_universe.csv   # Stock list with ASM/GSM flags
│   ├── analyst_reports.json  # RAG knowledge base (Phase 4)
│   ├── sector_summaries.json # RAG knowledge base (Phase 4)
│   └── macro_events.json     # RAG knowledge base (Phase 4)
│
├── logs/
│   ├── phase4_part1_context.log   # Phase 4 logs (existing)
│   └── phase5_tool_calls.log      # Phase 5 — every tool call logged
│
├── credentials.json   # Google OAuth — never committed
├── token.json         # Google OAuth token — never committed
└── .env               # API keys — never committed
```

---

## What Phase 5 Proves to the Evaluator

| Capstone Requirement | How Phase 5 Meets It |
|---|---|
| Define at least two tools | Five tools defined with full OpenAI-compatible schemas |
| Implement tool calling logic | OpenAI function calling with manual dispatch loop |
| Demonstrate correct tool selection | Logged examples of right tool called for right query |
| Show at least one failed tool call | Three failure cases demonstrated with root cause |
| Add safeguards against misuse or loops | Guardrails file with loop prevention + input validation + email gate |
| Real-world integration | Gmail MCP sends actual emails — not simulated |

---

## Dependencies Added in Phase 5

Add these to `requirements.txt`:

```
yfinance>=0.2.40
mcp>=1.0.0
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
google-api-python-client>=2.0.0
```

---

*Phase 5 of 9 | AI Relationship Manager Agent | Paytm Money Limited*