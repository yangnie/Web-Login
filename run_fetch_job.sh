#!/bin/bash

# Navigate to the OpenClaw-codes directory
cd /home/ubuntu/.openclaw/workspace/OpenClaw-codes

# Source the Python virtual environment
source ../venv/bin/activate

# Export TRADIER_API_KEY - IMPORTANT: REPLACE WITH YOUR ACTUAL KEY
export TRADIER_API_KEY="YOUR_ACTUAL_TRADIER_API_KEY_HERE"

# Run the fetch_tradier_data.py script to fetch data for active targets
python3 fetch_tradier_data.py fetch

# Deactivate the virtual environment (optional, good practice)
deactivate
