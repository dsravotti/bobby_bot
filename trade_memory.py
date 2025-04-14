import pandas as pd
from config import CONFIG

try:
    TRADE_MEMORY = pd.read_csv("trade_memory.csv")
    if not all(col in TRADE_MEMORY.columns for col in ["timestamp", "pair", "exchange", "entry_price", "exit_price", "profit", "sma_fast", "sma_slow"]):
        raise ValueError("Invalid columns in trade_memory.csv")
except (FileNotFoundError, ValueError):
    TRADE_MEMORY = pd.DataFrame(columns=["timestamp", "pair", "exchange", "entry_price", "exit_price", "profit", "sma_fast", "sma_slow"])

def log_to_memory(pair, exchange, entry_price, exit_price, profit, sma_fast, sma_slow):
    global TRADE_MEMORY
    new_trade = pd.DataFrame({
        "timestamp": [pd.Timestamp.now().isoformat()],
        "pair": [pair],
        "exchange": [exchange],
        "entry_price": [entry_price],
        "exit_price": [exit_price],
        "profit": [profit],
        "sma_fast": [sma_fast],
        "sma_slow": [sma_slow]
    })
    TRADE_MEMORY = pd.concat([TRADE_MEMORY, new_trade], ignore_index=True)
    TRADE_MEMORY.to_csv("trade_memory.csv", index=False)