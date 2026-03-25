import os
import json
import re
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def mock_cicd_pipeline(*args, **kwargs):
    """
    Simulates a GET deployments API.
    Returns: JSON-like dictionary
    """
    deploy_file = os.path.join(DATA_DIR, "deployments.json")
    if os.path.exists(deploy_file):
        with open(deploy_file, "r") as f:
            return json.load(f)
    return {"events": []}

def mock_metrics(*args, **kwargs):
    """
    Returns system metrics as a JSON-like Python dictionary.
    """
    metrics_file = os.path.join(DATA_DIR, "metrics.json")
    if os.path.exists(metrics_file):
        with open(metrics_file, "r") as f:
            return json.load(f)
    return {"metrics": []}

def mock_get_logs(*args, **kwargs) -> List[Dict[str, Any]]:
    """
    Reads a log file and converts each log line into structured JSON.
    """
    file_path = os.path.join(DATA_DIR, "checkout-system.log")
    parsed_logs = []

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                log_entry = {}
                parts = re.findall(r'(\w+)=(".*?"|\S+)', line)

                for key, value in parts:
                    value = value.strip('"')
                    if value.isdigit():
                        value = int(value)
                    elif value.replace('.', '', 1).isdigit():
                        value = float(value)
                    log_entry[key] = value

                parsed_logs.append(log_entry)

    return parsed_logs