## About

[arbtt](https://arbtt.nomeata.de/#what) is a desktop app that logs open and active windows on your computer to help you track where your time goes.

[Toggl](https://toggl.com/track/) is a nice web app for time tracking with a calendar view and generated reports.

**arbtt2toggl** is a python script that creates entries in Toggl by dumping logs from arbtt using the `arbtt-stats` cli tool.

## Setup
Create a secrets.yaml file with your Toggl API key and workspace ID (and optionally, Project IDs). Follow the example in secrets_template.yaml

Configure arbtt's `categorize.cfg` in a way that tags your entires `project:Name_Description`. Here's a sample from mine:
```
-- Primary apps with titles as descriptions
current window $program == ["chromium-browser","Navigator"] && current window $title =~ /^(.{0,25}).*/    ==> tag project:Web_$1,
current window $program == "slack"                          && current window $title =~ /^(.{0,25}).*/    ==> tag project:Communication_$1,
current window $program =~ /^code/                          && current window $title =~ /^(.{0,25}).*/    ==> tag project:Development_$1,

-- Catch all for other programs
tag project:Other_$current.program,
```
You can use a category other than `project` with a simple mod to main.py.

The project name, e.g. `Web` from my example above should correlate with a project in Toggl.

## Usage
Run the script with `python main.py`. It takes no arguments. Every time log since the last successful run is entered into Toggl.

Consider putting it on a cron.

## Notes
Hardcoding a workspace ID and project IDs is not user friendly, but it made the script a lot easier to bang out. You can find your API key at the bottom of your Toggl Profile Settings. Your workspace ID and project ID[s] can be found in the toggl url if you navigate to a project, e.g. `https://track.toggl.com/{your_workspace_id}/projects/{your_project_id}/team`

I believe the only user-specific bit I left in the script that you may need to change is the LA timezone.