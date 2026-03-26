import json
import os
import sys
import requests
import re
import sqlite3
import datetime

TRADIER_BASE_URL = "https://api.tradier.com/v1/markets"
DATABASE_NAME = "tradier_market_data.db"

# Global flag for debug printing
ENABLE_OPTION_DEBUG = False
DEBUG_TARGET_OPTION = None

def print_debug(message):
    # Only print debug messages if ENABLE_OPTION_DEBUG is True and it's for the target option
    if ENABLE_OPTION_DEBUG:
        print(f"DEBUG: {datetime.datetime.now().isoformat()} - {message}")

def init_db():
    """
    Initializes the SQLite database and creates tables for stocks and options.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create stocks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            type TEXT,
            price REAL,
            change_value REAL,
            change_percent REAL,
            volume INTEGER,
            currency TEXT,
            source TEXT,
            fetch_timestamp TEXT NOT NULL
        )
    """)

    # Create options table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            underlying TEXT,
            type TEXT,
            strike REAL,
            expiration TEXT,
            price REAL,
            bid REAL,
            ask REAL,
            delta REAL,
            gamma REAL,
            theta REAL,
            vega REAL,
            rho REAL,
            open_interest INTEGER,
            volume INTEGER,
            currency TEXT,
            source TEXT,
            fetch_timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_stock_data(data):
    """
    Saves stock data to the 'stocks' table.
    """
    print_debug(f"Attempting to save stock data for: {data.get('symbol')}")
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stocks (symbol, type, price, change_value, change_percent, volume, currency, source, fetch_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['symbol'], data['type'], data['price'], data.get('change_value'),
        data.get('change_percent'), data.get('volume'), data['currency'],
        data['source'], data['fetch_timestamp']
    ))
    conn.commit()
    conn.close()
    print_debug(f"Successfully saved stock data for: {data.get('symbol')}")

def save_option_data(data):
    """
    Saves option data to the 'options' table.
    """
    print_debug(f"Attempting to save option data for: {data.get('symbol')}")
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO options (symbol, underlying, type, strike, expiration, price, bid, ask, delta, gamma, theta, vega, rho, open_interest, volume, currency, source, fetch_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['symbol'], data['underlying'], data['type'], data['strike'], data['expiration'],
        data.get('price'), data.get('bid'), data.get('ask'), data.get('delta'),
        data.get('gamma'), data.get('theta'), data.get('vega'), data.get('rho'),
        data.get('open_interest'), data.get('volume'), data['currency'],
        data['source'], data['fetch_timestamp']
    ))
    conn.commit()
    conn.close()
    print_debug(f"Successfully saved option data for: {data.get('symbol')}")

def query_saved_data(table: str, symbol: str = None, limit: int = 10):
    """
    Queries saved data from the specified table.
    """
    print_debug(f"Querying table: {table}, symbol: {symbol}, limit: {limit}")
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    query = f"SELECT * FROM {table}"
    params = []
    if symbol:
        query += " WHERE symbol = ?"
        params.append(symbol)
    query += f" ORDER BY fetch_timestamp DESC LIMIT {limit}"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    
    result = []
    for row in rows:
        result.append(dict(zip(column_names, row)))
    
    conn.close()
    print_debug(f"Query returned {len(result)} rows.")
    return result

def parse_option_symbol(option_symbol: str):
    """
    Parses a Tradier option symbol (e.g., TSLA260327P0038000) into its components.
    Returns (underlying_symbol, expiration_date, option_type, strike_price).
    """
    # Note: Tradier OCC symbols can have varying strike price formats. 
    # The '0038000' format means $380.00. The last three digits are decimals.
    # OCC format: SYMBOL + YYMMDD + Call/Put + STRIKE_PRICE (5 digits before decimal, 3 after)
    match = re.match(r"([A-Z]+)(\d{6})([CP])(\d{5})(\d{3})", option_symbol) # Changed \d{7} to \d{8} total strike digits here
    if not match:
        print_debug(f"No regex match for option symbol in parse_option_symbol: {option_symbol}")
        return None, None, None, None

    underlying_symbol = match.group(1)
    expiration_raw = match.group(2)
    option_type = 'put' if match.group(3) == 'P' else 'call'
    # strike_whole = match.group(4) # This was \d{4}
    # strike_fraction = match.group(5) # This was \d{3}
    # Now with \d{8} it's just one group for strike_raw
    strike_raw_digits = match.group(4) + match.group(5) # Recombine to 8 digits

    # Reconstruct expiration date as YYYY-MM-DD
    year = "20" + expiration_raw[:2]
    month = expiration_raw[2:4]
    day = expiration_raw[4:6]
    expiration_date = f"{year}-{month}-{day}"

    # Convert strike price (e.g., 00380 + 000 -> 380.000)
    # The strike_raw_digits is now '00380000' for 380.000
    # Need to handle the 3 decimal places correctly
    try:
        strike_price = float(strike_raw_digits) / 1000.0
    except ValueError:
        print_debug(f"Error converting strike price: {strike_raw_digits}")
        strike_price = None

    print_debug(f"Parsed option: Underlying={underlying_symbol}, Expiration={expiration_date}, Type={option_type}, Strike={strike_price}")
    return underlying_symbol, expiration_date, option_type, strike_price

def fetch_option_data(api_key: str, option_symbol: str):
    """
    Fetches data for a specific option symbol by first getting the option chain.
    """
    global ENABLE_OPTION_DEBUG
    original_enable_debug = ENABLE_OPTION_DEBUG # Save original state
    
    # Temporarily enable debug for this option if it's the target
    if DEBUG_TARGET_OPTION and option_symbol == DEBUG_TARGET_OPTION:
        ENABLE_OPTION_DEBUG = True

    underlying_symbol, expiration_date, option_type, strike_price = parse_option_symbol(option_symbol)

    if not all([underlying_symbol, expiration_date, option_type, strike_price is not None]): # Check strike_price specifically
        print_debug(f"Error: Invalid option symbol format or parsing failed for: {option_symbol}")
        ENABLE_OPTION_DEBUG = original_enable_debug # Restore debug state
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    # First, get the option chain for the underlying and expiration
    chain_endpoint = f"{TRADIER_BASE_URL}/options/chains"
    chain_params = {
        "symbol": underlying_symbol,
        "expiration": expiration_date,
        "greeks": "true" # Fetch Greeks for options
    }

    try:
        print_debug(f"Fetching option chain from {chain_endpoint} with params: {chain_params}")
        response = requests.get(chain_endpoint, headers=headers, params=chain_params)
        response.raise_for_status()
        chain_data = response.json()

        print_debug(f"Raw option chain data for {underlying_symbol} {expiration_date}: {json.dumps(chain_data, indent=2)}")

        if 'options' in chain_data and chain_data['options'] and 'option' in chain_data['options']:
            options_list = chain_data['options']['option']
            
            # Ensure options_list is always a list for consistent iteration
            if isinstance(options_list, dict):
                options_list = [options_list]

            for option in options_list:
                print_debug(f"Checking option in chain: Symbol={option.get('symbol')}, Type={option.get('option_type')}, Strike={option.get('strike')}")

                # Match option type and strike price
                if option.get('option_type') == option_type and abs(option.get('strike') - strike_price) < 0.001:
                    # Found the specific option
                    print_debug(f"Matching option found: {option.get('symbol')}")
                    option_result = {
                        "symbol": option['symbol'],
                        "underlying": underlying_symbol,
                        "type": option_type,
                        "strike": option['strike'],
                        "expiration": expiration_date,
                        "price": option.get('last'),
                        "bid": option.get('bid'),
                        "ask": option.get('ask'),
                        "delta": option.get('greeks', {}).get('delta'),
                        "gamma": option.get('greeks', {}).get('gamma'),
                        "theta": option.get('greeks', {}).get('theta'),
                        "vega": option.get('greeks', {}).get('vega'),
                        "rho": option.get('greeks', {}).get('rho'),
                        "open_interest": option.get('open_interest'),
                        "volume": option.get('volume'),
                        "currency": "USD",
                        "source": "tradier",
                        "fetch_timestamp": datetime.datetime.now().isoformat()
                    }
                    ENABLE_OPTION_DEBUG = original_enable_debug # Restore debug state
                    return option_result
            print_debug(f"No matching option found in chain for {option_symbol}")
        else:
            print_debug(f"No 'option' list found in chain data for {underlying_symbol} on {expiration_date}.")
        ENABLE_OPTION_DEBUG = original_enable_debug # Restore debug state
        return None

    except requests.exceptions.RequestException as e:
        print_debug(f"Error fetching option chain from Tradier: {e}")
        ENABLE_OPTION_DEBUG = original_enable_debug # Restore debug state
        return None
    except Exception as e:
        print_debug(f"An unexpected error occurred while fetching option data: {e}")
        ENABLE_OPTION_DEBUG = original_enable_debug # Restore debug state
        return None
    finally:
        ENABLE_OPTION_DEBUG = original_enable_debug # Ensure debug state is restored even on unhandled errors

def fetch_tradier_data(active_items_json, debug_option_symbol=None):
    global ENABLE_OPTION_DEBUG, DEBUG_TARGET_OPTION
    
    if debug_option_symbol:
        ENABLE_OPTION_DEBUG = True
        DEBUG_TARGET_OPTION = debug_option_symbol
    
    api_key = os.environ.get('TRADIER_API_KEY')
    if not api_key:
        print("Error: TRADIER_API_KEY environment variable not set.") # Keep this as print for critical error
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    try:
        active_items = json.loads(active_items_json)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input for active monitor items.") # Keep this as print for critical error
        sys.exit(1)

    stock_symbols_to_fetch = []
    option_symbols_to_fetch = []
    
    for item in active_items:
        symbol = item['symbol'].strip() # Apply strip() here
        # Corrected heuristic to distinguish stock vs. option: use \d{8} for the strike digits
        if re.match(r"^[A-Z]+\d{6}[CP]\d{8}$", symbol):
            option_symbols_to_fetch.append(symbol)
        else:
            stock_symbols_to_fetch.append(symbol)

    print_debug(f"Symbols categorized: Stocks={stock_symbols_to_fetch}, Options={option_symbols_to_fetch}")

    all_fetched_data = {
        "timestamp": datetime.datetime.now().isoformat(), # Use current time for overall fetch
        "data": []
    }
    current_fetch_timestamp = datetime.datetime.now().isoformat()

    # Fetch stock quotes
    if stock_symbols_to_fetch:
        symbols_str = ",".join(stock_symbols_to_fetch)
        try:
            print_debug(f"Fetching stock quotes for: {symbols_str}")
            response = requests.get(
                f"{TRADIER_BASE_URL}/quotes",
                params={'symbols': symbols_str, 'greeks': 'false'},
                headers=headers
            )
            response.raise_for_status()
            quotes_data = response.json()

            if 'quotes' in quotes_data and quotes_data['quotes'] and 'quote' in quotes_data['quotes']:
                quotes_list = quotes_data['quotes']['quote']
                if isinstance(quotes_list, dict):
                    quotes_list = [quotes_list]

                for quote in quotes_list:
                    if 'symbol' in quote and 'last' in quote and 'type' in quote:
                        stock_entry = {
                            "symbol": quote['symbol'],
                            "type": quote['type'],
                            "price": quote['last'],
                            "change_value": quote.get('change'),
                            "change_percent": quote.get('change_percentage'),
                            "volume": quote.get('volume'),
                            "currency": "USD",
                            "source": "tradier",
                            "fetch_timestamp": current_fetch_timestamp
                        }
                        all_fetched_data["data"].append(stock_entry)
                        save_stock_data(stock_entry) # Save to DB
        except requests.exceptions.RequestException as e:
            print_debug(f"Error fetching stock quotes from Tradier: {e}")
        except Exception as e:
            print_debug(f"An unexpected error occurred while processing stock quotes: {e}")

    # Fetch option data
    for option_symbol in option_symbols_to_fetch:
        print_debug(f"Attempting to fetch data for option symbol: {option_symbol}")
        option_data = fetch_option_data(api_key, option_symbol)
        if option_data:
            option_data["fetch_timestamp"] = current_fetch_timestamp
            all_fetched_data["data"].append(option_data)
            save_option_data(option_data) # Save to DB
        else:
            print_debug(f"Could not retrieve data for option: {option_symbol}")
            # Optionally, you might want to add a placeholder or error entry for this option

    print(json.dumps(all_fetched_data, indent=2))

if __name__ == '__main__':
    init_db() # Initialize the database at script start

    # Parse additional command-line arguments for debugging
    debug_option_symbol = None
    args_to_pass = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--debug-option" and i + 1 < len(sys.argv):
            debug_option_symbol = sys.argv[i+1]
            i += 2 # Skip the option symbol
        else:
            args_to_pass.append(sys.argv[i])
            i += 1

    if len(args_to_pass) > 0:
        command = args_to_pass[0]
        if command == "fetch":
            if len(args_to_pass) > 1:
                active_items_json = args_to_pass[1]
                fetch_tradier_data(active_items_json, debug_option_symbol)
            else:
                print("Usage: python fetch_tradier_data.py fetch '<active_monitor_items_json>'")
                sys.exit(1)
        elif command == "query":
            if len(args_to_pass) > 1:
                table = args_to_pass[1]
                symbol = args_to_pass[2] if len(args_to_pass) > 2 else None
                limit = int(args_to_pass[3]) if len(args_to_pass) > 3 else 10
                results = query_saved_data(table, symbol, limit)
                print(json.dumps(results, indent=2))
            else:
                print("Usage: python fetch_tradier_data.py query <table_name> [symbol] [limit]")
                sys.exit(1)
        else:
            print("Unknown command. Use 'fetch' or 'query'.")
            sys.exit(1)
    else:
        print("Usage: python fetch_tradier_data.py <command> ... [--debug-option <symbol>]")
        sys.exit(1)