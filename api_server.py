import os
import json
import subprocess
import sys
import random
import bcrypt
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from functools import wraps
import datetime
import pyotp # Import pyotp


app = Flask(__name__, static_folder='.', static_url_path='')

# --- Debug Configuration ---
DEBUG_API = True # Set to True to enable debug prints for api_server.py

def print_api_debug(message):
    if DEBUG_API:
        print(f"[API_DEBUG] {datetime.datetime.now().isoformat()}: {message}", file=sys.stderr)

# --- Configuration ---
API_AUTH_TOKEN = os.environ.get('API_AUTH_TOKEN')
FETCH_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'fetch_tradier_data.py')

# Twilio Configuration





# --- Helper for running subprocess commands (for data fetching and user management) ---
def run_db_script(command, *args):
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
        try:
            # Attempt to parse error output if it's JSON
            error_details = json.loads(e.stdout.strip() or e.stderr.strip())
            return error_details, e.returncode if e.returncode != 0 else 500
        except json.JSONDecodeError:
            return {"error": error_message}, 500
    except json.JSONDecodeError as e:
        error_message = f"Failed to decode JSON from script output for command {command}. Raw output: {result.stdout}. Error: {e}"
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
def serve_menu():
    print_api_debug("Received request for /")
    return send_from_directory('.', 'menu.html')
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

    result, status_code = run_db_script('query', *args)
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
    result, status_code = run_db_script('list-targets', *args)
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
        
        result, status_code = run_db_script('add-target', symbol, target_type)
        print_api_debug(f"Response from add-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code

    elif request.method == 'DELETE':
        data = request.get_json()
        symbol = data.get('symbol')
        print_api_debug(f"Received DELETE request for /api/target with symbol={symbol}")

        if not symbol:
            print_api_debug("Missing symbol in DELETE request.")
            return jsonify({"error": "Missing 'symbol' in request body."}), 400
        
        result, status_code = run_db_script('remove-target', symbol)
        print_api_debug(f"Response from remove-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code

@app.route('/api/target/<symbol>/<action>', methods=['POST'])
@token_required
def toggle_target_status_endpoint(symbol, action):
    print_api_debug(f"Received POST request for /api/target/{symbol}/{action}")
    if action == 'activate':
        result, status_code = run_db_script('activate-target', symbol)
        print_api_debug(f"Response from activate-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code
    elif action == 'deactivate':
        result, status_code = run_db_script('deactivate-target', symbol)
        print_api_debug(f"Response from deactivate-target: Status={status_code}, Result={result}")
        return jsonify(result), status_code
    else:
        print_api_debug(f"Invalid action: {action}")
        return jsonify({"error": "Invalid action. Must be 'activate' or 'deactivate'."}), 400


@app.route('/api/init-db', methods=['POST'])
@token_required
def init_db_endpoint():
    print_api_debug("Received request for /api/init-db")
    result, status_code = run_db_script('init-db')
    print_api_debug(f"Response from /api/init-db: Status={status_code}, Result={result}")
    return jsonify(result), status_code

if __name__ == '__main__':
    if not API_AUTH_TOKEN:
        print_api_debug("ERROR: API_AUTH_TOKEN environment variable not set.")
        print("ERROR: API_AUTH_TOKEN environment variable not set. Please set it before running the API server.")
        sys.exit(1)


    print_api_debug("Starting Flask app with Gunicorn (HTTPS)...")
    # Use the virtual environment's python for gunicorn
    gunicorn_cmd = ["/home/ubuntu/.openclaw/workspace/venv/bin/gunicorn", 
                    "--certfile", "cert.pem", 
                    "--keyfile", "key.pem", 
                    "-b", "0.0.0.0:8000", 
                    "api_server:app"]
    subprocess.run(gunicorn_cmd)

# --- New User Authentication Endpoints ---

@app.route('/api/register', methods=['POST'])
def register_user():
    print_api_debug("Received request for /api/register")
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    phone_number = data.get('phone_number')
    email = data.get('email')

    if not username or not password or not phone_number:
        return jsonify({"error": "Missing username, password, or phone number."}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    result, status_code = run_db_script('add-user', username, hashed_password, phone_number, email or "")
    
    print_api_debug(f"Response from add-user: Status={status_code}, Result={result}")
    return jsonify(result), status_code

@app.route('/api/login', methods=['POST'])
def login_user():
    print_api_debug("Received request for /api/login")
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Missing username or password."}), 400

    user_result, status_code = run_db_script('find-user', username)
    if status_code != 200 or 'error' in user_result:
        return jsonify({"error": "Invalid credentials."}), 401
    
    user_data = user_result # user_result is already the dict

    if not user_data or not bcrypt.checkpw(password.encode('utf-8'), user_data['password_hash'].encode('utf-8')):
        print_api_debug(f"Login failed for user: {username}")
        return jsonify({"error": "Invalid credentials."}), 401

    # Check for TOTP secret first
    if user_data.get('totp_secret'):
        print_api_debug(f"User {username} has TOTP enabled. Prompting for TOTP code.")
        return jsonify({"message": "TOTP enabled. Please provide TOTP code.", "username": username, "two_factor_method": "totp"}), 202

    else:
        print_api_debug(f"User {username} does not have TOTP enabled. Redirecting to enable TOTP.")
        return jsonify({"message": "TOTP not enabled. Please enable TOTP first.", "username": username, "two_factor_method": "none"}), 403








# --- New TOTP 2FA Endpoints ---

@app.route('/api/enable-totp', methods=['POST'])
def enable_totp():
    print_api_debug("Received request for /api/enable-totp")
    data = request.get_json()
    username = data.get('username')

    if not username:
        return jsonify({"error": "Username is required."}), 400

    user_result, status_code = run_db_script('find-user', username)
    if status_code != 200 or 'error' in user_result:
        return jsonify({"error": "User not found."}), 404
    
    user_data = user_result

    # Generate a new TOTP secret
    totp_secret = pyotp.random_base32()

    # Update user's TOTP secret in the database
    update_success = run_db_script('update-user-totp-secret', username, totp_secret)
    if not update_success:
        print_api_debug(f"Failed to update TOTP secret for user {username}")
        return jsonify({"error": "Failed to save TOTP secret."}), 500

    # Generate provisioning URI for QR code
    # The issuer_name is typically your application name
    provisioning_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
        name=user_data['email'] or user_data['username'], 
        issuer_name="TradierMarketDataApp"
    )

    print_api_debug(f"TOTP secret generated and saved for {username}. Provisioning URI: {provisioning_uri}")
    return jsonify({"message": "TOTP secret generated.", "secret": totp_secret, "provisioning_uri": provisioning_uri}), 200

@app.route('/api/verify-totp-setup', methods=['POST'])
def verify_totp_setup():
    print_api_debug("Received request for /api/verify-totp-setup")
    data = request.get_json()
    username = data.get('username')
    totp_code = data.get('code')

    if not username or not totp_code:
        return jsonify({"error": "Username and TOTP code are required."}), 400

    user_result, status_code = run_db_script('find-user', username)
    if status_code != 200 or 'error' in user_result:
        return jsonify({"error": "User not found."}), 404
    
    user_data = user_result

    if not user_data.get('totp_secret'):
        return jsonify({"error": "TOTP is not enabled for this user."}), 400

    totp = pyotp.TOTP(user_data['totp_secret'])
    if totp.verify(totp_code):
        print_api_debug(f"User {username} successfully verified TOTP setup.")
        return jsonify({"message": "TOTP setup verified successfully."}), 200
    else:
        print_api_debug(f"User {username} failed TOTP setup verification.")
        return jsonify({"error": "Invalid TOTP code."}), 401

@app.route('/api/totp-verify', methods=['POST'])
def totp_login_verify():
    print_api_debug("Received request for /api/totp-verify")
    data = request.get_json()
    username = data.get('username')
    totp_code = data.get('code')

    if not username or not totp_code:
        return jsonify({"error": "Username and TOTP code are required."}), 400

    user_result, status_code = run_db_script('find-user', username)
    if status_code != 200 or 'error' in user_result:
        return jsonify({"error": "User not found."}), 404
    
    user_data = user_result

    if not user_data.get('totp_secret'):
        return jsonify({"error": "TOTP is not enabled for this user."}), 400
    
    totp = pyotp.TOTP(user_data['totp_secret'])
    if totp.verify(totp_code):
        print_api_debug(f"User {username} successfully verified TOTP during login.")
        # Here, you would issue a JWT or set a session
        return jsonify({"message": "TOTP verified successfully. User logged in (session/JWT placeholder).", "username": username}), 200
    else:
        print_api_debug(f"User {username} failed TOTP verification during login.")
        return jsonify({"error": "Invalid TOTP code."}), 401
