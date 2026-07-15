import os
import json
import datetime
from icalendar import Calendar, Event

import vrchatapi
from vrchatapi.api.calendar_api import CalendarApi
from vrchatapi.api.groups_api import GroupsApi

from groups_manager import load_groups, save_groups

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


def extract_events_from_response(response):
    """Extract event list from API response, handling wrapper objects."""
    if isinstance(response, list):
        return response
    elif isinstance(response, dict):
        # Check if this is a paginated response with 'results' key
        if 'results' in response and isinstance(response['results'], list):
            return response['results']
        # Otherwise try to find any list in the dict
        for key in response:
            if isinstance(response[key], list):
                return response[key]
    return []


def filter_upcoming_events(events, days_ahead=None):
    """Filter events to only include those within the next N days."""
    if days_ahead is None or days_ahead <= 0:
        return events

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now + datetime.timedelta(days=days_ahead)

    filtered = []
    for event in events:
        if isinstance(event, dict):
            start_str = event.get('starts_at')
            if start_str:
                try:
                    # Parse the start time
                    if start_str.endswith('Z'):
                        start_str = start_str.replace('Z', '+00:00')
                    start_time = datetime.datetime.fromisoformat(start_str)

                    # Include event if it starts before the cutoff
                    if start_time <= cutoff:
                        filtered.append(event)
                except ValueError:
                    # If we can't parse the date, include it to be safe
                    filtered.append(event)
            else:
                # If no start time, include it
                filtered.append(event)
        else:
            filtered.append(event)

    return filtered


def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    calendar_json_output_path = os.path.join(script_dir, settingsdata['files'].get('calendar_json_path', 'calendars_output.json'))
    ical_file_output_path = os.path.join(script_dir, settingsdata['files'].get('calendar_ical_path', 'calendars_output.ics'))

    # Get the days_ahead setting (default: no limit)
    days_ahead = settingsdata.get('calendar_days_ahead', None)
    if days_ahead is not None and days_ahead > 0:
        print(f"Limiting calendar to events in the next {days_ahead} days.")

    print("\n--- iCal Export ---")
    print("Fetching calendar events...")

    try:
        calendar_api = CalendarApi(api_client)
        all_events = []

        # Fetch followed calendar events
        print("  - Fetching followed calendar events...")
        upcoming_events = calendar_api.get_followed_calendar_events()
        cleaned_events = clean_for_json(upcoming_events)

        # Extract events from response wrapper
        events_list = extract_events_from_response(cleaned_events)
        all_events.extend(events_list)

        # Fetch group calendar events from groups.json
        groups_file_path = os.path.join(script_dir, settingsdata['files'].get('groups_path', 'groups.json'))
        groups = load_groups(groups_file_path)
        if groups:
            groups_api = GroupsApi(api_client)
            for g in groups:
                group_id = g.get('id')
                if not group_id:
                    continue

                # Fill missing group name if possible
                if not g.get('name'):
                    try:
                        info = groups_api.get_group(group_id)
                        name = getattr(info, 'name', None) or (info.get('name') if isinstance(info, dict) else None)
                        if name:
                            g['name'] = name
                            print(f"  - Filled name for group {group_id}: {name}")
                            save_groups(groups_file_path, groups)
                    except Exception as e:
                        print(f"  - Warning: Could not fetch group metadata for {group_id}: {e}")

                try:
                    print(f"  - Fetching events for group: {group_id} ({g.get('name')})")
                    group_events = calendar_api.get_group_calendar_events(group_id)
                    cleaned_group_events = clean_for_json(group_events)

                    # Extract events from response wrapper
                    group_events_list = extract_events_from_response(cleaned_group_events)
                    all_events.extend(group_events_list)
                except Exception as e:
                    print(f"  - Warning: Failed to fetch events for group {group_id}: {e}")
        else:
            print("  - No followed groups configured.")

        # Filter to upcoming events if setting is enabled
        if days_ahead and days_ahead > 0:
            initial_count = len(all_events)
            all_events = filter_upcoming_events(all_events, days_ahead)
            filtered_count = len(all_events)
            print(f"Filtered {initial_count - filtered_count} past/old events.")

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