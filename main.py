import subprocess
import csv
from datetime import datetime, timezone
from pytz import timezone as pytz_timezone
from io import StringIO
import requests
import json
import time
import os
import yaml

with open('secrets.yaml', 'r') as file:
    secrets = yaml.safe_load(file)

TOGGL_P_ID_MAP = secrets['TOGGL_P_ID_MAP']
TOGGL_KEY = secrets['TOGGL_KEY']
TOGGL_W_ID = secrets['TOGGL_W_ID']

def add_entry(project, description, start, duration):
    project_id = TOGGL_P_ID_MAP.get(project)
    headers = {
        'Content-Type': 'application/json',
    }
    auth = (TOGGL_KEY, 'api_token')
    url = f'https://api.track.toggl.com/api/v9/workspaces/{TOGGL_W_ID}/time_entries'
    data = {'description': description,
            'duration': duration,
            'start': start.isoformat()+'Z',
            'pid': project_id,
            'workspace_id': TOGGL_W_ID,
            'created_with': 'arbtt2toggl',
            'tags': ['arbtt2toggl'],
            }
    response = requests.post(url, headers=headers, auth=auth, data=json.dumps(data))
    if response.status_code != 200:
        raise Exception(f"Cannot create Toggl entry: {response.content}")
    return response.json()


def get_arbtt_data(last_run_date):
    # run the arbtt-stats command and get the output

    # sample_age is the duration of time since the last_run_date in the format hours:minutes
    now = datetime.now()
    duration = now - last_run_date
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    total_hours = hours + (duration.days * 24)
    sample_age = f"{total_hours:02}:{minutes:02}"

    result = subprocess.run(["arbtt-stats", "--intervals=project:", "--output-format=csv", f"--filter=$sampleage<={sample_age}"], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"arbtt-stats command failed: {result.stderr}")

    # parse the output as CSV
    reader = csv.reader(StringIO(result.stdout))
    data = []
    for row in reader:
        # skip empty lines and the first row (header)
        if not row or row[0] == "Tag":
            continue
        project_desc, start_time, end_time, duration = row
        tokens = project_desc.split("_")
        project = tokens[0]
        desc = " ".join(tokens[1:])
        # parse times
        start_time = datetime.strptime(start_time, "%m/%d/%y %H:%M:%S")
        la_timezone = pytz_timezone("America/Los_Angeles")
        start_time = start_time.astimezone(la_timezone).astimezone(timezone.utc).replace(tzinfo=None)
        duration_parts = duration.split(":")
        duration_seconds = int(duration_parts[0]) * 3600 + int(duration_parts[1]) * 60 + int(duration_parts[2])
        data.append({
            'project': project,
            'desc': desc,
            'start_time': start_time,
            'duration': duration_seconds,
        })

    return data

def add_all_entries(data):
    for entry in data:
        project = entry['project']
        desc = entry['desc']
        start = entry['start_time']
        duration = entry['duration']
        try:
            add_entry(project, desc, start, duration)
        except Exception as e:
            if '429' in str(e):
                print('Rate limit exceeded. Sleeping for 60 seconds.')
                time.sleep(60)
                add_entry(project, desc, start, duration)
            else:
                raise e
        # Sleep for a second to prevent hitting the rate limit
        time.sleep(0.1)


def save_last_run_date():
    # Get the current date and time
    now = datetime.now()

    # Format the date and time into a string
    date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Open the file in write mode
    with open(os.path.expanduser('~/.arbtt/last_run'), 'w') as file:
        # Write the date and time string to the file
        file.write(date_time_str)


def get_last_run_date():
    # Open the file in read mode
    with open(os.path.expanduser('~/.arbtt/last_run'), 'r') as file:
        # Read the date and time string from the file
        date_time_str = file.read().strip()

    # Convert the date and time string into a datetime object
    last_run_date = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")

    return last_run_date

if __name__ == "__main__":
    last_run_date = get_last_run_date()
    data = get_arbtt_data(last_run_date)
    print(f"Adding {len(data)} entries to Toggl...")
    add_all_entries(data)
    save_last_run_date()
    print("Done!")
