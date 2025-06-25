import csv
import json
import os
import time
from datetime import datetime, timedelta, UTC
from pathlib import Path

import requests

CPS_SIMULATOR_BASE_URL = "http://localhost:7420/api"
CPS_SIMULATOR_START_URL = f"{CPS_SIMULATOR_BASE_URL}/start-simulation"


def get_end_simulation_url(request_id):
    return f"{CPS_SIMULATOR_BASE_URL}/end-simulation/{request_id}"


CPS_BASE_URL = "http://localhost:3333/api/v1"
CPS_START_URL = f"{CPS_BASE_URL}/regulation/start-test"


def get_regulation_report_url(regulation_id):
    return f"{CPS_BASE_URL}/regulation/{regulation_id}/report"


BASE_FOLDER = f"{Path(__file__).parent}/test_cases/"
CSV_OUT_FOLDER = f"{Path(__file__).parent}/csv/"
REQUEST_FOLDERS = ["no_pid"]
WAIT_AFTER_SIM = 2  # seconds
WAIT_AFTER_REQUEST = 5  # seconds


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def start_simulation(payload):
    response = requests.post(CPS_SIMULATOR_START_URL, json=payload)
    try:
        print("Response body:", response.text)  # or response.json() if JSON
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        print("Error status:", response.status_code)
        print("Response body:", response.text)  # or response.json() if JSON

    return response.json()


def start_request(payload):
    response = requests.post(CPS_START_URL, json=payload)
    try:
        print("Response body:", response.text)  # or response.json() if JSON
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        print("Error status:", response.status_code)
        print("Response body:", response.text)  # or response.json() if JSON
    return response.json()


def fetch_report(regulation_id):
    response = requests.get(get_regulation_report_url(regulation_id))
    try:
        print("Response body:", response.text)  # or response.json() if JSON
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        print("Error status:", response.status_code)
        print("Response body:", response.text)  # or response.json() if JSON

    return response.json()


def run_simulation(folder):
    print(f"\n=== Running simulation test from folder: {folder} ===")
    folder_path = f"{BASE_FOLDER}/{folder}"
    timing_data = load_json(f"{folder_path}/timing.json")

    padding = timing_data["simulator_start_end_delay_padding_seconds"]
    test_length = timing_data["test_length_seconds"]
    v = datetime.now(UTC)

    req_data = load_json(f"{folder_path}/test_request.json")
    req_data["power_reduction_request"]["starts_at_time"] = str(v)
    req_data["power_reduction_request"]["ends_at_time"] = str(
        v + timedelta(seconds=test_length)
    )
    print(json.dumps(req_data, indent=2))

    print("\n=== Starting Charge Point Selector Request ===")
    req_result = start_request(req_data)
    regulation_request_id = req_result.get("regulation_request_id")

    if not regulation_request_id:
        raise ValueError("No request_id returned from request start.")
    print(f"\n=== Waiting {padding}s for simulator to startup ===")
    time.sleep(padding)

    sim_data = load_json(f"{folder_path}/simulation_request.json")
    sim_data["start_at"] = str(v)
    sim_data["end_at"] = (
        v + timedelta(seconds=(test_length * 10) + padding)
    ).isoformat()

    print("\n=== Starting simulation ===")
    sim_result = start_simulation(sim_data)
    simulation_request_id = sim_result.get("request_id")
    if not simulation_request_id:
        raise ValueError("No simulation_request_id returned from simulation start.")

    print(f"\n=== Waiting {test_length}s for test to finish ===")
    time.sleep(test_length)

    print(f"\n=== Fetching report for {regulation_request_id} ===")
    regulation_report = fetch_report(regulation_request_id)

    return regulation_report


for request_folder in REQUEST_FOLDERS:
    this_report = run_simulation(request_folder)
    # request_folder = no_pid

    now = f"{datetime.today().strftime('%Y-%m-%d_%H-%M-%S')}"

    # Only create folders if fetching report succeeds
    file_path = f"{CSV_OUT_FOLDER}{request_folder}/"
    os.makedirs(file_path, exist_ok=True)
    with open(
        f"{file_path}{datetime.today().strftime('%Y-%m-%d_%H-%M-%S')}.csv", "w"
    ) as f:
        # Step 3: Extract windows
        windows = this_report["report"]["windows"]
        writer = csv.DictWriter(
            f, fieldnames=["timestamp", "total_reduction", "total_error"]
        )
        writer.writeheader()
        writer.writerows(windows)
