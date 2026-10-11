
import os
import requests
import pandas as pd
from datetime import datetime, timezone

API_KEY = os.environ["TWELVE_DATA_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "@geniusgoldsignals")

# Your nine selected instruments
INSTRUMENTS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDCAD": "USD/CAD",
    "AUDCAD": "AUD/CAD",
    "AUDCHF": "AUD/CHF",
    "XAUUSD": "XAU/USD",
    "US100": "NDX",
    "XAGUSD": "XAG/USD",
    "GBPJPY": "GBP/JPY",
}

DATA_URL = "https://api.twelvedata.com/time_series"


def get_candles(symbol, interval, count=100):
    response = requests.get(
        DATA_URL,
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": count,
            "apikey": API_KEY,
            "timezone": "UTC",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if "values" not in data:
        raise RuntimeError(str(data))

    df = pd.DataFrame(data["values"])

    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column])

    df["datetime"] = pd.to_datetime(df["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


def send_signal(message):
    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )
    response = requests.post(
        url,
        data={"chat_id": CHAT_ID, "text": message},
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(str(result))


def scan_instrument(name, symbol):
    h1 = get_candles(symbol, "1h")
    m15 = get_candles(symbol, "15min")
    m5 = get_candles(symbol, "5min")

    # Exclude the latest candle, which may still be forming
    h1 = h1.iloc[:-1].reset_index(drop=True)
    m15 = m15.iloc[:-1].reset_index(drop=True)
    m5 = m5.iloc[:-1].reset_index(drop=True)

    if min(len(h1), len(m15), len(m5)) < 51:
        print(name, "Not enough candle data")
        return

    # H1 trend filter
    h1["ema20"] = h1["close"].ewm(
        span=20, adjust=False
    ).mean()
    h1["ema50"] = h1["close"].ewm(
        span=50, adjust=False
    ).mean()

    last_h1 = h1.iloc[-1]

    if (
        last_h1["close"] > last_h1["ema20"]
        and last_h1["ema20"] > last_h1["ema50"]
    ):
        direction = "BUY"

    elif (
        last_h1["close"] < last_h1["ema20"]
        and last_h1["ema20"] < last_h1["ema50"]
    ):
        direction = "SELL"

    else:
        print(name, "No clear H1 trend")
        return

    # M15 breakout: close beyond previous 20 candles
    last15 = m15.iloc[-1]
    previous15 = m15.iloc[-21:-1]

    resistance = previous15["high"].max()
    support = previous15["low"].min()

    if direction == "BUY":
        breakout = last15["close"] > resistance
    else:
        breakout = last15["close"] < support

    if not breakout:
        print(name, "Waiting for M15 breakout")
        return

    # M5 entry confirmation
    last5 = m5.iloc[-1]
    previous5 = m5.iloc[-2]

    if direction == "BUY":
        confirmed = (
            last5["close"] > previous5["high"]
            and last5["close"] > last5["open"]
        )
        stop = m5.iloc[-6:]["low"].min()

    else:
        confirmed = (
            last5["close"] < previous5["low"]
            and last5["close"] < last5["open"]
        )
        stop = m5.iloc[-6:]["high"].max()

    if not confirmed:
        print(name, "Waiting for M5 confirmation")
        return

    entry = float(last5["close"])
    stop = float(stop)

    if direction == "BUY" and stop >= entry:
        return
    if direction == "SELL" and stop <= entry:
        return

    risk = abs(entry - stop)
    if risk == 0:
        return

    target = (
        entry + 2 * risk
        if direction == "BUY"
        else entry - 2 * risk
    )

    message = (
        "GENIUS GOLD SIGNALS\n\n"
        f"Instrument: {name}\n"
        f"Direction: {direction}\n"
        "H1: Trend confirmed\n"
        "M15: Breakout confirmed\n"
        "M5: Entry confirmed\n\n"
        f"Entry reference: {entry}\n"
        f"Stop loss: {stop}\n"
        f"Take profit (2R): {target}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        "Educational signal only. Check live prices and risk."
    )

    send_signal(message)
    print(name, "Signal sent")


def main():
    for name, symbol in INSTRUMENTS.items():
        try:
            scan_instrument(name, symbol)
        except Exception as error:
            print(name, "Error:", error)


if __name__ == "__main__":
    main()

