# Tummy Funny VRCScripts
## What is this
This is a small script that I made to make it easier to go through community labs quicker. I hate to look through the menu and try to remember where I am.
It's not beautiful. But it works pretty well. I also added an option to make it easier to regenerate impostors on your avatar. I thought that was pretty neat.

## Language & Technologies
- **Python** - Core scripting language (3.9+)
- **Shell/Batch** - Launch scripts for cross-platform support

## Usage
You need at least Python 3.9 or something. Haven't checked properly. But everything that is pretty new should work.
Download the project. And run `run.bat` (Windows) or `run.sh` (Linux/Mac). This will set up a virtual environment and install the packages needed in there.
You will be prompted to login. and if you want to save your credentials.
>If you store your credentials. They will be stored in a file on your disk. Just make sure no one gets that file. It will list where it is located.

### Command Line Arguments

If you do some tweaks, you can skip the first options menu by calling `--run module_name`. Which makes it handy to run on a server. 

```bash
python main.py --run export_calendar
python main.py --run world_hopper
python main.py --run regenerate_impostors
```

Currently, the automated run is most useful with the ICAL export.

### Main Menu
Once authenticated, you'll see the main menu:

- `[0]` - VRChat World Hopper
- `[1]` - Impostor Regenerator
- `[2]` - Export Followed Events to iCal
- `[l]` - Logout (clears all stored credentials and cookies)
- `[q]` - Quit the script

### Impostor Regenerator

This will remove and request generation of new impostors for your avatars.

**Input Options:**
- **Leave blank** - The script will compare impostor versions on all your avatars and regenerate everything that doesn't have the highest version number.
- **Enter a version number** - If you know the latest impostor version (e.g., `1.4.7`), you can type it in. The script will regenerate all avatars with an older version.

**Note:** VRChat limits impostor regenerations to 50 per day.

### ICAL export
This creates an ical file of all the upcoming events you've followed and from groups you follow. Useful for importing into calendar applications. You can limit the exported events to only show upcoming events within a certain timeframe using the `calendar_days_ahead` setting in settings.json.

### Worldhopper

#### Initial Setup

```
Load worlds from IDs file? (y/n):
```
- **y** - Load worlds from `world_ids.txt` (one world ID per line)
- **n** - Use API search to fetch worlds

```
Enter offset (0-999):
```
How many worlds in do you want to start? Skip the first 10 by typing `10`.

```
Load old worlds (Ascending)? (y/n):
```
- **y** - Load oldest worlds (skips some in the beginning due to older unsupported unity versions)
- **n** - Load newest community lab worlds

#### Navigation Commands

Once you're in the jumping loop, here are all the commands:

**Basic Navigation:**
- `[empty]` - Advance to the next world in the list
- `[number]` - Jump to that position in the list

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
- `update` - Add all friends from your current instance to the co-explorers list
- `add` - Manually add a friend by their User ID (format: `usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- `remove` - Remove a user from your co-explorers list
- `clear` - Clear your entire co-explorers list

**Favorites:**
- `fav` - Add the current world you're in to VRCX favorites (requires VRCX integration enabled)

**Help:**
- `help` - Display all available commands

## settings.json
|Setting |Value | Description |
|-----------|---------------------|----------------------------|
|"cookie_path"| "nope/cookie.json"|Where the authentication cookie is stored
|"cred_path"| "nope/cred.json"|Where saved credentials are stored
|"cookie_lifetime_days"| 7|Cookie lifetime in days. Type `null` to make it endless.
|"co_explorers_path"| "worldhoppers.json"|File that stores which friends get invited in worldhopper
|"world_list_path"| "worlds_output.json"|The API response with worlds
|"manual_world_list"| "world_ids.txt"|File path where you add a list of world IDs manually
|"api_delay_seconds"| 30|Delay between API requests (some time to let realtime servers cool off)
|"vrcx_db_path"| "~/AppData/Roaming/VRCX/VRCX.sqlite3"|Path to VRCX SQLite database
|"currentworld"| ""|Stores your current world index when worldhopping
|"instanceid"| "SpeedHopping"|What the instance ID will be named (requires VRC+)
|"allowvrcx"|false|Whether the script can interface with VRCX
|"vrcxfavgroup"| "Favorites"|Name of the local VRCX world favorite list to use
|"calendar_json_path"| "calendars_output.json"|Output path for raw calendar JSON file
|"calendar_ical_path"| "calendars_output.ics"|Output path for the iCal file
|"followed_groups"| []|List of VRChat group IDs to fetch calendar events from
|"calendar_days_ahead"| 30|Limit calendar export to only events within the next N days. Set to `null` or `0` to show all events

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