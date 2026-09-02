import os
import json
import datetime
from icalendar import Calendar, Event

import vrchatapi
from vrchatapi.api.calendar_api import CalendarApi
from vrchatapi.api.groups_api import GroupsApi
from groups_manager import load_groups, save_groups
from rich.console import Console

# force_terminal=False ensures that when run via cron, Rich strips color codes to keep logs clean
console = Console(force_terminal=False)

def clean_for_json(obj):
    if hasattr(obj, "to_dict"): return clean_for_json(obj.to_dict())
    elif isinstance(obj, dict): return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (datetime.datetime, datetime.date)): return obj.isoformat()
    return obj

def json_to_ical(events_data):
    cal = Calendar()
    cal.add('prodid', '-//VRChat API//WorldHoppingTool//EN')
    cal.add('version', '2.0')
    cal.add('method', 'PUBLISH')

    if isinstance(events_data, dict):
        found_list = False
        for key in events_data:
            if isinstance(events_data[key], list):
                events_data = events_data[key]
                found_list = True
                break
        if not found_list:
            console.print("[red]Error: Could not find a list of events.[/red]")
            return None

    for event_data in events_data:
        if not isinstance(event_data, dict): continue
        event = Event()
        title = event_data.get('title', 'No Title')
        event.add('summary', title)
        event.add('description', event_data.get('description', ''))
        if event_data.get('id'): event.add('uid', event_data.get('id'))

        start_str = event_data.get('starts_at')
        end_str = event_data.get('ends_at')
        if start_str: event.add('dtstart', datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')))
        if end_str: event.add('dtend', datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00')))

        event.add('dtstamp', datetime.datetime.now(datetime.timezone.utc))

        if event_data.get('owner_id') and event_data.get('id'):
            event.add('location', f"https://vrchat.com/home/group/{event_data['owner_id']}/calendar/{event_data['id']}")
        if event_data.get('deleted_at') is not None:
            event.add('status', 'CANCELLED')
            event.add('summary', f"CANCELLED: {title}")
        cal.add_component(event)

    return cal.to_ical()

def extract_events_from_response(response):
    if isinstance(response, list): return response
    elif isinstance(response, dict):
        if 'results' in response and isinstance(response['results'], list): return response['results']
        for key in response:
            if isinstance(response[key], list): return response[key]
    return []

def filter_upcoming_events(events, days_ahead=None):
    if days_ahead is None or days_ahead <= 0: return events
    cutoff = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days_ahead)
    filtered = []
    for event in events:
        if isinstance(event, dict) and event.get('starts_at'):
            try:
                if datetime.datetime.fromisoformat(event['starts_at'].replace('Z', '+00:00')) <= cutoff:
                    filtered.append(event)
            except ValueError:
                filtered.append(event)
        else:
            filtered.append(event)
    return filtered

def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    calendar_json_output_path = os.path.join(script_dir, settingsdata['files'].get('calendar_json_path', 'calendars_output.json'))
    ical_file_output_path = os.path.join(script_dir, settingsdata['files'].get('calendar_ical_path', 'calendars_output.ics'))
    days_ahead = settingsdata.get('calendar_days_ahead', None)

    console.print("\n[bold]--- iCal Export ---[/bold]")
    if days_ahead and days_ahead > 0:
        console.print(f"Limiting calendar to events in the next {days_ahead} days.")

    try:
        calendar_api = CalendarApi(api_client)
        all_events = []

        console.print("  - Fetching followed calendar events...")
        all_events.extend(extract_events_from_response(clean_for_json(calendar_api.get_followed_calendar_events())))

        groups_file_path = os.path.join(script_dir, settingsdata['files'].get('groups_path', 'groups.json'))
        groups = load_groups(groups_file_path)

        if groups:
            groups_api = GroupsApi(api_client)
            for g in groups:
                group_id = g.get('id')
                if not group_id: continue

                if not g.get('name'):
                    try:
                        info = groups_api.get_group(group_id)
                        name = getattr(info, 'name', None) or (info.get('name') if isinstance(info, dict) else None)
                        if name:
                            g['name'] = name
                            save_groups(groups_file_path, groups)
                    except Exception as e:
                        console.print(f"  [yellow]- Warning: Could not fetch group metadata for {group_id}: {e}[/yellow]")

                try:
                    console.print(f"  - Fetching events for group: {group_id} ({g.get('name')})")
                    all_events.extend(extract_events_from_response(clean_for_json(calendar_api.get_group_calendar_events(group_id))))
                except Exception as e:
                    console.print(f"  [yellow]- Warning: Failed to fetch events for group {group_id}: {e}[/yellow]")
        else:
            console.print("  - No followed groups configured.")

        if days_ahead and days_ahead > 0:
            all_events = filter_upcoming_events(all_events, days_ahead)

        with open(calendar_json_output_path, "w", encoding="utf-8") as f:
            json.dump(all_events, f, indent=2, ensure_ascii=False)

        console.print("Converting to iCalendar format...")
        ical_output = json_to_ical(all_events)

        if ical_output:
            with open(ical_file_output_path, "wb") as f:
                f.write(ical_output)
            console.print(f"[green][+] Success! iCalendar file written to: {ical_file_output_path}[/green]")
        else:
            console.print("[red][-] Failed to generate iCal data.[/red]")

    except Exception as e:
        console.print(f"[red]Error fetching calendar data: {e}[/red]")