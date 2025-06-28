
import os
import time
import requests
import pandas as pd
from binance.client import Client
from binance.enums import *
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PAIR = "1000SATSUSDT"
LEVERAGE = 10
USDT_AMOUNT = 2.4
TP_PERCENT = 3
SL_PERCENT = 2

client = Client(API_KEY, API_SECRET)
client.futures_change_leverage(symbol=PAIR, leverage=LEVERAGE)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, json=payload)
    except:
        print("Telegram error")

def get_klines(symbol, interval, limit=100):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['volume'] = df['volume'].astype(float)
    return df

def signal_generator(df):
    rsi = RSIIndicator(df['close'], window=14).rsi()
    ema_fast = EMAIndicator(df['close'], window=5).ema_indicator()
    ema_slow = EMAIndicator(df['close'], window=21).ema_indicator()
    macd_line = MACD(df['close']).macd_diff()
    if rsi.iloc[-1] < 30 and macd_line.iloc[-1] > 0 and ema_fast.iloc[-1] > ema_slow.iloc[-1]:
        return "BUY"
    elif rsi.iloc[-1] > 70 and macd_line.iloc[-1] < 0 and ema_fast.iloc[-1] < ema_slow.iloc[-1]:
        return "SELL"
    return "HOLD"

def place_order(signal):
    price = float(client.futures_symbol_ticker(symbol=PAIR)["price"])
    quantity = round(USDT_AMOUNT * LEVERAGE / price, 0)
    side = SIDE_BUY if signal == "BUY" else SIDE_SELL
    opposite = SIDE_SELL if side == SIDE_BUY else SIDE_BUY
    tp_price = price * (1 + TP_PERCENT / 100) if side == SIDE_BUY else price * (1 - TP_PERCENT / 100)
    sl_price = price * (1 - SL_PERCENT / 100) if side == SIDE_BUY else price * (1 + SL_PERCENT / 100)
    client.futures_create_order(symbol=PAIR, side=side, type=ORDER_TYPE_MARKET, quantity=quantity)
    send_telegram(f"✅ Відкрито {'LONG' if side == SIDE_BUY else 'SHORT'} @ {price}$")
    client.futures_create_order(symbol=PAIR, side=opposite, type=ORDER_TYPE_LIMIT, quantity=quantity,
                                price=round(tp_price, 6), timeInForce=TIME_IN_FORCE_GTC, reduceOnly=True)
    client.futures_create_order(symbol=PAIR, side=opposite, type=ORDER_TYPE_STOP_MARKET,
                                stopPrice=round(sl_price, 6), closePosition=True)

def main():
    while True:
        try:
            df = get_klines(PAIR, "15m")
            signal = signal_generator(df)
            send_telegram(f"📈 Сигнал: {signal}")
            pos_info = client.futures_position_information(symbol=PAIR)
            position_amt = float(pos_info[0]["positionAmt"])
            if position_amt == 0 and signal in ["BUY", "SELL"]:
                place_order(signal)
        except Exception as e:
            send_telegram(f"❌ Помилка: {str(e)}")
        time.sleep(900)

main()
