import logging
from datetime import datetime
import os
import pandas as pd
from config import PROFIT_TRACKER, TRADE_MEMORY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_trade(signal, prices, amount, net_profit, gross_profit, fees, latency, slippage):
    PROFIT_TRACKER['trades'].append({
        'time': datetime.now().isoformat(),
        'signal': signal,
        'buy_price': prices[0],
        'sell_price': prices[1] if len(prices) > 1 else prices[0],
        'amount': amount,
        'gross_profit': gross_profit,
        'fees': fees,
        'net_profit': net_profit,
        'latency': latency,
        'slippage': slippage
    })
    PROFIT_TRACKER['total_profit'] += net_profit
    PROFIT_TRACKER['trade_count'] += 1
    PROFIT_TRACKER['last_trade_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_to_memory(pair, exchange, entry_price, exit_price, profit, sma_fast, sma_slow):
    new_trade = pd.DataFrame({
        "timestamp": [datetime.now().isoformat()],
        "pair": [pair],
        "exchange": [exchange],
        "entry_price": [entry_price],
        "exit_price": [exit_price],
        "profit": [profit],
        "sma_fast": [sma_fast],
        "sma_slow": [sma_slow]
    })
    global TRADE_MEMORY
    TRADE_MEMORY = pd.concat([TRADE_MEMORY, new_trade], ignore_index=True)
    TRADE_MEMORY.to_csv("trade_memory.csv", index=False)

def write_profit_report():
    OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
    HOURLY_REPORT_DIR = os.path.join(OUTPUT_DIR, "hourly_report")
    os.makedirs(HOURLY_REPORT_DIR, exist_ok=True)
    REPORT_FILE = os.path.join(HOURLY_REPORT_DIR, f"hourly_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv")
    if PROFIT_TRACKER['trades']:
        df = pd.DataFrame(PROFIT_TRACKER['trades'])
        df.to_csv(REPORT_FILE, index=False)
        win_rate = len(df[df['net_profit'] > 0]) / len(df)
        avg_profit = df['net_profit'].mean()
        df_summary = pd.DataFrame({
            'Win Rate': [win_rate],
            'Avg Profit': [avg_profit],
            'Total Profit': [PROFIT_TRACKER['total_profit']],
            'Trade Count': [PROFIT_TRACKER['trade_count']]
        })
        df_summary.to_csv(REPORT_FILE.replace('.csv', '_summary.csv'), index=False)
        PROFIT_TRACKER['trades'] = []
        logger.info(f"Hourly report saved: {REPORT_FILE}")