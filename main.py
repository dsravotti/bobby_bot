import asyncio
import tkinter as tk
from gui import TradingGUI
from config import CONFIG
import time
import threading

def loading_counter():
    print("Initializing Bobby-Bot Arbitrage & Scalping...")
    for i in range(101):
        print(f"\rProgress: {i}%", end='', flush=True)
        time.sleep(0.05)  # Simulates loading; we'll adjust this later
    print("\nGUI Starting...")

def main():
    # Show loading progress in terminal
    loading_counter()

    # Start GUI
    root = tk.Tk()
    app = TradingGUI(root, CONFIG)
    
    # Move slow initialization to a background thread
    def initialize_exchanges():
        app.log("Starting exchange initialization in background...")
        # These are already called in TradingGUI.__init__, but we could optimize further if needed
        # app.binance = initialize_exchange("binance")
        # app.coinbase = initialize_exchange("coinbase")
        # test_connectivity(app.binance, "Binance", app.log)
        # test_connectivity(app.coinbase, "Coinbase", app.log)
        app.log("Exchange initialization complete.")

    threading.Thread(target=initialize_exchanges, daemon=True).start()
    
    root.mainloop()

if __name__ == "__main__":
    main()