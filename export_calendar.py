import os
import json
import datetime
from icalendar import Calendar, Event

import vrchatapi
from vrchatapi.api.calendar_api import CalendarApi
from vrchatapi.api.groups_api import GroupsApi

def clean_for_json(obj):
    """Recursively convert model objects to JSON-serializable structures."""
    if hasattr(obj, "to_dict"):
        return clean_for_json(obj.to_dict())
    elif isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    else:
        return obj

def json_to_ical(events_data):
    # Initialize the calendar with required properties
    cal = Calendar()
    cal.add('prodid', '-//VRChat API//WorldHoppingTool//EN')
    cal.add('version', '2.0')
    cal.add('method', 'PUBLISH') # Helps email clients/calendars treat this as a standalone calendar

    # 1. Handle case where input is a Dictionary (wrapper) instead of a List
    if isinstance(events_data, dict):
        found_list = False
        for key in events_data:
            if isinstance(events_data[key], list):
                events_data = events_data[key]
                found_list = True
                break

        if not found_list:
            print("Error: Input is a dictionary, but could not find a list of events inside it.")
            return None

    # 2. Iterate safely
    for event_data in events_data:
        if not isinstance(event_data, dict):
            continue

        event = Event()
        title = event_data.get('title', 'No Title')

        # Add properties using .add() method
        event.add('summary', title)
        event.add('description', event_data.get('description', ''))

        # Unique ID
        if event_data.get('id'):
            event.add('uid', event_data.get('id'))

        # Handle Timestamps
        start_str = event_data.get('starts_at')
        end_str = event_data.get('ends_at')

        if start_str:
            if start_str.endswith('Z'):
                start_str = start_str.replace('Z', '+00:00')
            event.add('dtstart', datetime.datetime.fromisoformat(start_str))

        if end_str:
            if end_str.endswith('Z'):
                end_str = end_str.replace('Z', '+00:00')
            event.add('dtend', datetime.datetime.fromisoformat(end_str))

        # Handle 'dtstamp' (Required by RFC 5545)
        now = datetime.datetime.now(datetime.timezone.utc)
        event.add('dtstamp', now)

        # Handle Location
        owner_id = event_data.get('owner_id')
        instance_id = event_data.get('id')
        if owner_id and instance_id:
            location_url = f"https://vrchat.com/home/group/{owner_id}/calendar/{instance_id}"
            event.add('location', location_url)

        # Handle Deleted/Cancelled status
        if event_data.get('deleted_at') is not None:
            event.add('status', 'CANCELLED')
            event.add('summary', f"CANCELLED: {title}")

        # Add the event component to the calendar
        cal.add_component(event)

    # Return bytes directly to preserve correct line endings (\r\n)
    return cal.to_ical()


def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    calendar_json_output_path = os.path.join(script_dir, settingsdata['files'].get('calendar_json_path', 'calendars_output.json'))
    ical_file_output_path = os.path.join(script_dir, settingsdata['files'].get('calendar_ical_path', 'calendars_output.ics'))

    print("\n--- iCal Export ---")
    print("Fetching calendar events...")

    try:
        calendar_api = CalendarApi(api_client)
        all_events = []

        # Fetch followed calendar events
        print("  - Fetching followed calendar events...")
        upcoming_events = calendar_api.get_followed_calendar_events()
        cleaned_events = clean_for_json(upcoming_events)

        if isinstance(cleaned_events, list):
            all_events.extend(cleaned_events)
        else:
            all_events.append(cleaned_events)

        # Fetch group calendar events
        followed_groups = settingsdata.get('followed_groups', [])
        if followed_groups:
            groups_api = GroupsApi(api_client)
            for group_id in followed_groups:
                try:
                    print(f"  - Fetching events for group: {group_id}")
                    group_events = calendar_api.get_group_calendar_events(group_id)
                    cleaned_group_events = clean_for_json(group_events)

                    if isinstance(cleaned_group_events, list):
                        all_events.extend(cleaned_group_events)
                    else:
                        all_events.append(cleaned_group_events)
                except Exception as e:
                    print(f"  - Warning: Failed to fetch events for group {group_id}: {e}")
        else:
            print("  - No followed groups configured.")

        # Save the raw JSON backup
        with open(calendar_json_output_path, "w", encoding="utf-8") as f:
            json.dump(all_events, f, indent=2, ensure_ascii=False)
        print(f"Saved raw event JSON to: {calendar_json_output_path}")

        # Convert straight from memory without doing a redundant read from disk
        print("Converting to iCalendar format...")
        ical_output = json_to_ical(all_events)

        if ical_output:
            # Use "wb" (write binary) to ensure CRLF line endings are preserved correctly on Windows
            with open(ical_file_output_path, "wb") as f:
                f.write(ical_output)
            print(f"[+] Success! iCalendar file written to: {ical_file_output_path}")
        else:
            print("[-] Failed to generate iCal data.")

    except vrchatapi.ApiException as e:
        print(f"Exception when fetching calendar data: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print("-------------------\n")