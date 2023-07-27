import subprocess
import csv
from datetime import datetime, timezone, timedelta
from pytz import timezone as pytz_timezone
from io import StringIO
import requests
import json
import time
import os
import yaml

try:
    with open('secrets.yaml', 'r') as file:
        secrets = yaml.safe_load(file)
except FileNotFoundError:
    print("Please create 'secrets.yaml' following the example in secrets_template.yaml.")
    exit(1)

TOGGL_P_ID_MAP = secrets['TOGGL_P_ID_MAP']
TOGGL_KEY = secrets['TOGGL_KEY']
TOGGL_W_ID = secrets['TOGGL_W_ID']
ARBTT_TIMEZONE = secrets['ARBTT_TIMEZONE']

def add_entry(project, description, start, duration):
    '''Add a new entry to Toggl'''
    
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
    '''run the arbtt-stats command and get the output as list of dicts'''

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
        arbtt_timezone = pytz_timezone(ARBTT_TIMEZONE)
        start_time = start_time.astimezone(arbtt_timezone).astimezone(timezone.utc).replace(tzinfo=None)
        duration_parts = duration.split(":")
        duration_seconds = int(duration_parts[0]) * 3600 + int(duration_parts[1]) * 60 + int(duration_parts[2])
        data.append({
            'project': project,
            'desc': desc,
            'start_time': start_time,
            'duration': duration_seconds,
        })

    print(f"Got {len(data)} new entries from arbtt-stats.")

    return data


def merge_entries(data):
    '''Merge entries that are within a minute of each other and have the same project'''

    data.sort(key=lambda x: x['start_time'])
    merged_data = []
    for entry in data:
        if not merged_data:
            merged_data.append(entry)
        else:
            last_entry = merged_data[-1]
            if last_entry['project'] == entry['project'] and last_entry['start_time'] + timedelta(seconds=last_entry['duration'] + 60) >= entry['start_time']:
                last_entry['duration'] += entry['duration']
                if entry['desc'] not in last_entry['desc']:
                    last_entry['desc'] += f", {entry['desc']}"
            else:
                merged_data.append(entry)

    print(f"Merged {len(data) - len(merged_data)} entries.")

    return merged_data


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
    '''Save the current date and time to a file to exclude entries already added to toggl'''
    now = datetime.now()
    date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.expanduser('~/.arbtt/last_run'), 'w') as file:
        file.write(date_time_str)


def get_last_run_date():
    '''Get the date and time of the last run from a file'''
    try:
        with open(os.path.expanduser('~/.arbtt/last_run'), 'r') as file:
            date_time_str = file.read().strip()
        last_run_date = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
    except FileNotFoundError:
        # If the file does not exist, return the Unix epoch start
        last_run_date = datetime(1970, 1, 1, 0, 0, 0)
    return last_run_date


if __name__ == "__main__":
    last_run_date = get_last_run_date()
    data = get_arbtt_data(last_run_date)
    data = merge_entries(data)
    print(f"Adding {len(data)} entries to Toggl...")
    add_all_entries(data)
    save_last_run_date()
    print("Done!")
