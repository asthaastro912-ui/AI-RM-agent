# AI Relationship Manager Agent

## Overview

LLM-powered investment advisory assistant
built for Paytm Money.

## Features

- Portfolio Analysis
- Trade Cost Calculation
- Trade Confirmation Workflow
- Email Notifications
- RAG-based Analyst Research
- Guardrails
- Conversation Memory Compression

## Architecture

diagram

## Setup

pip install -r requirements.txt

## Run API

uvicorn api.main:app --reload

## Run Agent

python -m agent.phase7_agent

## Run Streamlit

streamlit run app.py


Project Evolution by Phase
## Phase 1 — Problem Framing & System Design

Goal: Define the AI Relationship Manager use case, user persona, scope, success metrics, and constraints.

Deliverables

Problem framing document
User workflow analysis
Success criteria and evaluation metrics
## Phase 2 — Baseline agent

Goal: Build the financial knowledge base used by the advisor.

Files Introduced

agent/baseline_agent.py


## Phase 3 - adding LLM intelligence 

Goal: Create the first retrieval-augmented investment advisor.

Files Introduced:
added only llm
agent/llm_agent.py
added llm along with a bit of portfolio context (present in the same file)
agent/llm_agent_2.py


## Phase 4 - Add Knowledge & Retrieval

Vector database creation
Retrieval of analyst reports and market context
Basic advisory responses using RAG
Phase 4 — LLM Agent with Tool Planning

Goal: Move from static RAG answers to tool-aware reasoning.

Files Introduced
agent/llm_agent_3.py
data/analysts_report.json
data/macro_events.json
data/sector_summaries.json
agent/test_rag.py
agent/rag.py
agent/create_db.py

Outcome

## Phase 5 — Tool-Calling Financial Agent

Goal: Introduce live portfolio and market tools.

Files Introduced

agent/phase5_agent.py
agent/tools.py
agent/phase5_agent.py
api/trade_execution_api.py
data/portfolio_db.json
agent/test_api.py
agent/mcp_gmail.py


## Phase 6 — Guardrails & Memory

Goal: Improve safety and long-conversation handling.

Files Introduced

agent/memory.py
agent/phase6_agent.py

Key Features


## Phase 7 — Adaptive behaviour

Goal: Improve planning, tool chaining, and portfolio-aware responses.

Files Introduced

agent/phase7_agent.py
data/feedback/
streamlit_app.py

for improvement

## Phase 8 - deployment ready code

added only few error fallbacks no extra files introduced

## Phase 9 — Production-Ready RM Agent & Evaluation

Goal: Deliver a complete AI Relationship Manager with safety, execution flow, and evaluation.

Files Introduced

agent/phase9_agent.py
eval/test_cases.json
eval/eval_runner.py

## NOTE: Logs are present in logs/ for all the phases for the purpose of documenting 