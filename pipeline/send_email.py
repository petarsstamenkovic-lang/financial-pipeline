"""
send_email.py
Builds an HTML email from the daily payload and sends via Gmail SMTP.
"""

import os
import json
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

CET = ZoneInfo("Europe/Belgrade")
GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT    = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)
DATA_DIR     = Path(__file__).parent.parent / "docs" / "data"
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://petarstamenkovic.github.io/financial-pipeline/")


def load_payload():
    path = DATA_DIR / "latest.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def arrow(pct):
    if pct is None:
        return "—"
    if pct > 0:
        return f'<span style="color:#22c55e">▲ {pct:+.2f}%</span>'
    elif pct < 0:
        return f'<span style="color:#ef4444">▼ {pct:.2f}%</span>'
    return f'<span style="color:#94a3b8">→ {pct:.2f}%</span>'


def format_price(val, symbol=""):
    if val is None:
        return "—"
    if symbol in ("EURUSD=X",):
        return f"{val:.4f}"
    if val > 1000:
        return f"{val:,.1f}"
    return f"{val:.2f}"


def market_table(category_data, title):
    rows = ""
    for name, d in category_data.items():
        if "error" in d:
            continue
        price_fmt = format_price(d.get("price"), d.get("symbol", ""))
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #1e293b;color:#94a3b8;font-size:13px;">{name}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e293b;text-align:right;font-family:'Courier New',monospace;font-size:13px;">{price_fmt}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e293b;text-align:right;font-size:13px;">{arrow(d.get('change_pct'))}</td>
        </tr>"""
    return f"""
    <div style="margin-bottom:24px;">
      <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#64748b;text-transform:uppercase;margin-bottom:8px;">{title}</div>
      <table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:8px;overflow:hidden;">
        {rows}
      </table>
    </div>"""


def news_block(items, limit=6):
    html = ""
    for item in items[:limit]:
        title   = item.get("title", "")
        link    = item.get("link", "#")
        summary = item.get("summary", "")
        source  = item.get("source", "")
        pub     = item.get("published", "")
        pub_str = ""
        if pub:
            try:
                dt = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00"))
                pub_str = dt.strftime("%H:%M")
            except Exception:
                pub_str = pub[:10]
        html += f"""
        <div style="padding:12px 0;border-bottom:1px solid #1e293b;">
          <a href="{link}" style="color:#e2e8f0;font-size:14px;font-weight:600;text-decoration:none;line-height:1.4;">{title}</a>
          <div style="color:#475569;font-size:12px;margin-top:4px;">{source}{' · ' + pub_str if pub_str else ''}</div>
          {f'<div style="color:#94a3b8;font-size:12px;margin-top:6px;line-height:1.5;">{summary}</div>' if summary else ''}
        </div>"""
    return html


def build_html(payload):
    date_str = datetime.datetime.now(CET).strftime("%A, %d %B %Y")
    market   = payload.get("market", {})
    news     = payload.get("news", {})
    events   = payload.get("key_events", [])

    # Market tables
    indices_html   = market_table(market.get("indices", {}),      "Global Indices")
    fx_html        = market_table(market.get("fx_commodities", {}), "FX & Commodities")
    sectors_html   = market_table(market.get("sectors", {}),      "US Sectors")
    largecap_html  = market_table(market.get("large_cap", {}),    "Large-Cap Equities")

    # News blocks
    macro_html   = news_block(news.get("macro_global", []), limit=7)
    serbia_html  = news_block(news.get("serbia", []), limit=10)

    # Events
    events_html = ""
    for ev in events[:5]:
        events_html += f"""
        <div style="padding:8px 0;border-bottom:1px solid #1e293b;">
          <a href="{ev.get('link','#')}" style="color:#e2e8f0;font-size:13px;text-decoration:none;">{ev.get('title','')}</a>
        </div>"""
    if not events_html:
        events_html = '<div style="color:#475569;font-size:13px;">No scheduled events found.</div>'

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#020817;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="border-left:3px solid #3b82f6;padding-left:16px;margin-bottom:32px;">
    <div style="font-size:11px;letter-spacing:3px;color:#3b82f6;text-transform:uppercase;font-weight:700;">Daily Intelligence</div>
    <div style="font-size:22px;font-weight:700;color:#f1f5f9;margin-top:4px;">{date_str}</div>
    <div style="font-size:12px;color:#475569;margin-top:2px;">Generated 13:00 CET · <a href="{DASHBOARD_URL}" style="color:#3b82f6;text-decoration:none;">Open Dashboard →</a></div>
  </div>

  <!-- Markets -->
  <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#3b82f6;text-transform:uppercase;margin-bottom:16px;">Markets</div>
  {indices_html}
  {fx_html}
  {sectors_html}
  {largecap_html}

  <!-- Macro News -->
  <div style="margin-top:32px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#3b82f6;text-transform:uppercase;margin-bottom:16px;">Global Macro</div>
    {macro_html if macro_html else '<div style="color:#475569;font-size:13px;">No stories today.</div>'}
  </div>

  <!-- Serbian News -->
  <div style="margin-top:32px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#f59e0b;text-transform:uppercase;margin-bottom:4px;">Serbia · Finance & Economy</div>
    <div style="font-size:12px;color:#475569;margin-bottom:12px;">NBS policy · fiscal developments · FX · macro impact</div>
    {serbia_html if serbia_html else '<div style="color:#475569;font-size:13px;">No Serbian stories found today.</div>'}
  </div>

  <!-- Key Events -->
  <div style="margin-top:32px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#8b5cf6;text-transform:uppercase;margin-bottom:16px;">Key Events Today</div>
    {events_html}
  </div>

  <!-- Footer -->
  <div style="margin-top:40px;padding-top:20px;border-top:1px solid #1e293b;text-align:center;">
    <a href="{DASHBOARD_URL}" style="display:inline-block;padding:10px 24px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">Open Full Dashboard</a>
    <div style="margin-top:16px;font-size:11px;color:#334155;">
      Data: yfinance · Reuters RSS · NBS · NewsAPI · Investing.com<br>
      This is not investment advice.
    </div>
  </div>

</div>
</body>
</html>"""
    return html


def send_email(html, date_str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Daily Financial Brief · {date_str}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
    print(f"Email sent to {RECIPIENT}")


if __name__ == "__main__":
    payload  = load_payload()
    html     = build_html(payload)
    date_str = datetime.datetime.now(CET).strftime("%d %b %Y")
    send_email(html, date_str)
