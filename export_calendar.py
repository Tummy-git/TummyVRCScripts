import os
import json
import datetime
from icalendar import Calendar, Event

import vrchatapi
from vrchatapi.api.calendar_api import CalendarApi

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
    print("Fetching followed calendar events...")

    try:
        calendar_api = CalendarApi(api_client)
        upcoming_events = calendar_api.get_followed_calendar_events()

        # Clean the data to be JSON-friendly
        cleaned_events = clean_for_json(upcoming_events)

        # Save the raw JSON backup just like the old script did
        with open(calendar_json_output_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_events, f, indent=2, ensure_ascii=False)
        print(f"Saved raw event JSON to: {calendar_json_output_path}")

        # Convert straight from memory without doing a redundant read from disk
        print("Converting to iCalendar format...")
        ical_output = json_to_ical(cleaned_events)

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