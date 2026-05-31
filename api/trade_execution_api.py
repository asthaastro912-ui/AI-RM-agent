from fastapi import FastAPI,HTTPException
import json
import os
from pydantic import BaseModel, Field
from typing import Literal
import csv
from datetime import datetime,date
import time
import logging

# ─────────────────────────────────────────────────────────────
# APP CONFIG
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI RM Portfolio API",
    description="Simulated Paytm Money Portfolio Execution API",
    version="1.0.0"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
DB_PATH = os.path.join(PROJECT_ROOT,"data","portfolio_db.json")
STOCKS_PATH = os.path.join(PROJECT_ROOT,"data","stock_universe.csv")

# ─────────────────────────────────────────────────────────────
# REQUEST MODEL
# ─────────────────────────────────────────────────────────────

class OrderRequest(BaseModel):
    client_id: str
    symbol: str
    action: Literal["BUY","SELL"]
    quantity: int = Field(gt=0)
    price : float = Field(gt=0)
    total_charges: float = Field(gt=0)

# ─────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────

def load_db():
    with open(DB_PATH,"r") as f:
        return json.load(f)
    
def save_db(db):
    with open(DB_PATH,"w") as f:
        return json.dump(db,f,indent=2)
    
# ─────────────────────────────────────────────────────────────
# STOCK LOOKUP
# ─────────────────────────────────────────────────────────────

def get_stocks_info(symbol: str):
    with open(STOCKS_PATH,"r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row["Symbol"]==symbol:
                return row
    return None

# ─────────────────────────────────────────────────────────────
# PORTFOLIO RECALCULATION
# ─────────────────────────────────────────────────────────────

def recalculate_portfolio(client_data):
    holdings = client_data["holdings"]
    cash = client_data["client"]["cash_available"]
    total_current = cash
    total_invested = 0

    for h in holdings:
        h["invested_value"] = round(
            h["quantity"] * h["avg_buy_price"], 2
        )

        h["current_value"] = round(
            h["quantity"] * h["current_price"], 2
        )

        h["unrealised_pnl"] = round(
            h["current_value"] - h["invested_value"], 2
        )

        if h["invested_value"] > 0:
            h["unrealised_pnl_pct"] = round(
                (h["unrealised_pnl"] / h["invested_value"]) * 100,
                2
            )
        else:
            h["unrealised_pnl_pct"] = 0

        total_current += h["current_value"]
        total_invested += h["invested_value"]

    # Portfolio Weights
    for h in holdings:

        h["portfolio_weight_pct"] = round(
            (h["current_value"] / total_current) * 100,
            2
        )

    # Sector Exposure
    sector_map = {}

    for h in holdings:

        sector = h["sector"]

        sector_map[sector] = round(
            sector_map.get(sector, 0)
            + h["portfolio_weight_pct"],
            2
        )

    cash_weight = round(
        (cash / total_current) * 100,
        2
    )

    sector_map["Cash"] = cash_weight

    client_data["sector_exposure"] = sector_map

    # Client Totals
    total_pnl = round(
        total_current - cash - total_invested,
        2
    )

    client_data["client"]["total_invested"] = round(
        total_invested,
        2
    )

    client_data["client"]["current_value"] = round(
        total_current,
        2
    )

    client_data["client"]["total_pnl"] = total_pnl

    if total_invested > 0:
        client_data["client"]["total_pnl_pct"] = round(
            (total_pnl / total_invested) * 100,
            2
        )
    else:
        client_data["client"]["total_pnl_pct"] = 0

    return client_data

# ─────────────────────────────────────────────────────────────
# ORDER ID
# ─────────────────────────────────────────────────────────────

def generate_order_id():
    return f"PM{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ─────────────────────────────────────────────────────────────
# ROOT
# ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "AI RM Portfolio API Running"
    }
# ─────────────────────────────────────────────────────────────
# GET ALL CLIENT IDS
# ─────────────────────────────────────────────────────────────

@app.get("/client")
def get_clients():
    db = load_db()
    return{
        "clients": list(db.keys())
    }

# ─────────────────────────────────────────────────────────────
# GET CLIENT PORTFOLIO
# ─────────────────────────────────────────────────────────────

@app.get("/portfolio/{client_id}")
def get_portfolio(client_id: str):
    db = load_db()

    if client_id not in db:
        raise HTTPException(
            status_code=404,
            detail="client not found"
        )
    return db[client_id]

# ─────────────────────────────────────────────────────────────
# PLACE ORDER
# ─────────────────────────────────────────────────────────────

@app.post("/place-order")
def place_order(order: OrderRequest):
    db = load_db()
    client_id = order.client_id

    if client_id not in db:
        raise HTTPException(
            status_code=404,
            detail="client not found"
        )
    
    client_data = db[client_id]
    holdings = client_data["holdings"]
    cash = client_data["client"]["cash_available"]
    symbol = order.symbol.upper()

    trade_value = round(
        order.quantity*order.price,2
    )

    total_outflow = round(
        trade_value+order.total_charges,2
    )

    netinflow = round(
        trade_value-order.total_charges,2
    )

    existing = next(
        (
            h for h in holdings
            if h["symbol"] == symbol
        ),
        None
    )
    # ───────────────── BUY ─────────────────

    if order.action == "BUY":
        if total_outflow > cash:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient cash. "
                    f"Need ₹{total_outflow}, "
                    f"Available ₹{cash}"
                )
            )
        
        # Existing Holding
        if existing:

            old_qty = existing["quantity"]
            old_avg = existing["avg_buy_price"]

            new_qty = old_qty + order.quantity

            new_avg = round(
                (
                    (old_qty * old_avg)
                    +
                    (order.quantity * order.price)
                ) / new_qty,
                2
            )

            existing["quantity"] = new_qty
            existing["avg_buy_price"] = new_avg
            existing["current_price"] = order.price

        # New Holding
        else:

            stock_info = get_stocks_info(symbol)

            if not stock_info:

                raise HTTPException(
                    status_code=404,
                    detail="Stock symbol not found"
                )
            
            holdings.append({
                "symbol": symbol,
                "company": stock_info["company_name"],
                "sector": stock_info["sector"],
                "cap_type": stock_info["cap_type"],
                "quantity": order.quantity,
                "avg_buy_price": order.price,
                "current_price": order.price,
                "invested_value": trade_value,
                "current_value": trade_value,
                "unrealised_pnl": 0,
                "unrealised_pnl_pct": 0,
                "portfolio_weight_pct": 0,
                "holding_days": 0,
                "date_of_first_purchase": date.today().isoformat()
            })

        client_data["client"]["cash_available"] = round(
            cash - total_outflow,
            2
        )
# ───────────────── SELL ─────────────────
    elif order.action == "SELL":

        if not existing:

            raise HTTPException(
                status_code=400,
                detail="No existing holding found"
            )

        if order.quantity > existing["quantity"]:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot sell {order.quantity}. "
                    f"You only hold "
                    f"{existing['quantity']} shares."
                )
            )
        existing["quantity"] -= order.quantity
        existing["current_price"] = order.price

        # Remove if zero
        if existing["quantity"] == 0:
            holdings.remove(existing)

        client_data["client"]["cash_available"] = round(
            cash + netinflow,
            2
        )
# ───────────────── RECALCULATE ─────────────────

    client_data = recalculate_portfolio(client_data)
# ───────────────── TRADE HISTORY ─────────────────

    order_id = generate_order_id()

    client_data["trade_history"].append({
        "order_id": order_id,
        "symbol": symbol,
        "action": order.action,
        "quantity": order.quantity,
        "price": order.price,
        "trade_value": trade_value,
        "total_charges": order.total_charges,
        "timestamp": datetime.now().isoformat()
    })

# ───────────────── SAVE ─────────────────

    db[client_id] = client_data

    save_db(db)

    return {
        "success": True,
        "order_id": order_id,
        "message": (
            f"{order.action} order executed "
            f"for {order.quantity} shares "
            f"of {symbol}"
        ),
        "updated_cash": client_data["client"]["cash_available"]
    }
# ─────────────────────────────────────────────────────────────
# GET TRADE HISTORY
# ─────────────────────────────────────────────────────────────

@app.get("/trade-history/{client_id}")
def trade_history(client_id: str):

    db = load_db()

    if client_id not in db:
        raise HTTPException(
            status_code=404,
            detail="Client not found"
        )

    return {
        "client_id": client_id,
        "trade_history": db[client_id]["trade_history"]
    }


# checking latency we add this 

@app.middleware("http")
async def log_latency(request, call_next):

    start = time.time()

    response = await call_next(request)

    duration = round(time.time() - start, 3)

    logging.info(
        f"{request.method} "
        f"{request.url.path} "
        f"{duration}s"
    )

    return response