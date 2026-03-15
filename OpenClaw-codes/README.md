# OpenClaw-codes: Tradier Market Data Monitor

This repository contains a Python script, `fetch_tradier_data.py`, designed to interact with the Tradier API for fetching stock and option market data, and then persisting this data into a local SQLite database. It's built for use within an OpenClaw agent environment to enable automated market data monitoring and analysis.

The script also manages a `monitor_target` table, allowing you to easily add, remove, activate, or deactivate stock and option symbols for automated fetching.

## Features

-   **Stock Data Fetching:** Retrieves real-time stock quotes for specified symbols.
-   **Option Data Fetching:** Retrieves detailed option chain data for specified option symbols, including Greeks (delta, gamma, theta, vega, rho), open interest, and volume.
-   **SQLite Integration:** Stores fetched stock and option data into a `tradier_market_data.db` SQLite database, adhering to a defined schema.
-   **Monitor Target Management:** A `monitor_target` table in the database allows for dynamic management of symbols to be monitored, replacing the need for direct JSON input for fetching.
-   **Command-Line Interface:** Easy-to-use commands for database initialization, target management, data fetching, and historical data querying.
-   **Debug Logging:** Provides detailed debug output for troubleshooting, especially for option symbol parsing and fetching.

## Setup

1.  **Navigate to the `OpenClaw-codes` directory:**
    ```bash
    cd ~/.openclaw/workspace/OpenClaw-codes
    ```

2.  **Create and activate a Python virtual environment (if you haven't already):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install required Python packages:**
    ```bash
    pip install requests
    ```

4.  **Set your Tradier API Key as an environment variable:**
    Obtain your API key from [Tradier](https://developer.tradier.com/).
    ```bash
    export TRADIER_API_KEY="YOUR_TRADIER_API_KEY_HERE"
    # Example: export TRADIER_API_KEY="Fn6Yb76XhAtPCUXeLLRJGxuPsBVy"
    ```
    Replace `YOUR_TRADIER_API_KEY_HERE` with your actual key.

## Usage

The script `fetch_tradier_data.py` supports several commands: `init-db`, `add-target`, `remove-target`, `list-targets`, `activate-target`, `deactivate-target`, `fetch`, and `query`.

### Initialize Database

This command initializes the `tradier_market_data.db` SQLite database and creates the `stocks`, `options`, and `monitor_target` tables based on the defined schema. You only need to run this once.

```bash
python fetch_tradier_data.py init-db
```

### Manage Monitoring Targets

These commands allow you to add, remove, list, activate, and deactivate stock and option symbols in the `monitor_target` table.

#### Add Target
Adds a new symbol to the `monitor_target` table. Specify the `symbol` and `type` (`stock` or `option`).

```bash
python fetch_tradier_data.py add-target TSLA stock
python fetch_tradier_data.py add-target CRWV stock
python fetch_tradier_data.py add-target TSLA260327P00380000 option
python fetch_tradier_data.py add-target TSLA260417P00365000 option
```

#### List Targets
Lists all monitoring targets, or filters by active/inactive status.

```bash
# List all targets
python fetch_tradier_data.py list-targets

# List only active targets
python fetch_tradier_data.py list-targets active

# List only inactive targets
python fetch_tradier_data.py list-targets inactive
```

#### Activate/Deactivate Target
Changes the `is_active` status of a symbol.

```bash
# Activate a target
python fetch_tradier_data.py activate-target TSLA

# Deactivate a target
python fetch_tradier_data.py deactivate-target CRWV
```

#### Remove Target
Removes a symbol from the `monitor_target` table.

```bash
python fetch_tradier_data.py remove-target CRWV
```

### Fetch Market Data

This command fetches market data for all **active** symbols defined in the `monitor_target` table. The fetched data (stocks and options) is then saved into the `stocks` and `options` tables in `tradier_market_data.db`.

```bash
python fetch_tradier_data.py fetch
```

#### Fetch with Debugging
To enable detailed debug logging for a specific option symbol during a `fetch` operation, use the `--debug-option` flag. This will print verbose debug messages related to parsing and fetching that particular option.

```bash
python fetch_tradier_data.py fetch --debug-option TSLA260327P00380000
```

### Query Saved Data

Queries historical stock or option data from the `tradier_market_data.db` database.

```bash
# Query the 10 most recent stock entries
python fetch_tradier_data.py query stocks

# Query the 5 most recent stock entries for TSLA
python fetch_tradier_data.py query stocks TSLA 5

# Query the 10 most recent option entries
python fetch_tradier_data.py query options

# Query the 3 most recent option entries for a specific option symbol
python fetch_tradier_data.py query options TSLA260327P00380000 3
```

## Database Schema (`tradier_market_data.db`)

The database structure aligns with `schema.sql` in this repository.

### `stocks` Table
Stores historical stock data.

| Column          | Type    | Description                               |
| :-------------- | :------ | :---------------------------------------- |
| `id`            | INTEGER | Primary Key, Auto-increment               |
| `symbol`        | TEXT    | Stock ticker symbol (e.g., TSLA)          |
| `last_price`    | REAL    | Last traded price                         |
| `change_value`  | REAL    | Change in price                           |
| `change_percent`| REAL    | Percentage change in price                |
| `volume`        | INTEGER | Trading volume                            |
| `fetch_timestamp`| DATETIME| Timestamp when data was fetched           |

### `options` Table
Stores historical option contract data.

| Column          | Type    | Description                               |
| :-------------- | :------ | :---------------------------------------- |
| `id`            | INTEGER | Primary Key, Auto-increment               |
| `symbol`        | TEXT    | OCC Option Symbol (e.g., TSLA260327P00380000) |
| `underlying`    | TEXT    | Underlying stock symbol                   |
| `expiration_date`| TEXT   | Expiration date (YYYY-MM-DD)              |
| `strike_price`  | REAL    | Strike price                              |
| `option_type`   | TEXT    | Type of option ('call' or 'put')          |
| `last_price`    | REAL    | Last traded price                         |
| `delta`         | REAL    | Option Delta                              |
| `gamma`         | REAL    | Option Gamma                              |
| `theta`         | REAL    | Option Theta                              |
| `vega`          | REAL    | Option Vega                               |
| `rho`           | REAL    | Option Rho                                |
| `bid_iv`        | REAL    | Bid Implied Volatility                    |
| `mid_iv`        | REAL    | Mid Implied Volatility                    |
| `ask_iv`        | REAL    | Ask Implied Volatility                    |
| `open_interest` | INTEGER | Open Interest                             |
| `volume`        | INTEGER | Trading volume                            |
| `fetch_timestamp`| DATETIME| Timestamp when data was fetched           |

### `monitor_target` Table
Stores the list of symbols to be actively monitored.

| Column          | Type    | Description                               |
| :-------------- | :------ | :---------------------------------------- |
| `id`            | INTEGER | Primary Key, Auto-increment               |
| `symbol`        | TEXT    | Stock or option symbol (UNIQUE)           |
| `type`          | TEXT    | 'stock' or 'option'                       |
| `is_active`     | INTEGER | 1 for active, 0 for inactive (DEFAULT 1)  |

---
