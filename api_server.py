import os
import json
import subprocess
import sys
from flask import Flask, request, jsonify
from functools import wraps
import datetime

app = Flask(__name__)

# --- Debug Configuration ---
DEBUG_API = True # Set to True to enable debug prints for api_server.py

def print_api_debug(message):
    if DEBUG_API:
        print(f"[API_DEBUG] {datetime.datetime.now().isoformat()}: {message}", file=sys.stderr)

# --- Configuration ---
API_AUTH_TOKEN = os.environ.get('API_AUTH_TOKEN')
FETCH_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'fetch_tradier_data.py')

# --- Helper for running subprocess commands ---
def run_fetch_script(command, *args):
    cmd = ['python3', FETCH_SCRIPT_PATH, command] + list(args)
    print_api_debug(f"Executing fetch_tradier_data.py command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.stderr.strip():
            print_api_debug(f"fetch_tradier_data.py STDERR:\n{result.stderr.strip()}")

        if result.stdout.strip():
            print_api_debug(f"fetch_tradier_data.py STDOUT:\n{result.stdout.strip()}")
            return json.loads(result.stdout.strip()), 200 # Always return data and a 200 status code
        print_api_debug(f"fetch_tradier_data.py STDOUT was empty.")
        return {}, 200 # Return empty dict and 200 if no output, assuming success for some commands that don't return data
    except subprocess.CalledProcessError as e:
        error_message = f"Script execution failed for command {command}: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}"
        print_api_debug(f"ERROR during script execution: {error_message}")
        return {"error": error_message}, 500
    except json.JSONDecodeError:
        error_message = f"Failed to decode JSON from script output for command {command}. Raw output: {result.stdout}"
        print_api_debug(f"ERROR decoding JSON: {error_message}")
        return {"error": error_message}, 500
    except Exception as e:
        error_message = f"An unexpected error occurred while running script {command}: {e}"
        print_api_debug(f"UNEXPECTED ERROR: {error_message}")
        return {"error": error_message}, 500

# --- Authentication Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        print_api_debug("Checking token authentication...")
        if not API_AUTH_TOKEN:
            print_api_debug("API authentication token not configured on server.")
            return jsonify({'message': 'API authentication token not configured on server.'}), 500

        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        
        if not token or token != API_AUTH_TOKEN:
            print_api_debug(f"Authentication failed. Token received: {token}")
            return jsonify({'message': 'Authentication Required: Invalid or missing token!'}), 401

        print_api_debug("Authentication successful.")
        return f(*args, **kwargs)
    return decorated

# --- API Endpoints ---

@app.route('/', methods=['GET'])
def index():
    print_api_debug("Received request for /")
    return jsonify({"message": "Tradier Market Data API. Use /api/fetch, /api/query, /api/targets, etc."})

@app.route('/api/fetch', methods=['POST'])
@token_required
def fetch_data_endpoint():
    print_api_debug("Received request for /api/fetch")
    result, status_code = run_fetch_script('fetch', '--global-debug')
    print_api_debug(f"Response from /api/fetch: Status={status_code}, Result={result}")
    return jsonify(result), status_code

@app.route('/api/query/<table_name>', methods=['GET'])
@token_required
def query_data_endpoint(table_name):
    symbol = request.args.get('symbol')
    limit = request.args.get('limit', default=10, type=int)
    print_api_debug(f"Received request for /api/query/{table_name} with symbol={symbol}, limit={limit}")

    if table_name not in ['stocks', 'options']:
        print_api_debug(f"Invalid table name: {table_name}")
        return jsonify({"error": "Invalid table name. Must be 'stocks' or 'options'."}), 400
    
    args = [table_name]
    if symbol:
        args.append(symbol)
    args.append(str(limit))

    result, status_code = run_fetch_script('query', *args)
    print_api_debug(f"Response from /api/query/{table_name}: Status={status_code}, Result={result}")
    return jsonify(result), status_code

@app.route('/api/targets', methods=['GET'])
@token_required
def list_targets_endpoint():
    status_filter = request.args.get('status') 
    print_api_debug(f"Received request for /api/targets with status_filter={status_filter or 'all'}")
    args = []
    if status_filter:
        args.append(status_filter)
    result, status_code = run_fetch_script('list-targets', *args)
    print_api_debug(f"Response from /api/targets: Status={status_code}, Result={result}")
    return jsonify(result), status_code

@app.route('/api/target', methods=['POST', 'DELETE'])
@token_required
def manage_target_endpoint():
    if request.method == 'POST':
        data = request.get_json()
        symbol = data.get('symbol')
        target_type = data.get('type')
        print_api_debug(f"Received POST request for /api/target with symbol={symbol}, type={target_type}")

        if not symbol or not target_type:
            print_api_debug("Missing symbol or type in POST request.")
            return jsonify({"error": "Missing 'symbol' or 'type' in request body."}), 400
        if target_type not in ['stock', 'option']:
            print_api_debug(f"Invalid target type: {target_type}")
            return jsonify({"error": "Invalid target 'type'. Must be 'stock' or 'option'."}), 400
        
        result, status_code = run_fetch_script('add-target', symbol, target_type)
        print_api_debug(f"Response from add-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code

    elif request.method == 'DELETE':
        data = request.get_json()
        symbol = data.get('symbol')
        print_api_debug(f"Received DELETE request for /api/target with symbol={symbol}")

        if not symbol:
            print_api_debug("Missing symbol in DELETE request.")
            return jsonify({"error": "Missing 'symbol' in request body."}), 400
        
        result, status_code = run_fetch_script('remove-target', symbol)
        print_api_debug(f"Response from remove-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code

@app.route('/api/target/<symbol>/<action>', methods=['POST'])
@token_required
def toggle_target_status_endpoint(symbol, action):
    print_api_debug(f"Received POST request for /api/target/{symbol}/{action}")
    if action == 'activate':
        result, status_code = run_fetch_script('activate-target', symbol)
        print_api_debug(f"Response from activate-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code
    elif action == 'deactivate':
        result, status_code = run_fetch_script('deactivate-target', symbol)
        print_api_debug(f"Response from deactivate-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code
    else:
        print_api_debug(f"Invalid action: {action}")
        return jsonify({"error": "Invalid action. Must be 'activate' or 'deactivate'."}), 400


@app.route('/api/init-db', methods=['POST'])
@token_required
def init_db_endpoint():
    print_api_debug("Received request for /api/init-db")
    result, status_code = run_fetch_script('init-db')
    print_api_debug(f"Response from /api/init-db: Status={status_code}, Result={result}")
    return jsonify(result), status_code

if __name__ == '__main__':
    if not API_AUTH_TOKEN:
        print_api_debug("ERROR: API_AUTH_TOKEN environment variable not set.")
        print("ERROR: API_AUTH_TOKEN environment variable not set. Please set it before running the API server.")
        sys.exit(1)
    print_api_debug("Starting Flask app...")
    app.run(host='0.0.0.0', port=5000, debug=False)
