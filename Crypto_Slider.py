import requests
import json
import threading
import time

class CryptoSlider:
    """
    Manages fetching cryptocurrency conversion rates from Binance API
    and provides methods to access these rates.
    """
    def __init__(self):
        # Binance API endpoints for USDT conversion
        self.usdt_api_endpoints = {
            "BTC": "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            "LTC": "https://api.binance.com/api/v3/ticker/price?symbol=LTCUSDT",
            "BNB": "https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT",
            "POL": "https://api.binance.com/api/v3/ticker/price?symbol=POLYXUSDT", # POLYX is the symbol for POL
            "XRP": "https://api.binance.com/api/v3/ticker/price?symbol=XRPUSDT",
            "DOGE": "https://api.binance.com/api/v3/ticker/price?symbol=DOGEUSDT",
            "ETH": "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
            "TRX": "https://api.binance.com/api/v3/ticker/price?symbol=TRXUSDT",
            "SOL": "https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT"
        }

        # Binance API endpoints for EUR conversion (NEW)
        self.eur_api_endpoints = {
            "BTC": "https://api.binance.com/api/v3/ticker/price?symbol=BTCEUR",
            "LTC": "https://api.binance.com/api/v3/ticker/price?symbol=LTCEUR",
            "BNB": "https://api.binance.com/api/v3/ticker/price?symbol=BNBEUR",
            "POL": "https://api.binance.com/api/v3/ticker/price?symbol=POLYXEUR", # POLYX is the symbol for POL
            "XRP": "https://api.binance.com/api/v3/ticker/price?symbol=XRPEUR",
            "DOGE": "https://api.binance.com/api/v3/ticker/price?symbol=DOGEEUR",
            "ETH": "https://api.binance.com/api/v3/ticker/price?symbol=ETHEUR",
            "TRX": "https://api.binance.com/api/v3/ticker/price?symbol=TRXEUR",
            "SOL": "https://api.binance.com/api/v3/ticker/price?symbol=SOLEUR"
        }

        # Initialize dictionaries to store fetched rates
        self._usdt_rates = {}
        self._eur_rates = {} # New: To store EUR rates

        # Lock for thread-safe access to rates
        self._rates_lock = threading.Lock()

        print("DEBUG: CryptoSlider: Initialized with Binance API URLs.")

    def _fetch_rates_for_currency(self, endpoints, target_rates_dict):
        """
        Internal helper to fetch rates for a given set of endpoints and store them
        in the specified target dictionary.
        """
        fetched_data = {}
        for crypto_symbol, url in endpoints.items():
            try:
                response = requests.get(url, timeout=5) # 5-second timeout
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                data = response.json()
                price = float(data['price'])
                fetched_data[crypto_symbol] = price
                print(f"DEBUG: Fetched {crypto_symbol} price from {url}: {price}")
            except requests.exceptions.RequestException as e:
                print(f"ERROR: Failed to fetch {crypto_symbol} price from {url}: {e}")
            except json.JSONDecodeError:
                print(f"ERROR: Could not decode JSON from response for {url}")
            except KeyError:
                print(f"ERROR: 'price' key not found in JSON response for {url}")
            except ValueError:
                print(f"ERROR: Could not convert price to float for {url}")

        with self._rates_lock:
            target_rates_dict.update(fetched_data)
            # Add RLT and RST dummy rates as they are not on Binance
            if "RLT" not in target_rates_dict:
                target_rates_dict["RLT"] = 0.5 # Default dummy rate for RLT
            if "RST" not in target_rates_dict:
                target_rates_dict["RST"] = 0.0001 # Default dummy rate for RST
        print(f"DEBUG: Updated rates: {target_rates_dict}")

    def fetch_usdt_conversion_rates(self):
        """
        Fetches the latest USDT conversion rates in a separate thread.
        """
        print("DEBUG: CryptoSlider: Starting USDT conversion rate fetch.")
        fetch_thread = threading.Thread(
            target=self._fetch_rates_for_currency,
            args=(self.usdt_api_endpoints, self._usdt_rates)
        )
        fetch_thread.daemon = True # Allow the thread to exit with the main program
        fetch_thread.start()

    def fetch_euro_conversion_rates(self):
        """
        Fetches the latest EUR conversion rates in a separate thread. (NEW)
        """
        print("DEBUG: CryptoSlider: Starting EUR conversion rate fetch.")
        fetch_thread = threading.Thread(
            target=self._fetch_rates_for_currency,
            args=(self.eur_api_endpoints, self._eur_rates)
        )
        fetch_thread.daemon = True # Allow the thread to exit with the main program
        fetch_thread.start()

    def get_usdt_rates(self):
        """
        Returns the currently stored USDT conversion rates.
        """
        with self._rates_lock:
            return self._usdt_rates.copy() # Return a copy to prevent external modification

    def get_euro_rates(self):
        """
        Returns the currently stored EUR conversion rates. (NEW)
        """
        with self._rates_lock:
            return self._eur_rates.copy() # Return a copy to prevent external modification

if __name__ == "__main__":
    # Example usage for testing
    slider = CryptoSlider()

    print("Fetching USDT rates...")
    slider.fetch_usdt_conversion_rates()
    time.sleep(3) # Give thread time to fetch
    print("Current USDT Rates:", slider.get_usdt_rates())

    print("\nFetching EUR rates...")
    slider.fetch_euro_conversion_rates()
    time.sleep(3) # Give thread time to fetch
    print("Current EUR Rates:", slider.get_euro_rates())

    # Keep the main thread alive for a bit to allow daemon threads to finish
    time.sleep(5)
    print("Exiting test.")
