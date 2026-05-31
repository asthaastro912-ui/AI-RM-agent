import requests

BASE = "http://localhost:8000"

# 1. Health check
r = requests.get(f"{BASE}/")
print("Root:", r.json())

# 2. Get clients
r = requests.get(f"{BASE}/client")
print("Clients:", r.json())

# 3. Get portfolio — use whatever client_id is in your portfolio_db.json
r = requests.get(f"{BASE}/portfolio/PM_HNI_001")
print("Portfolio status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    print("Holdings count:", len(data["holdings"]))
    print("Cash:", data["client"]["cash_available"])

# 4. Place a BUY order
order = {
    "client_id": "PM_HNI_001",
    "symbol": "INFY",
    "action": "BUY",
    "quantity": 10,
    "price": 1500.0,
    "total_charges": 45.0
}
r = requests.post(f"{BASE}/place-order", json=order)
print("Place order status:", r.status_code)
print("Place order response:", r.json())

# 5. Check trade history
r = requests.get(f"{BASE}/trade-history/PM_HNI_001")
print("Trade history:", r.json())