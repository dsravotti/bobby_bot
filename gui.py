import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import asyncio
import numpy as np
from config import CONFIG, CRYPTO_PAIRS as CONFIG_CRYPTO_PAIRS, POSITION, PROFIT_TRACKER
from exchanges import initialize_exchange, test_connectivity, validate_api_keys
from trading_strategies import TradingStrategies
from utils import get_timestamp, write_profit_report
from data_manager import OHLCV_HISTORY, PRICE_HISTORY, TRADE_MARKERS, LAST_PRICES
from collections import deque
import time
import os
from datetime import datetime

class TradingGUI:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.root.title("Bobby-Bot Arbitrage & Scalping")
        self.root.geometry("1400x900")
        self.root.configure(bg='#1A1A1A')

        self.bg_color = '#1A1A1A'
        self.widget_bg = '#2A2A2A'
        self.text_color = '#E0E0E0'
        self.accent_color = '#00A8CC'
        self.dropdown_bg = '#E0E0E0'
        self.dropdown_text = '#000000'
        self.button_bg = '#4A4A4A'

        self.binance = None
        self.coinbase = None
        self.strategies = None

        self.running = False
        self.paused = False
        self.setup_styles()
        self.setup_gui()

        def init_exchanges():
            validate_api_keys()
            self.binance = initialize_exchange("binance")
            self.coinbase = initialize_exchange("coinbase")
            self.strategies = TradingStrategies(self.binance, self.coinbase, self.log)
            if not self.coinbase:
                for pair in list(CONFIG_CRYPTO_PAIRS.keys()):
                    if 'coinbase' in CONFIG_CRYPTO_PAIRS[pair]:
                        CONFIG_CRYPTO_PAIRS[pair].pop('coinbase')
                        if not CONFIG_CRYPTO_PAIRS[pair]:
                            del CONFIG_CRYPTO_PAIRS[pair]
                self.log(f"{get_timestamp()} - Coinbase disabled; adjusted pairs: {list(CONFIG_CRYPTO_PAIRS.keys())}")
            test_connectivity(self.binance, "Binance", self.log)
            test_connectivity(self.coinbase, "Coinbase", self.log)
            self.log(f"{get_timestamp()} - Exchange initialization complete.")

        threading.Thread(target=init_exchanges, daemon=True).start()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TLabel", font=("Helvetica", 10), background=self.bg_color, foreground=self.text_color)
        style.configure("TButton", font=("Helvetica", 10, "bold"), background=self.button_bg, foreground=self.text_color)
        style.map("TButton", background=[('active', '#5A5A5A')])
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabelframe", background=self.bg_color, foreground=self.text_color)
        style.configure("TLabelframe.Label", background=self.bg_color, foreground=self.text_color)
        style.configure("TCombobox", fieldbackground=self.dropdown_bg, background=self.dropdown_bg, foreground=self.dropdown_text,
                       selectbackground=self.dropdown_bg, selectforeground=self.dropdown_text, font=("Helvetica", 10))

    def setup_gui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        control_panel = ttk.Frame(main_frame)
        control_panel.pack(side=tk.LEFT, fill="y", padx=5)

        config_frame = ttk.LabelFrame(control_panel, text="Controls", padding=10)
        config_frame.pack(fill="x", pady=5)

        self.crypto_var = tk.StringVar(value=list(CONFIG_CRYPTO_PAIRS.keys())[0])
        ttk.Label(config_frame, text="Crypto Pair:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.crypto_dropdown = ttk.Combobox(config_frame, textvariable=self.crypto_var, values=list(CONFIG_CRYPTO_PAIRS.keys()), state="readonly")
        self.crypto_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.dry_run_var = tk.BooleanVar(value=CONFIG['DRY_RUN'])
        ttk.Checkbutton(config_frame, text="Dry Run", variable=self.dry_run_var, command=self.toggle_dry_run).grid(row=1, column=0, columnspan=2, pady=5)

        config_items = [
            ("Balance %:", "balance_pct_var", tk.DoubleVar(value=CONFIG['BALANCE_PERCENTAGE'])),
            ("Simulated Balance:", "simulated_balance_var", tk.DoubleVar(value=CONFIG['SIMULATED_BALANCE'])),
            ("SMA Fast:", "sma_fast_var", tk.IntVar(value=CONFIG['SMA_FAST'])),
            ("SMA Slow:", "sma_slow_var", tk.IntVar(value=CONFIG['SMA_SLOW'])),
            ("Amount:", "amount_var", tk.StringVar(value="0.0")),  # Added Amount field
        ]
        self.entries = {}
        for i, (label, var_name, value) in enumerate(config_items, start=2):
            ttk.Label(config_frame, text=label).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            entry = tk.Entry(config_frame, textvariable=value, bg=self.widget_bg, fg=self.text_color, insertbackground=self.text_color)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            self.entries[var_name] = entry
            setattr(self, var_name, value)

        ttk.Button(config_frame, text="Save Config", command=self.update_config).grid(row=len(config_items)+2, column=0, columnspan=2, pady=5)

        button_frame = ttk.Frame(config_frame)
        button_frame.grid(row=len(config_items)+3, column=0, columnspan=2, pady=10, sticky="ew")
        button_layout = [
            ("Start Trading", self.start_trading, 0, 0),
            ("Stop Trading", self.stop_trading, 0, 1),
            ("Pause Trading", self.pause_trading, 1, 0),
            ("Reset Positions", self.reset_positions, 1, 1),
            ("Manual Buy", lambda: self.manual_trade("BUY"), 2, 0),
            ("Manual Sell", lambda: self.manual_trade("SELL"), 2, 1),
            ("Cash Out", self.cash_out, 3, 0),
            ("Export Log", self.export_log, 3, 1),
            ("Clear Log", self.clear_log, 4, 0),
        ]
        for text, command, row, col in button_layout:
            ttk.Button(button_frame, text=text, command=command).grid(row=row, column=col, padx=5, pady=5, sticky="ew")

        log_frame = ttk.LabelFrame(control_panel, text="Transaction Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log_text = tk.Text(log_frame, height=15, bg=self.widget_bg, fg=self.text_color, font=("Courier", 10), insertbackground=self.text_color)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill="both", expand=True, padx=5)

        status_frame = ttk.LabelFrame(right_panel, text="Bot Status", padding=10)
        status_frame.pack(fill="x", pady=5)
        status_items = [
            ("Binance Price:", "price_var", "0.00"),
            ("Coinbase Price:", "coinbase_price_var", "0.00"),
            ("Position:", "position_var", "None"),
            ("Status:", "exchange_status_var", "Idle"),
            ("Total P/L:", "pl_var", "0.00"),
            ("Simulated Balance:", "sim_balance_display_var", f"${CONFIG['SIMULATED_BALANCE']:.2f}"),
            ("Arbitrage Opportunity:", "arbitrage_var", "None"),
            ("Trade Count:", "trade_count_var", "0"),
            ("Last Trade:", "last_trade_var", "N/A"),
            ("Volatility:", "volatility_var", "0.00"),
            ("ATR:", "atr_var", "0.00"),
        ]
        self.status_labels = []
        for i, (label, var_name, default) in enumerate(status_items):
            ttk.Label(status_frame, text=label).grid(row=i, column=0, padx=5, pady=3, sticky="w")
            setattr(self, var_name, tk.StringVar(value=default))
            label_widget = ttk.Label(status_frame, textvariable=getattr(self, var_name))
            label_widget.grid(row=i, column=1, padx=5, pady=3, sticky="w")
            self.status_labels.append(label_widget)

        chart_frame = ttk.LabelFrame(right_panel, text="Price Chart (Local Time)", padding=10)
        chart_frame.pack(fill="both", expand=True, pady=5)
        self.timeframe_var = tk.StringVar(value="1 Hour")
        ttk.Label(chart_frame, text="Timeframe:").pack(anchor="nw")
        self.timeframe_combo = ttk.Combobox(chart_frame, textvariable=self.timeframe_var, 
                                           values=["1 Hour", "12 Hours", "24 Hours"], state="readonly")
        self.timeframe_combo.pack(anchor="nw", pady=5)

        self.fig = Figure(figsize=(10, 4), dpi=100, facecolor=self.widget_bg)
        self.ax = self.fig.add_subplot(111, facecolor=self.bg_color)
        self.ax.tick_params(colors=self.text_color)
        self.ax.grid(True, linestyle='--', alpha=0.3, color='#606060')
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.status_bar = ttk.Label(self.root, text="Idle", anchor="w", background=self.bg_color, foreground=self.text_color)
        self.status_bar.pack(side=tk.BOTTOM, fill="x", padx=10)

        # Context Menu Setup
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_text)
        self.context_menu.add_command(label="Paste", command=self.paste_text)
        self.context_menu.add_command(label="Clear Field", command=self.clear_field)
        self.context_menu.add_command(label="Rename Pair", command=self.rename_pair)
        self.context_menu.add_command(label="Refresh Prices", command=self.refresh_prices)

        # Bind context menu
        self.entries['amount_var'].bind("<Button-3>", self.show_context_menu)
        self.crypto_dropdown.bind("<Button-3>", self.show_context_menu)
        self.log_text.bind("<Button-3>", self.show_context_menu)
        for label in self.status_labels:
            label.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        widget = event.widget
        self.context_menu.entryconfigure("Paste", state="normal" if isinstance(widget, (tk.Entry, tk.Text)) else "disabled")
        self.context_menu.entryconfigure("Clear Field", state="normal" if isinstance(widget, (tk.Entry, tk.Text)) else "disabled")
        self.context_menu.entryconfigure("Rename Pair", state="normal" if widget == self.crypto_dropdown else "disabled")
        try:
            self.context_menu.post(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_text(self):
        try:
            widget = self.root.focus_get()
            if isinstance(widget, tk.Entry):
                selected = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.log(f"{get_timestamp()} - Copied from Entry: {selected}")
            elif isinstance(widget, tk.Text):
                selected = widget.get("sel.first", "sel.last")
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.log(f"{get_timestamp()} - Copied from Log: {selected}")
            elif isinstance(widget, ttk.Label):
                text = widget.cget("text")
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.log(f"{get_timestamp()} - Copied from Label: {text}")
        except tk.TclError:
            self.log(f"{get_timestamp()} - Copy failed: No text selected")

    def paste_text(self):
        try:
            widget = self.root.focus_get()
            if isinstance(widget, tk.Entry):
                widget.delete(0, tk.END)
                widget.insert(0, self.root.clipboard_get())
                self.log(f"{get_timestamp()} - Pasted into Entry: {widget.get()}")
            elif isinstance(widget, tk.Text):
                widget.insert(tk.INSERT, self.root.clipboard_get())
                self.log(f"{get_timestamp()} - Pasted into Log")
        except tk.TclError:
            self.log(f"{get_timestamp()} - Paste failed: Clipboard empty")

    def clear_field(self):
        try:
            widget = self.root.focus_get()
            if isinstance(widget, tk.Entry):
                widget.delete(0, tk.END)
                self.log(f"{get_timestamp()} - Cleared Entry field")
            elif isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                self.log(f"{get_timestamp()} - Cleared Log")
        except Exception as e:
            self.log(f"{get_timestamp()} - Clear failed: {str(e)}")

    def rename_pair(self):
        try:
            current_pair = self.crypto_var.get()
            new_name = simpledialog.askstring("Rename Pair", f"Enter new name for {current_pair}:", parent=self.root)
            if new_name and new_name not in CONFIG_CRYPTO_PAIRS:
                CONFIG_CRYPTO_PAIRS[new_name] = CONFIG_CRYPTO_PAIRS.pop(current_pair)
                self.crypto_var.set(new_name)
                self.crypto_dropdown['values'] = list(CONFIG_CRYPTO_PAIRS.keys())
                self.log(f"{get_timestamp()} - Renamed pair {current_pair} to {new_name}")
            elif new_name in CONFIG_CRYPTO_PAIRS:
                self.log(f"{get_timestamp()} - Rename failed: {new_name} already exists")
        except Exception as e:
            self.log(f"{get_timestamp()} - Rename failed: {str(e)}")

    def refresh_prices(self):
        self.log(f"{get_timestamp()} - Refreshing prices manually...")
        current_pair = self.crypto_var.get()
        asyncio.run_coroutine_threadsafe(self.get_price_data_async(self.binance, CONFIG_CRYPTO_PAIRS[current_pair]['binance'], current_pair, 'binance'), self.loop)
        if self.coinbase and 'coinbase' in CONFIG_CRYPTO_PAIRS[current_pair]:
            asyncio.run_coroutine_threadsafe(self.get_price_data_async(self.coinbase, CONFIG_CRYPTO_PAIRS[current_pair], current_pair, 'coinbase'), self.loop)

    def log(self, message):
        try:
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
        except Exception as e:
            print(f"Log error: {str(e)}")

    def clear_log(self):
        try:
            self.log_text.delete("1.0", tk.END)
            self.log(f"{get_timestamp()} - Transaction Log Cleared")
        except Exception as e:
            self.log(f"{get_timestamp()} - Clear Log Failed: {str(e)}")

    def toggle_dry_run(self):
        CONFIG['DRY_RUN'] = self.dry_run_var.get()
        self.log(f"{get_timestamp()} - Dry Run {'Enabled' if CONFIG['DRY_RUN'] else 'Disabled'}")

    def update_config(self):
        CONFIG['BALANCE_PERCENTAGE'] = self.balance_pct_var.get()
        CONFIG['SIMULATED_BALANCE'] = self.simulated_balance_var.get()
        CONFIG['SMA_FAST'] = self.sma_fast_var.get()
        CONFIG['SMA_SLOW'] = self.sma_slow_var.get()
        self.log(f"{get_timestamp()} - Configuration Updated")
        for pair in OHLCV_HISTORY:
            OHLCV_HISTORY[pair]['binance'].maxlen = CONFIG['LIMIT']
            OHLCV_HISTORY[pair]['coinbase'].maxlen = CONFIG['LIMIT']

    def cash_out(self):
        if not self.strategies:
            self.log(f"{get_timestamp()} - Cash Out Failed: Strategies not initialized")
            return

        current_pair = self.crypto_var.get()
        total_cashout_profit = 0.0
        self.paused = True  # Pause trading to avoid conflicts
        self.log(f"{get_timestamp()} - Initiating Cash Out for {current_pair}")

        # Get current prices
        binance_price = float(self.price_var.get().replace('$', '')) if self.price_var.get() not in ["0.00", "N/A"] else 0
        coinbase_price = float(self.coinbase_price_var.get().replace('$', '')) if self.coinbase_price_var.get() not in ["0.00", "N/A"] else 0

        # Sell Binance holdings
        if POSITION[current_pair]['binance']['holding'] and binance_price > 0:
            amount = POSITION[current_pair]['binance']['amount']
            symbol = CONFIG_CRYPTO_PAIRS[current_pair]['binance']
            success = self.strategies.execute_trade(self.binance, "SELL", binance_price, amount, symbol, current_pair, "Cash Out")
            if success:
                profit = (binance_price - POSITION[current_pair]['binance']['entry_price']) * amount
                fees = binance_price * amount * CONFIG['FEE_RATE_BINANCE']
                total_cashout_profit += profit - fees
                self.log(f"{get_timestamp()} - {current_pair} - Cash Out Binance: Sold {amount:.6f} at ${binance_price:.2f}, Net Profit: ${profit - fees:.2f}")

        # Sell Coinbase holdings
        if self.coinbase and POSITION[current_pair]['coinbase']['holding'] and coinbase_price > 0:
            amount = POSITION[current_pair]['coinbase']['amount']
            symbol = CONFIG_CRYPTO_PAIRS[current_pair]['coinbase']
            success = self.strategies.execute_trade(self.coinbase, "SELL", coinbase_price, amount, symbol, current_pair, "Cash Out")
            if success:
                profit = (coinbase_price - POSITION[current_pair]['coinbase']['entry_price']) * amount
                fees = coinbase_price * amount * CONFIG['FEE_RATE_COINBASE']
                total_cashout_profit += profit - fees
                self.log(f"{get_timestamp()} - {current_pair} - Cash Out Coinbase: Sold {amount:.6f} at ${coinbase_price:.2f}, Net Profit: ${profit - fees:.2f}")

        # Update balance and reset positions
        if total_cashout_profit != 0:
            CONFIG['SIMULATED_BALANCE'] += total_cashout_profit
            PROFIT_TRACKER['total_profit'] += total_cashout_profit
            self.log(f"{get_timestamp()} - Cash Out Complete: Total Profit ${total_cashout_profit:.2f}, New Balance ${CONFIG['SIMULATED_BALANCE']:.2f}")
            write_profit_report()

        # Reset positions
        POSITION[current_pair]['binance'].update({'holding': False, 'amount': 0.0, 'entry_price': 0.0})
        POSITION[current_pair]['coinbase'].update({'holding': False, 'amount': 0.0, 'entry_price': 0.0})
        self.paused = False  # Resume trading

    def update_display(self, pair_prices):
        current_pair = self.crypto_var.get()
        binance_price = pair_prices[current_pair]['binance']
        coinbase_price = pair_prices[current_pair]['coinbase']

        self.price_var.set(f"${binance_price:.2f}" if binance_price > 0 else "N/A")
        self.coinbase_price_var.set(f"${coinbase_price:.2f}" if coinbase_price > 0 else "N/A")
        self.position_var.set(f"B: {'Holding' if POSITION[current_pair]['binance']['holding'] else 'None'} {POSITION[current_pair]['binance']['amount']:.6f} | "
                             f"C: {'Holding' if POSITION[current_pair]['coinbase']['holding'] else 'None'} {POSITION[current_pair]['coinbase']['amount']:.6f}")
        self.pl_var.set(f"${PROFIT_TRACKER['total_profit']:.2f}")
        self.sim_balance_display_var.set(f"${CONFIG['SIMULATED_BALANCE'] + PROFIT_TRACKER['total_profit']:.2f}")
        self.trade_count_var.set(str(PROFIT_TRACKER['trade_count']))
        self.last_trade_var.set(PROFIT_TRACKER['last_trade_time'] or "N/A")
        
        binance_prices = [candle[4] for candle in OHLCV_HISTORY[current_pair]['binance']]
        volatility = np.std(binance_prices[-CONFIG['VOLATILITY_WINDOW']:]) if len(binance_prices) >= CONFIG['VOLATILITY_WINDOW'] else 0
        self.volatility_var.set(f"{volatility:.4f}")

        if len(binance_prices) >= CONFIG['ATR_PERIOD']:
            try:
                from data_manager import calculate_atr
                atr = calculate_atr(OHLCV_HISTORY[current_pair]['binance'], CONFIG['ATR_PERIOD'])
                self.atr_var.set(f"{atr:.4f}")
            except Exception as e:
                self.atr_var.set("N/A")
                self.log(f"{get_timestamp()} - ATR Calculation Failed: {str(e)}")
        else:
            self.atr_var.set("N/A")

        if binance_price > 0 and coinbase_price > 0:
            price_diff = (binance_price - coinbase_price) / coinbase_price
            arbitrage_action = "Buy Coinbase, Sell Binance" if price_diff > 0 else "Buy Binance, Sell Coinbase"
            arbitrage_display = f"{arbitrage_action} ({price_diff:.2%})" if abs(price_diff) > CONFIG['CROSS_ARBITRAGE_THRESHOLD'] else "None"
            self.arbitrage_var.set(arbitrage_display)
            self.exchange_status_var.set("Active" if abs(price_diff) > CONFIG['CROSS_ARBITRAGE_THRESHOLD'] else "Idle")
        else:
            self.arbitrage_var.set("N/A")
            self.exchange_status_var.set("Idle")

        PRICE_HISTORY[current_pair].append((time.time(), binance_price, coinbase_price))
        timeframe = self.timeframe_var.get()
        time_window = 3600 if timeframe == "1 Hour" else 43200 if timeframe == "12 Hours" else 86400
        current_time = time.time()
        PRICE_HISTORY[current_pair] = deque([(t, bp, cp) for t, bp, cp in PRICE_HISTORY[current_pair] if t >= current_time - time_window], maxlen=1000)
        TRADE_MARKERS[current_pair] = deque([(t, p, s) for t, p, s in TRADE_MARKERS[current_pair] if t >= current_time - time_window], maxlen=1000)

        self.log(f"{get_timestamp()} - {current_pair} - TRADE_MARKERS before plot: {list(TRADE_MARKERS[current_pair])}")
    
        self.ax.clear()
        self.ax.grid(True, linestyle='--', alpha=0.3, color='#606060')
        if PRICE_HISTORY[current_pair]:
            times, b_prices, c_prices = zip(*PRICE_HISTORY[current_pair])
            times = [datetime.fromtimestamp(t) for t in times]
            if any(bp > 0 for bp in b_prices):
                self.ax.plot(times, b_prices, '#00FFFF', label='Binance', linewidth=1.5)
                if len(b_prices) >= CONFIG['SMA_SLOW']:
                    try:
                        sma_fast = [np.mean(list(b_prices)[max(0, i-CONFIG['SMA_FAST']):i+1]) for i in range(len(b_prices))]
                        sma_slow = [np.mean(list(b_prices)[max(0, i-CONFIG['SMA_SLOW']):i+1]) for i in range(len(b_prices))]
                        self.ax.plot(times, sma_fast, '#FF00FF', label='SMA Fast', linestyle='--')
                        self.ax.plot(times, sma_slow, '#00FF00', label='SMA Slow', linestyle='--')
                    except Exception as e:
                        self.log(f"{get_timestamp()} - SMA Plot Error: {str(e)}")
            if any(cp > 0 for cp in c_prices):
                self.ax.plot(times, c_prices, '#FFFF00', label='Coinbase', linewidth=1.5)
            buy_times = [datetime.fromtimestamp(t) for t, p, s in TRADE_MARKERS[current_pair] if s == "BUY"]
            buy_prices = [p for t, p, s in TRADE_MARKERS[current_pair] if s == "BUY"]
            sell_times = [datetime.fromtimestamp(t) for t, p, s in TRADE_MARKERS[current_pair] if s == "SELL"]
            sell_prices = [p for t, p, s in TRADE_MARKERS[current_pair] if s == "SELL"]
            if buy_times and buy_prices:
                self.ax.scatter(buy_times, buy_prices, color='green', marker='^', label='Buy', s=100)
            if sell_times and sell_prices:
                self.ax.scatter(sell_times, sell_prices, color='red', marker='v', label='Sell', s=100)
        self.ax.legend(facecolor=self.widget_bg, edgecolor=self.text_color, labelcolor=self.text_color)
        self.ax.set_title(f"{current_pair} Price Movement (Local Time)", color=self.text_color)
        self.ax.set_xlabel("Time (Local)", color=self.text_color)
        self.ax.set_ylabel("Price (USD)", color=self.text_color)
        self.fig.autofmt_xdate()
        self.canvas.draw()

    def manual_trade(self, signal):
        current_pair = self.crypto_var.get()
        binance_price = float(self.price_var.get().replace('$', '')) if self.price_var.get() not in ["0.00", "N/A"] else 0
        coinbase_price = float(self.coinbase_price_var.get().replace('$', '')) if self.coinbase_price_var.get() not in ["0.00", "N/A"] else 0
        
        if binance_price == 0 and coinbase_price == 0:
            self.log(f"{get_timestamp()} - {current_pair} - Manual {signal} Failed: No valid prices")
            return
        
        available_balance = (CONFIG['SIMULATED_BALANCE'] + PROFIT_TRACKER['total_profit']) * CONFIG['TRADE_SIZE_PERCENTAGE']
        min_price = min(binance_price, coinbase_price) if binance_price > 0 and coinbase_price > 0 else max(binance_price, coinbase_price)
        if min_price == 0:
            self.log(f"{get_timestamp()} - {current_pair} - Manual {signal} Failed: Insufficient price data")
            return
        
        amount = min(max(CONFIG['MIN_TRADE_AMOUNT'], available_balance / min_price),
                     (CONFIG['SIMULATED_BALANCE'] + PROFIT_TRACKER['total_profit']) * CONFIG['MAX_POSITION_PERCENTAGE'] / min_price)
        
        if signal == "BUY":
            exchange = self.binance if binance_price < coinbase_price or coinbase_price == 0 else self.coinbase
            price = binance_price if exchange == self.binance else coinbase_price
            symbol = CONFIG_CRYPTO_PAIRS[current_pair]['binance'] if exchange == self.binance else CONFIG_CRYPTO_PAIRS[current_pair]['coinbase']
        else:
            exchange = self.coinbase if POSITION[current_pair]['coinbase']['holding'] else self.binance if POSITION[current_pair]['binance']['holding'] else None
            if not exchange:
                self.log(f"{get_timestamp()} - {current_pair} - Manual {signal} Failed: No position to sell")
                return
            price = coinbase_price if exchange == self.coinbase else binance_price
            symbol = CONFIG_CRYPTO_PAIRS[current_pair]['coinbase'] if exchange == self.coinbase else CONFIG_CRYPTO_PAIRS[current_pair]['binance']

        if price > 0 and self.strategies:
            self.log(f"{get_timestamp()} - {current_pair} - Manual {signal} Initiated: {amount:.6f} {symbol} at ${price:.2f}")
            self.strategies.execute_trade(exchange, signal, price, amount, symbol, current_pair, "Manual")

    async def trading_loop(self):
        from config import CRYPTO_PAIRS
        LAST_REPORT_TIME = time.time()
        self.log(f"{get_timestamp()} - Multi-Strategy Trading Started")
        self.status_bar.config(text="Running")
        while self.running:
            if self.paused:
                self.status_bar.config(text="Paused")
                await asyncio.sleep(1)
                continue
            if not self.strategies:
                self.log(f"{get_timestamp()} - Waiting for exchange initialization...")
                await asyncio.sleep(1)
                continue
            try:
                current_pair = self.crypto_var.get()
                pair_prices = {pair: {'binance': 0.0, 'coinbase': 0.0} for pair in CRYPTO_PAIRS}

                tasks = []
                for pair in CRYPTO_PAIRS:
                    if 'binance' in CRYPTO_PAIRS[pair]:
                        tasks.append(asyncio.create_task(self.get_price_data_async(self.binance, CRYPTO_PAIRS[pair]['binance'], pair, 'binance')))
                    if 'coinbase' in CRYPTO_PAIRS[pair] and self.coinbase:
                        tasks.append(asyncio.create_task(self.get_price_data_async(self.coinbase, CRYPTO_PAIRS[pair]['coinbase'], pair, 'coinbase')))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                idx = 0
                current_time = time.time()
                for pair in CRYPTO_PAIRS:
                    if 'binance' in CRYPTO_PAIRS[pair]:
                        result = results[idx]
                        if isinstance(result, Exception) or result is None or result.empty:
                            self.log(f"{get_timestamp()} - {pair} - Binance Price Fetch Failed")
                            last_price, last_time = LAST_PRICES[pair]['binance']
                            if current_time - last_time < CONFIG['PRICE_TTL']:
                                pair_prices[pair]['binance'] = last_price
                        else:
                            last_candle = (result['timestamp'].iloc[-1], result['open'].iloc[-1], result['high'].iloc[-1],
                                          result['low'].iloc[-1], result['close'].iloc[-1], result['volume'].iloc[-1])
                            price = result['close'].iloc[-1]
                            pair_prices[pair]['binance'] = price
                            LAST_PRICES[pair]['binance'] = (price, current_time)
                            OHLCV_HISTORY[pair]['binance'].append(last_candle)
                        idx += 1
                    if 'coinbase' in CRYPTO_PAIRS[pair] and self.coinbase:
                        result = results[idx]
                        if isinstance(result, Exception) or result is None or result.empty:
                            self.log(f"{get_timestamp()} - {pair} - Coinbase Price Fetch Failed")
                            last_price, last_time = LAST_PRICES[pair]['coinbase']
                            if current_time - last_time < CONFIG['PRICE_TTL']:
                                pair_prices[pair]['coinbase'] = last_price
                        else:
                            last_candle = (result['timestamp'].iloc[-1], result['open'].iloc[-1], result['high'].iloc[-1],
                                          result['low'].iloc[-1], result['close'].iloc[-1], result['volume'].iloc[-1])
                            price = result['close'].iloc[-1]
                            pair_prices[pair]['coinbase'] = price
                            LAST_PRICES[pair]['coinbase'] = (price, current_time)
                            OHLCV_HISTORY[pair]['coinbase'].append(last_candle)
                        idx += 1

                await self.strategies.cross_exchange_arbitrage(pair_prices, current_pair)
                await self.strategies.scalping_strategy(pair_prices, current_pair)
                self.update_display(pair_prices)
                
                if PROFIT_TRACKER['total_profit'] < -CONFIG['CIRCUIT_BREAKER_THRESHOLD'] * CONFIG['SIMULATED_BALANCE']:
                    self.pause_trading()
                    self.log(f"{get_timestamp()} - Circuit Breaker Triggered: Loss exceeded {CONFIG['CIRCUIT_BREAKER_THRESHOLD']*100}%")
                
                if time.time() - LAST_REPORT_TIME >= 3600:
                    write_profit_report()
                    LAST_REPORT_TIME = time.time()

                await asyncio.sleep(CONFIG['LOOP_INTERVAL'] if PROFIT_TRACKER['trade_count'] > 5 else 0.5)
            except Exception as e:
                self.log(f"{get_timestamp()} - Trading Loop Error: {str(e)}")

    async def get_price_data_async(self, exchange, symbol, pair, exchange_name):
        from data_manager import get_price_data
        data = get_price_data(exchange, symbol)
        if data is None or data.empty:
            self.log(f"{get_timestamp()} - {pair} - {exchange_name} Data Fetch Failed: No data returned for {symbol}")
        return data

    def start_trading(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.log(f"{get_timestamp()} - Trading Started")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.thread = threading.Thread(target=lambda: self.loop.run_until_complete(self.trading_loop()))
            self.thread.daemon = True
            self.thread.start()

    def stop_trading(self):
        self.running = False
        self.paused = False
        self.log(f"{get_timestamp()} - Trading Stopped")
        self.status_bar.config(text="Stopped")
        write_profit_report()
        if hasattr(self, 'loop'):
            self.loop.call_soon_threadsafe(self.loop.stop)
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def pause_trading(self):
        self.paused = not self.paused
        self.log(f"{get_timestamp()} - Trading {'Paused' if self.paused else 'Resumed'}")
        self.status_bar.config(text="Paused" if self.paused else "Running")

    def reset_positions(self):
        current_pair = self.crypto_var.get()
        POSITION[current_pair]['binance'].update({'holding': False, 'amount': 0.0, 'entry_price': 0.0})
        POSITION[current_pair]['coinbase'].update({'holding': False, 'amount': 0.0, 'entry_price': 0.0})
        self.log(f"{get_timestamp()} - {current_pair} - Positions Reset")

    def export_log(self):
        try:
            filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"trade_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt")
            with open(filename, 'w') as f:
                f.write(self.log_text.get("1.0", tk.END))
            self.log(f"{get_timestamp()} - Log Exported Successfully: {filename}")
            messagebox.showinfo("Export", "Log exported successfully!")
        except Exception as e:
            self.log(f"{get_timestamp()} - Export Log Failed: {str(e)}")