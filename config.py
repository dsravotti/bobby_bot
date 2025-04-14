import pandas as pd

CRYPTO_PAIRS = {
    'BTC/USDT': {'binance': 'BTC/USDT', 'coinbase': 'BTC-USDC'},
    'ETH/USDT': {'binance': 'ETH/USDT', 'coinbase': 'ETH-USDC'},
    'XRP/USDT': {'binance': 'XRP/USDT', 'coinbase': 'XRP-USDC'},
    'LTC/USDT': {'binance': 'LTC/USDT', 'coinbase': 'LTC-USDC'},
    'BCH/USDT': {'binance': 'BCH/USDT', 'coinbase': 'BCH-USDC'},
    'ETH/BTC': {'binance': 'ETH/BTC'},
}

CONFIG = {
    'TIMEFRAME': '1m',
    'LIMIT': 200,
    'MIN_USDT_BALANCE': 10.0,
    'DRY_RUN': True,
    'LOOP_INTERVAL': 0.1,
    'BALANCE_PERCENTAGE': 0.95,
    'MIN_TRADE_AMOUNT': 0.00005,
    'TRADE_SIZE_PERCENTAGE': 0.1,
    'FEE_RATE_BINANCE': 0.00075,
    'FEE_RATE_COINBASE': 0.005,
    'CROSS_ARBITRAGE_THRESHOLD': 0.001,
    'SCALPING_THRESHOLD': 0.001,
    'SMA_FAST': 10,
    'SMA_SLOW': 50,
    'TRIANGULAR_THRESHOLD': 0.001,
    'VOLATILITY_WINDOW': 20,
    'FUNDING_RATE_THRESHOLD': 0.0005,
    'SIMULATED_BALANCE': 25,
    'MAX_POSITION_PERCENTAGE': 0.10,
    'STOP_LOSS_PERCENTAGE': 0.02,
    'SLIPPAGE': 0.001,
    'LATENCY_MIN': 0.05,
    'LATENCY_MAX': 0.2,
    'FAILURE_RATE': 0.01,
    'PARTIAL_FILL_RATE': 0.1,
    'PRICE_TTL': 60,
    'MIN_PROFIT_MARGIN': 0.002,
    'CIRCUIT_BREAKER_THRESHOLD': 0.05,
    'ATR_PERIOD': 14,
}

# Global state
POSITION = {pair: {
    'binance': {'holding': False, 'amount': 0.0, 'entry_price': 0.0, 'exchange': 'binance'},
    'coinbase': {'holding': False, 'amount': 0.0, 'entry_price': 0.0, 'exchange': 'coinbase'}
} for pair in CRYPTO_PAIRS if 'USDT' in pair}

PROFIT_TRACKER = {'total_profit': 0.0, 'trades': [], 'trade_count': 0, 'last_trade_time': None}

EXCHANGE_QUOTE_CURRENCIES = {
    'binance': 'USDT',
    'coinbase': 'USDC'
}

try:
    TRADE_MEMORY = pd.read_csv("trade_memory.csv")
    if not all(col in TRADE_MEMORY.columns for col in ["timestamp", "pair", "exchange", "entry_price", "exit_price", "profit", "sma_fast", "sma_slow"]):
        raise ValueError("Invalid columns in trade_memory.csv")
except (FileNotFoundError, ValueError):
    TRADE_MEMORY = pd.DataFrame(columns=["timestamp", "pair", "exchange", "entry_price", "exit_price", "profit", "sma_fast", "sma_slow"])