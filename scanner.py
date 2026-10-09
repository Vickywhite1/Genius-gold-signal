import os
import json
import urllib.request
import urllib.parse

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API_KEY = os.environ["TWELVE_DATA_API_KEY"]
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "@geniusgoldsignals")

def candles(interval):
    params = urllib.parse.urlencode({
        "symbol": "EUR/USD",
        "interval": interval,
        "outputsize": 40,
        "apikey": API_KEY
    })
    url = "https://api.twelvedata.com/time_series?" + params
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read().decode())
    if "values" not in data:
        raise Exception("Market data unavailable: " + str(data.get("message")))
    return list(reversed(data["values"]))

h1 = candles("1h")[:-1]
m15 = candles("15min")[:-1]

trend = "BUY" if float(h1[-1]["close"]) > float(h1[-10]["close"]) else "SELL"
last = m15[-1]
previous = m15[-6:-1]

if trend == "BUY":
    valid = (
        float(last["low"]) < min(float(c["low"]) for c in previous)
        and float(last["close"]) > float(last["open"])
    )
else:
    valid = (
        float(last["high"]) > max(float(c["high"]) for c in previous)
        and float(last["close"]) < float(last["open"])
    )

if valid:
    entry = float(last["close"])
    if trend == "BUY":
        sl = min(float(c["low"]) for c in previous) - 0.00015
        tp = entry + 2 * (entry - sl)
    else:
        sl = max(float(c["high"]) for c in previous) + 0.00015
        tp = entry - 2 * (sl - entry)

    message = (
        f"GENIUS GOLD SIGNALS - EURUSD\n"
        f"Potential setup: {trend}\n"
        f"Entry reference: {entry:.5f}\n"
        f"Stop loss: {sl:.5f}\n"
        f"Take profit: {tp:.5f}\n"
        f"Time: {last['datetime']} UTC\n"
        "Educational alert only. Verify the setup and prices in MT5."
    )

    body = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": message
    }).encode()

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=body
    )

    with urllib.request.urlopen(request, timeout=20) as r:
        print(r.read().decode())
else:
    print("No qualifying setup. No signal sent.")
