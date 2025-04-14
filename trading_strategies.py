import numpy as np
import random
import time
import asyncio
from threading import Lock
from config import CONFIG, POSITION, PROFIT_TRACKER, CRYPTO_PAIRS
from utils import get_timestamp, log_trade, log_to_memory
from data_manager import OHLCV_HISTORY, TRADE_MARKERS, calculate_atr

POSITION_LOCK = Lock()
PROFIT_TRACKER_LOCK = Lock()

class TradingStrategies:
    def __init__(self, binance, coinbase, log_func):
        self.binance = binance
        self.coinbase = coinbase
        self.log = log_func
        self.trading_paused = False
        CONFIG['DEFAULT_MAKER_FEE'] = CONFIG.get('FEE_RATE_BINANCE', 0.001)
        CONFIG['DEFAULT_TAKER_FEE'] = CONFIG.get('FEE_RATE_BINANCE', 0.001)
        CONFIG['CIRCUIT_BREAKER_THRESHOLD'] = CONFIG.get('CIRCUIT_BREAKER_THRESHOLD', -1000.0)

    async def fetch_fee_rate(self, exchange, symbol):
        try:
            fees = await exchange.fetch_trading_fees()
            return fees[symbol]['maker'], fees[symbol]['taker']
        except Exception as e:
            self.log(f"{get_timestamp()} - Failed to fetch fee rates for {symbol}: {str(e)}")
            return CONFIG['DEFAULT_MAKER_FEE'], CONFIG['DEFAULT_TAKER_FEE']

    async def retry_operation(self, operation, max_retries=3, delay=1):
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                self.log(f"{get_timestamp()} - Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(delay * (2 ** attempt))
        return None

    def pause_trading(self):
        self.trading_paused = True
        self.log(f"{get_timestamp()} - Trading paused due to circuit breaker.")

    def resume_trading(self):
        self.trading_paused = False
        self.log(f"{get_timestamp()} - Trading resumed.")

    def execute_trade(self, exchange, signal, price, amount, symbol, pair, trade_type="Auto"):
        if self.trading_paused:
            self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Skipped: Trading paused by circuit breaker")
            return False

        if not exchange:
            self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Failed: Exchange not initialized")
            return False

        exchange_name = 'binance' if exchange == self.binance else 'coinbase'
        # Derive currency from symbol (e.g., BTC/USDT -> USDT, BTC/USDC -> USDC)
        currency = symbol.split('/')[-1]

        if not CONFIG['DRY_RUN'] and signal == "BUY":
            try:
                balance = exchange.fetch_balance().get(currency, {}).get('free', 0.0)
                required_funds = price * amount
                if balance < required_funds:
                    self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Failed: Insufficient {currency} balance ({balance:.2f} < {required_funds:.2f})")
                    return False
            except Exception as e:
                self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Failed: Balance check error - {str(e)}")
                return False

        loop = asyncio.get_event_loop()
        maker_fee, taker_fee = loop.run_until_complete(self.fetch_fee_rate(exchange, symbol))
        fee_rate = taker_fee

        with POSITION_LOCK:
            if pair not in POSITION or exchange_name not in POSITION[pair]:
                self.log(f"{get_timestamp()} - {pair} - Invalid exchange or pair in POSITION")
                return False

            if signal == "BUY" and POSITION[pair][exchange_name]['holding']:
                self.log(f"{get_timestamp()} - {pair} - Already holding, skipping BUY")
                return False
            if signal == "SELL" and not POSITION[pair][exchange_name]['holding']:
                self.log(f"{get_timestamp()} - {pair} - No position to SELL")
                return False

        TRADE_MARKERS[pair].append((time.time(), price, signal))

        if CONFIG['DRY_RUN']:
            latency = random.uniform(CONFIG['LATENCY_MIN'], CONFIG['LATENCY_MAX'])
            time.sleep(latency)

            if random.random() < CONFIG['FAILURE_RATE']:
                self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Failed: Simulated network error (Latency: {latency:.2f}s)")
                return False

            slippage_factor = CONFIG['SLIPPAGE'] * random.uniform(0.5, 2.0)
            adjusted_price = price * (1 + slippage_factor) if signal == "BUY" else price * (1 - slippage_factor)

            if signal == "BUY":
                expected_profit = (adjusted_price * (1 + CONFIG['MIN_PROFIT_MARGIN']) - adjusted_price) * amount
                total_cost = adjusted_price * amount * (fee_rate + CONFIG['SLIPPAGE']) * 1.5
                if expected_profit <= total_cost:
                    self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Skipped: Profit {expected_profit:.2f} < Cost {total_cost:.2f}")
                    return False

            if signal == "SELL" and adjusted_price < POSITION[pair][exchange_name]['entry_price'] * (1 - CONFIG['STOP_LOSS_PERCENTAGE']):
                self.log(f"{get_timestamp()} - {pair} - {trade_type} SELL Stop-Loss Triggered: {amount:.6f} {symbol} at ${adjusted_price:.2f}")
                trade_type = "Stop-Loss"

            if random.random() < CONFIG['PARTIAL_FILL_RATE']:
                original_amount = amount
                amount *= random.uniform(0.1, 0.9)
                self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Partial Fill: {amount:.6f}/{original_amount:.6f}")

            self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Executed (Dry Run): Amount: {amount:.6f} {symbol}, Price: ${adjusted_price:.2f}, Fees: ${adjusted_price * amount * fee_rate:.2f}, Slippage: {slippage_factor*100:.2f}%, Latency: {latency:.2f}s")
            with POSITION_LOCK:
                if signal == "BUY":
                    POSITION[pair][exchange_name].update({'holding': True, 'amount': amount, 'entry_price': adjusted_price})
                else:
                    profit = (adjusted_price - POSITION[pair][exchange_name]['entry_price']) * amount
                    fees = adjusted_price * amount * fee_rate
                    POSITION[pair][exchange_name].update({'holding': False, 'amount': 0.0})
                    log_trade(f"{trade_type} {signal} {pair}", [POSITION[pair][exchange_name]['entry_price'], adjusted_price], amount, profit - fees, profit, fees, latency, slippage_factor)
                    if trade_type == "Scalping":
                        log_to_memory(pair, exchange_name, POSITION[pair][exchange_name]['entry_price'], adjusted_price, profit, CONFIG['SMA_FAST'], CONFIG['SMA_SLOW'])

            with PROFIT_TRACKER_LOCK:
                if signal == "SELL":
                    PROFIT_TRACKER['total_profit'] += profit - fees
                    PROFIT_TRACKER['trade_count'] += 1
                    PROFIT_TRACKER['last_trade_time'] = get_timestamp()
                    if PROFIT_TRACKER['total_profit'] < CONFIG['CIRCUIT_BREAKER_THRESHOLD']:
                        self.pause_trading()
                        return False
            return True

        async def execute_real_trade():
            try:
                order = None
                if signal == "BUY":
                    if exchange_name == 'coinbase':
                        cost = amount * price
                        order = await exchange.create_market_buy_order(symbol, cost)
                        executed_amount = order['filled'] / price if order.get('filled') else cost / price
                    else:
                        order = await exchange.create_market_buy_order(symbol, amount)
                        executed_amount = order['filled'] if order.get('filled') else amount
                elif signal == "SELL":
                    order = await exchange.create_market_sell_order(symbol, amount)
                    executed_amount = order['filled'] if order.get('filled') else amount

                if order and order.get('filled') and order['filled'] < amount:
                    self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Partial Fill: {order['filled']:.6f}/{amount:.6f}")
                    executed_amount = order['filled']

                fees = price * executed_amount * fee_rate
                self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Executed: Amount: {executed_amount:.6f} {symbol}, Price: ${price:.2f}, Fees: ${fees:.2f}")

                with POSITION_LOCK:
                    if signal == "BUY":
                        POSITION[pair][exchange_name].update({'holding': True, 'amount': executed_amount, 'entry_price': price})
                    else:
                        profit = (price - POSITION[pair][exchange_name]['entry_price']) * executed_amount
                        POSITION[pair][exchange_name].update({'holding': False, 'amount': 0.0})
                        log_trade(f"{trade_type} {signal} {pair}", [POSITION[pair][exchange_name]['entry_price'], price], executed_amount, profit - fees, profit, fees, 0, 0)
                        if trade_type == "Scalping":
                            log_to_memory(pair, exchange_name, POSITION[pair][exchange_name]['entry_price'], price, profit, CONFIG['SMA_FAST'], CONFIG['SMA_SLOW'])

                with PROFIT_TRACKER_LOCK:
                    if signal == "SELL":
                        PROFIT_TRACKER['total_profit'] += profit - fees
                        PROFIT_TRACKER['trade_count'] += 1
                        PROFIT_TRACKER['last_trade_time'] = get_timestamp()
                        if PROFIT_TRACKER['total_profit'] < CONFIG['CIRCUIT_BREAKER_THRESHOLD']:
                            self.pause_trading()
                            return False
                return True
            except Exception as e:
                self.log(f"{get_timestamp()} - {pair} - {trade_type} {signal} Failed: {symbol} at ${price:.2f} - {str(e)}")
                return False

        return loop.run_until_complete(self.retry_operation(execute_real_trade))

    async def cross_exchange_arbitrage(self, pair_prices, current_pair):
        if self.trading_paused:
            self.log(f"{get_timestamp()} - {current_pair} - Cross-Exchange Arbitrage Skipped: Trading paused")
            return

        if current_pair not in pair_prices:
            self.log(f"{get_timestamp()} - {current_pair} - Cross-Exchange Arbitrage Failed: Pair not in prices")
            return

        binance_price = pair_prices[current_pair]['binance']
        coinbase_price = pair_prices[current_pair]['coinbase']

        if binance_price <= 0 or coinbase_price <= 0:
            self.log(f"{get_timestamp()} - {current_pair} - Cross-Exchange Arbitrage Skipped: Invalid prices (Binance: {binance_price}, Coinbase: {coinbase_price})")
            return

        price_diff = (binance_price - coinbase_price) / coinbase_price
        amount = min(CONFIG['MIN_TRADE_AMOUNT'], (CONFIG['SIMULATED_BALANCE'] + PROFIT_TRACKER['total_profit']) * CONFIG['TRADE_SIZE_PERCENTAGE'] / min(binance_price, coinbase_price))

        if abs(price_diff) > CONFIG['CROSS_ARBITRAGE_THRESHOLD']:
            if price_diff > 0:  # Buy Coinbase, Sell Binance
                buy_success = self.execute_trade(self.coinbase, "BUY", coinbase_price, amount, CRYPTO_PAIRS[current_pair]['coinbase'], current_pair, "Arbitrage")
                if buy_success:
                    sell_success = self.execute_trade(self.binance, "SELL", binance_price, amount, CRYPTO_PAIRS[current_pair]['binance'], current_pair, "Arbitrage")
                    if not sell_success:
                        self.log(f"{get_timestamp()} - {current_pair} - Arbitrage Failed: Sell on Binance did not complete")
            else:  # Buy Binance, Sell Coinbase
                buy_success = self.execute_trade(self.binance, "BUY", binance_price, amount, CRYPTO_PAIRS[current_pair]['binance'], current_pair, "Arbitrage")
                if buy_success:
                    sell_success = self.execute_trade(self.coinbase, "SELL", coinbase_price, amount, CRYPTO_PAIRS[current_pair]['coinbase'], current_pair, "Arbitrage")
                    if not sell_success:
                        self.log(f"{get_timestamp()} - {current_pair} - Arbitrage Failed: Sell on Coinbase did not complete")

    async def scalping_strategy(self, pair_prices, current_pair):
        if self.trading_paused:
            self.log(f"{get_timestamp()} - {current_pair} - Scalping Skipped: Trading paused")
            return

        if current_pair not in OHLCV_HISTORY:
            self.log(f"{get_timestamp()} - {current_pair} - Scalping Failed: No OHLCV data")
            return

        binance_data = list(OHLCV_HISTORY[current_pair]['binance'])
        if len(binance_data) < max(CONFIG['SMA_FAST'], CONFIG['SMA_SLOW']):
            self.log(f"{get_timestamp()} - {current_pair} - Scalping Skipped: Insufficient data")
            return

        closes = [candle[4] for candle in binance_data]
        sma_fast = np.mean(closes[-CONFIG['SMA_FAST']:])
        sma_slow = np.mean(closes[-CONFIG['SMA_SLOW']:])
        current_price = pair_prices[current_pair]['binance']

        if current_price <= 0:
            self.log(f"{get_timestamp()} - {current_pair} - Scalping Skipped: Invalid price")
            return

        amount = min(CONFIG['MIN_TRADE_AMOUNT'], (CONFIG['SIMULATED_BALANCE'] + PROFIT_TRACKER['total_profit']) * CONFIG['TRADE_SIZE_PERCENTAGE'] / current_price)

        if sma_fast > sma_slow and not POSITION[current_pair]['binance']['holding']:
            self.execute_trade(self.binance, "BUY", current_price, amount, CRYPTO_PAIRS[current_pair]['binance'], current_pair, "Scalping")
        elif sma_fast < sma_slow and POSITION[current_pair]['binance']['holding']:
            self.execute_trade(self.binance, "SELL", current_price, amount, CRYPTO_PAIRS[current_pair]['binance'], current_pair, "Scalping")

    async def triangular_arbitrage(self, exchange, base_pair, quote_pair, bridge_pair):
        if self.trading_paused:
            self.log(f"{get_timestamp()} - {base_pair}-{quote_pair}-{bridge_pair} - Triangular Arbitrage Skipped: Trading paused")
            return
        # Existing implementation (unchanged)
        pass