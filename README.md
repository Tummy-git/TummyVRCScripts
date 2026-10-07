# Tummy Funny VRCScripts
## What is this
This is a small script that I made to make it easier to go through community labs quicker. I hate to look through the menu and try to remember where I am.
It's not beautiful. But it works pretty well. I also added an option to make it easier to regenerate impostors on your avatar. I thought that was pretty neat.

## Language & Technologies
- **Python** - Core scripting language (3.10+)
- **Shell/Batch** - Launch scripts for cross-platform support

## Usage
You need Python 3.10 or newer.
Download the project. And run `run.bat` (Windows) or `run.sh` (Linux/Mac). This will set up a virtual environment and install the packages from `requirements.txt` in there.
You will be prompted to login. and if you want to save your credentials.
>If you store your credentials. They will be stored in `nope/cred.json` (see `cred_path` in settings.json). They are only base64 encoded, not encrypted. So make sure no one gets that file.

### Command Line Arguments

You can skip the main menu by calling `--run module_name`. Which makes it handy to run on a server.
This needs a saved login (cookie or credentials) since there is no one around to type in a 2FA code.

```bash
python main.py --run export_calendar
python main.py --run world_visit_tracker
python main.py --run world_hopper
python main.py --run regenerate_impostors
python main.py --run groups_manager
```

`run.bat` and `run.sh` pass arguments along too, so `run.bat --run export_calendar` works as well.
Currently, the automated run is most useful with the ICAL export and the world visit tracker.

### Main Menu
Once authenticated, you'll see the main menu:

- `[0]` - VRChat World Hopper
- `[1]` - Impostor Regenerator
- `[2]` - Export Followed Events to iCal
- `[3]` - Manage Followed Groups
- `[4]` - World Visit Tracker
- `[l]` - Logout (clears all stored credentials and cookies)
- `[q]` - Quit the script

### Impostor Regenerator

This will remove and request generation of new impostors for your avatars.

**Input Options:**
- **Leave blank** - The script will compare impostor versions on all your avatars and regenerate everything that doesn't have the highest version number.
- **Enter a version number** - If you know the latest impostor version (e.g., `1.4.7`), you can type it in. The script will regenerate all avatars with an older version.

You get a table of what will be regenerated and have to confirm with `y` before anything is sent.

**Note:** VRChat limits impostor regenerations to 50 per day.

### ICAL export
This creates an ical file of the events you've followed and the events from the groups in your followed groups list (see Manage Followed Groups). Useful for importing into calendar applications. You can limit how far ahead the export goes with the `calendar_days_ahead` setting in settings.json.

### Manage Followed Groups
Keeps the list of groups the ICAL export fetches events from. It is stored in `groups.json`.
- `l` - List the groups
- `a` - Add a group by its group ID (`grp_...`). The name is fetched automatically
- `r` - Remove a group by its number in the list
- `f` - Fetch names for groups that don't have one yet
- `q` - Back to the main menu

### World Visit Tracker
Logs the visit count of the world in `visitors_world_id` to `world_visits.log`, one line per run (`YYYY-MM-DD HH:MM:SS visits`). Meant to be run on a schedule with `--run world_visit_tracker`.

### Worldhopper

#### Initial Setup

If you quit in the middle of a session, you get asked if you want to continue where you left off.
Otherwise you pick which worlds to go through:

```
Select a queue to load (1-5):
```
- **1** - File: the worlds in `world_ids.txt` (one world ID per line). IDs that can't be loaded are skipped and listed
- **2** - Community Labs (Newest)
- **3** - Public (Recently Published)
- **4** - Public (Hot / Popular)
- **5** - Public (Random / Shuffle)

```
Enter offset (0-999):
```
For the API queues. How many worlds in do you want to start? Skip the first 10 by typing `10`.

#### Navigation Commands

Once you're in the jumping loop, here are all the commands. The most common ones are also listed at the bottom of the screen.

**Basic Navigation:**
- `[empty]` - Advance to the next world in the list. If the last jump failed, it retries that world
- `[number]` - Jump to that position in the list
- `quit` - Exit the hopper. The session is saved so you can continue later

There is a cooldown between jumps (`api_delay_seconds`). A countdown is shown while it waits.

**Instance Type:**
- `type` - Open a menu to change instance type
- `type friends` - Set to Friends only
- `type friends+` or `type hidden` - Set to Friends+ (Hidden)
- `type invite` or `type invite+` or `type private` - Set to Invite Only (Private)
- `type public` - Set to Public instance

**Mode:**
- `mode` - Open a menu to change action mode
- `mode invite` - Send API invites to yourself and co-explorers
- `mode launch` - Open VRChat client directly via URI
- `mode both` - Launch client AND invite co-explorers

**Co-Explorers Management:**
- `update` - Replace the co-explorers list with everyone in your current instance
- `add` - Manually add a friend by their User ID (format: `usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- `remove` - Remove a user from your co-explorers list
- `clear` - Clear your entire co-explorers list

**Favorites:**
- `fav` - Add the current world you're in to VRCX favorites (requires VRCX integration enabled)

**Help:**
- `help` - Show all available commands

## settings.json
`settings.json` is not tracked by git. On first run it is created from `settings.example.json`, so edit your local `settings.json` freely.

|Setting |Default | Description |
|-----------|---------------------|----------------------------|
|"cookie_path"| "nope/cookie.json"|Where the authentication cookie is stored
|"cred_path"| "nope/cred.json"|Where saved credentials are stored
|"cookie_lifetime_days"| 7|Cookie lifetime in days. Type `null` to make it endless.
|"co_explorers_path"| "worldhoppers.json"|File that stores which friends get invited in worldhopper
|"world_list_path"| "worlds_output.json"|The API response with worlds
|"manual_world_list"| "world_ids.txt"|File path where you add a list of world IDs manually
|"api_delay_seconds"| 20|Delay between jumps (some time to let realtime servers cool off)
|"vrcx_db_path"| "~/AppData/Roaming/VRCX/VRCX.sqlite3"|Path to VRCX SQLite database
|"calendar_json_path"| "calendars_output.json"|Output path for raw calendar JSON file
|"calendar_ical_path"| "calendars_output.ics"|Output path for the iCal file
|"groups_path"| "groups.json"|Where the followed groups list is stored (optional, inside "files")
|"visitors_log_path"| "world_visits.log"|Where the world visit tracker writes its log
|"currentworld"| ""|Stores your current world index when worldhopping. Managed by the script
|"instanceid"| "SpeedHopping"|What the instance ID will be named (requires VRC+)
|"allowvrcx"|false|Whether the script can interface with VRCX
|"vrcxfavgroup"| "Favorites"|Name of the local VRCX world favorite list to use
|"calendar_days_ahead"| 30|Limit calendar export to only events within the next N days. Set to `null` or `0` to show all events
|"visitors_world_id"| ""|World ID (`wrld_...`) the world visit tracker logs visits for

All file paths are relative to the script folder, so it doesn't matter where you run it from.

# VRCX Integration
You can favorite the world you're currently in from the worldhopping script into a local VRCX favorite list. 

**Warning:** This is experimental. It writes directly to the VRCX SQLite database and doesn't update inside VRCX until you restart it or some other magic happens. I personally think it's pretty neat though.

## VRCX Database Location
This is where the VRCX SQLite database is located. It might differ slightly, but this should give you an idea:

|OS         |Path                                             |
|-----------|-------------------------------------------------|
|Windows    |`~/AppData/Roaming/VRCX/VRCX.sqlite3`            |
|Linux      |`~/VRCX/VRCX.sqlite3`                            |
|macOS      |`~/Library/Application Support/VRCX/VRCX.sqlite3`|

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Last words
Remember. Only trust the code as much as you trust me. It's always good to double check code if you don't 100% trust the person that hands it out. And I take no responsibilities for any damages the script might cause.