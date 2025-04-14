import ccxt
import os
import sys
from dotenv import load_dotenv
import logging
from utils import get_timestamp
from config import EXCHANGE_QUOTE_CURRENCIES, CRYPTO_PAIRS

logger = logging.getLogger(__name__)
load_dotenv()

def initialize_exchange(exchange_type):
    try:
        if exchange_type == "binance":
            return ccxt.binance({
                'apiKey': os.getenv('BINANCE_API_KEY'),
                'secret': os.getenv('BINANCE_SECRET'),
                'enableRateLimit': True,
                'verbose': True
            })
        elif exchange_type == "coinbase":
            return ccxt.coinbase({
                'apiKey': os.getenv('COINBASE_API_KEY'),
                'secret': os.getenv('COINBASE_SECRET'),
                'enableRateLimit': True,
                'options': {'createMarketBuyOrderRequiresPrice': False}
            })
    except Exception as e:
        logger.error(f"{get_timestamp()} - Exchange Init Failed: {exchange_type} - {str(e)}")
        return None

def validate_api_keys():
    if not all([os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET')]):
        logger.error("Binance API credentials missing!")
        sys.exit(1)
    if not all([os.getenv('COINBASE_API_KEY'), os.getenv('COINBASE_SECRET')]):
        logger.warning("Coinbase API credentials missing! Proceeding without Coinbase.")

def test_connectivity(exchange, name, log_func):
    if exchange:
        try:
            pair_key = 'BTC/USDT'
            currency = EXCHANGE_QUOTE_CURRENCIES.get(name.lower(), 'USDT')
            ticker = CRYPTO_PAIRS[pair_key][name.lower()] if name.lower() in CRYPTO_PAIRS[pair_key] else 'BTC-USD'
            response = exchange.fetch_ticker(ticker)
            balance = exchange.fetch_balance()
            balance_value = balance.get(currency, {}).get('free', None)
            if balance_value is None and name.lower() == 'coinbase':
                balance_value = balance.get('USD', {}).get('free', None)
                log_func(f"{get_timestamp()} - {name} Debug: Balance keys available: {list(balance.keys())}")
                log_func(f"{get_timestamp()} - {name} Debug: USDC balance: {balance.get('USDC', 'Not found')}, USD balance: {balance.get('USD', 'Not found')}")
                if balance_value is None:
                    balance_value = "0.0 (No USDC funds detected)"
            log_func(f"{get_timestamp()} - {name} connectivity test passed - Last Price: {response.get('last', 'N/A')} - {currency} Balance: {balance_value}")
        except Exception as e:
            log_func(f"{get_timestamp()} - Critical: {name} connectivity test failed - {str(e)}")
            if name == "Coinbase":
                log_func(f"{get_timestamp()} - Warning: Proceeding without Coinbase")
    else:
        log_func(f"{get_timestamp()} - Critical: {name} initialization failed")