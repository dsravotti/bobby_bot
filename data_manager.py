import ccxt
import pandas as pd
import numpy as np
from tenacity import retry, wait_exponential, stop_after_attempt
from config import CONFIG, CRYPTO_PAIRS, TRADE_MEMORY
from collections import deque

PRICE_HISTORY = {pair: deque(maxlen=1000) for pair in CRYPTO_PAIRS}
TRADE_MARKERS = {pair: deque(maxlen=1000) for pair in CRYPTO_PAIRS}
LAST_PRICES = {pair: {'binance': (0.0, 0), 'coinbase': (0.0, 0)} for pair in CRYPTO_PAIRS}
OHLCV_HISTORY = {pair: {'binance': deque(maxlen=CONFIG['LIMIT']), 'coinbase': deque(maxlen=CONFIG['LIMIT'])} for pair in CRYPTO_PAIRS}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_price_data(exchange, symbol, timeframe=CONFIG['TIMEFRAME'], limit=CONFIG['LIMIT']):
    if not exchange:
        print(f"Price fetch error for {symbol}: Exchange not initialized")
        return None
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        if df.empty:
            print(f"Price fetch warning for {symbol}: Empty data returned")
            return None
        return df
    except ccxt.NetworkError as e:
        print(f"Network error fetching {symbol}: {str(e)}")
        return None
    except ccxt.ExchangeError as e:
        print(f"Exchange error fetching {symbol}: {str(e)}")
        return None
    except Exception as e:
        print(f"Price fetch error for {symbol}: {str(e)}")
        return None

def calculate_atr(ohlcv_deque, period):
    ohlcv_list = list(ohlcv_deque)[-period:]
    if len(ohlcv_list) < period:
        return 0.0
    tr_values = []
    for i in range(1, len(ohlcv_list)):
        high, low, prev_close = ohlcv_list[i][2], ohlcv_list[i][3], ohlcv_list[i-1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    return np.mean(tr_values) if tr_values else 0.0