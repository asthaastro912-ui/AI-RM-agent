import os
import json
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
CLIENT_EMAIL = os.getenv("CLIENT_EMAIL")

# ─────────────────────────────────────────────────────────────
# AUTHENTICATE
# First run: opens browser for OAuth
# Subsequent runs: uses saved token.json
# ─────────────────────────────────────────────────────────────

def get_gmail_service():
    """
    Authenticates with Gmail API using OAuth2.
    On first run, opens a browser window for the user to sign in.
    Saves token.json so subsequent runs are automatic.
    """
    creds = None

    # Load saved token if it exists
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If no valid token, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_PATH}. "
                    f"Download it from Google Cloud Console and place it in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print(f"[Gmail MCP] Token saved to {TOKEN_PATH}")

    return build("gmail", "v1", credentials=creds)


# ─────────────────────────────────────────────────────────────
# BUILD EMAIL HTML
# ─────────────────────────────────────────────────────────────

def build_email_html(order: dict) -> str:
    """
    Builds a professional HTML email body for the trade confirmation.
    """
    action = order.get("action", "")
    symbol = order.get("symbol", "")
    quantity = order.get("quantity", 0)
    price = order.get("price", 0)
    total_charges = order.get("total_charges", 0)
    order_id = order.get("order_id", "N/A")
    updated_cash = order.get("updated_cash", 0)

    trade_value = round(quantity * price, 2)
    action_color = "#16a34a" if action == "BUY" else "#dc2626"

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white;
                    border-radius: 8px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

            <!-- Header -->
            <div style="border-bottom: 2px solid #003087; padding-bottom: 16px; margin-bottom: 24px;">
                <h2 style="color: #003087; margin: 0;">Paytm Money</h2>
                <p style="color: #666; margin: 4px 0 0;">Trade Confirmation</p>
            </div>

            <!-- Order Badge -->
            <div style="background-color: {action_color}; color: white;
                        display: inline-block; padding: 6px 16px;
                        border-radius: 4px; font-weight: bold;
                        font-size: 14px; margin-bottom: 20px;">
                {action} ORDER EXECUTED
            </div>

            <!-- Order Details -->
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
                <tr style="background-color: #f8f8f8;">
                    <td style="padding: 12px; font-weight: bold; color: #444;">Order ID</td>
                    <td style="padding: 12px; color: #111;">{order_id}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; font-weight: bold; color: #444;">Stock</td>
                    <td style="padding: 12px; color: #111;">{symbol}</td>
                </tr>
                <tr style="background-color: #f8f8f8;">
                    <td style="padding: 12px; font-weight: bold; color: #444;">Quantity</td>
                    <td style="padding: 12px; color: #111;">{quantity} shares</td>
                </tr>
                <tr>
                    <td style="padding: 12px; font-weight: bold; color: #444;">Price per Share</td>
                    <td style="padding: 12px; color: #111;">₹{price:,.2f}</td>
                </tr>
                <tr style="background-color: #f8f8f8;">
                    <td style="padding: 12px; font-weight: bold; color: #444;">Trade Value</td>
                    <td style="padding: 12px; color: #111;">₹{trade_value:,.2f}</td>
                </tr>
            </table>

            <!-- Charges Breakdown -->
            <div style="background-color: #fff8e1; border-left: 4px solid #f59e0b;
                        padding: 16px; border-radius: 4px; margin-bottom: 24px;">
                <p style="font-weight: bold; color: #444; margin: 0 0 8px;">
                    Total Charges: ₹{total_charges:,.2f}
                </p>
                <p style="color: #666; font-size: 13px; margin: 0;">
                    Includes brokerage, STT, exchange charges, SEBI fee, GST, and stamp duty.
                </p>
            </div>

            <!-- Cash Balance -->
            <div style="background-color: #f0fdf4; border-left: 4px solid #16a34a;
                        padding: 16px; border-radius: 4px; margin-bottom: 24px;">
                <p style="font-weight: bold; color: #444; margin: 0;">
                    Updated Cash Balance: ₹{updated_cash:,.2f}
                </p>
            </div>

            <!-- RM Contact -->
            <div style="border-top: 1px solid #eee; padding-top: 16px; color: #666; font-size: 13px;">
                <p style="margin: 0;">Questions? Contact your Relationship Manager:</p>
                <p style="margin: 4px 0 0;">
                    <strong>Priya Sharma</strong> —
                    <a href="mailto:priya.sharma@paytmmoney.com"
                       style="color: #003087;">priya.sharma@paytmmoney.com</a>
                </p>
                <p style="margin: 16px 0 0; font-size: 11px; color: #aaa;">
                    This is an automated confirmation from Paytm Money Limited.
                    Investments are subject to market risks.
                </p>
            </div>

        </div>
    </body>
    </html>
    """
    return html


# ─────────────────────────────────────────────────────────────
# SEND EMAIL
# ─────────────────────────────────────────────────────────────

def send_confirmation_email(to_email: str, order: dict) -> dict:
    """
    Sends a trade confirmation email via Gmail API.

    Args:
        to_email: recipient email address
        order:    confirmed order dict from session_state

    Returns:
        dict with success status and Gmail message ID
    """
    if not SENDER_EMAIL:
        return {
            "error": "SENDER_EMAIL not set in .env file."
        }

    try:
        service = get_gmail_service()

        # Build MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"Trade Confirmation — {order.get('action')} "
            f"{order.get('quantity')} shares of {order.get('symbol')} | "
            f"Order {order.get('order_id')}"
        )
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email

        # Plain text fallback
        plain_text = (
            f"Trade Confirmation\n\n"
            f"Order ID: {order.get('order_id')}\n"
            f"Action: {order.get('action')}\n"
            f"Stock: {order.get('symbol')}\n"
            f"Quantity: {order.get('quantity')} shares\n"
            f"Price: ₹{order.get('price')}\n"
            f"Total Charges: ₹{order.get('total_charges')}\n"
            f"Updated Cash: ₹{order.get('updated_cash')}\n\n"
            f"Contact: priya.sharma@paytmmoney.com"
        )

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(build_email_html(order), "html"))

        # Encode and send
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()

        print(f"[Gmail MCP] Email sent — Message ID: {result['id']}")

        return {
            "success": True,
            "message_id": result["id"],
            "to": to_email,
            "subject": msg["Subject"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ─────────────────────────────────────────────────────────────
# STANDALONE TEST
# Run this file directly to trigger OAuth + send a test email
# python agent/mcp_gmail.py
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Gmail MCP — OAuth + Send Test")
    print("=" * 50)

    # Mock order for testing
    test_order = {
        "order_id": "PM_TEST_001",
        "symbol": "TCS",
        "action": "BUY",
        "quantity": 10,
        "price": 3578.0,
        "total_charges": 47.32,
        "updated_cash": 389334.68
    }

    print(f"\nSending test email to: {CLIENT_EMAIL}")
    result = send_confirmation_email(
        to_email=CLIENT_EMAIL,
        order=test_order
    )

    if result.get("success"):
        print(f"\n✅ Email sent successfully!")
        print(f"   Message ID: {result['message_id']}")
        print(f"   Check inbox: {CLIENT_EMAIL}")
    else:
        print(f"\n❌ Failed: {result.get('error')}")