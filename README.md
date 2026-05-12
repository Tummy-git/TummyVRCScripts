
# Tummy Funny VRCScripts
## What is this
This is a small script that I made to make it easier to go through community labs quicker. I hate to look through the menu and try to remember where I am.
It's not beautiful. But it works pretty well. I also added an option to make it easier to regenerate impostors on your avatar. I thought that was pretty neat.
## Usage
You need at least Python 3.9 or something. Haven't checked properly. But everything that is pretty new should work.
Download the project. And run `run.bat` or `run,sh`. This will set up a virtual environment and install the packages needed in there.
You will be prompted to login. and if you want to save your credentials.
>If you store your credentials. They will be stored in a file on your disk. Just make sure no one gets that file. It will list where it is located.
If you  do some tweaks, you can skip the first options menu by calling `--run module_name`. Which makes it handy to run on a server. Only really usable by the ICAL export right now. But it allows you to hook it up in cron like this. `0 3 * * * /usr/bin/python3 /path/to/your/script/folder/main.py --run export_calendar >> /path/to/your/script/folder/cron.log 2>&1` If you want later you can just export the ical on a web server so your google calendar or wahtever can subscribe to it. 

### Impostor Regenerator
This will remove and request generation of new impostors for your avatars.
If you press enter while blank. It will just compare the impostor versions on your avatars. If there is a mismatch it regenerates everything that doesn't have the highest version number.

If you know what the latest impostor version is, you can just type it in, like `1.4.7`

### ICAL export
This creates an ical file of all the upcoming events you've followed.

### Worldhopper
Load worlds from IDs file? (y/n):
If you enter y, you will load the worlds in worlds_ids.txt. It's just one world id per line. Nothing else.

Enter offset (0-999):
How many worlds in do you want to start? Skip the first 10 by typing 10.

Load old worlds (Ascending)? (y/n):
This is just a silly where it loads the oldest worlds it can find. Skips some in the beginning due to older unsupported unity versions.

Then you have some options. 
goto#?, empty to advance, or 'update/clear/add/remove/fav':

 - If you just press enter on a blank prompt you advance to the next world.
 - If you write an number you jump to that position in the list
 - If you type `update` it adds all friends in the instance to the invite list.
 - If you type `clear` it wipes the list.
 - If you type `add` you can add a friend through UUID
 - If you type `remove` you can remove a single user.
 - If you type `fav` you will add the current world to favorites. If enabled in settings.

## settings.json.
|Setting |Value | Description |
|-----------|---------------------|----------------------------|
|"cookie_path"| "nope/cookie.json"|Where the cookie is stored
|"cred_path"| "nope/cred.json"|Where saved credentials is stored
|"cookie_lifetime_days"| 7|Cookie lifetime. Type `null` to make it endless.
|"co_explorers_path"| "worldhoppers.json"|Stores what friends gets invited
|"world_list_path"| "worlds_output.json"|The API response with worlds
|"manual_world_list"| "world_ids.txt"|Where you add a list manually
|"api_delay_seconds"| 30|Some time to led realtime servers cool off.
|"vrcx_db_path"| "~/AppData/Roaming/VRCX/VRCX.sqlite3"|Check VRCX settings below
|"currentworld"| ""|Current world.
|"instanceid"| "SpeedHopping"
|"allowvrcx"|false|Can the script interface with vrcx
|"vrcxfavgroup"| "Favorites"|Name of a local VRCX world favorite list.
|"calendar_json_path"| "calendars_output.json"|Output path for raw calendar file.
|"calendar_ical_path"| "calendars_output.ics"|Output path for the ical.


# VRCX
You can favorite the world you're currently in from the worldhopping script into a local favorite list. Not into the vrc ones.
I would not recommend it. It writes directly to the VRCX SQLite and doesn't update inside VRCX until you restart it. Or some other magic happens.
I personally think it's pretty neat, and I use it. But back up your database before testing and stuff. I don't want you to lose your VRCX data.

## VRCX settings.
This is where the VRCX SQLite database is located. It might differ. But this would give you some idea.

|OS         |Path                                             |
|-----------|-------------------------------------------------|
|Windows    |`~/AppData/Roaming/VRCX/VRCX.sqlite3`            |
|Linux      |`~/VRCX/VRCX.sqlite3`                            |
|macOS      |`~/Library/Application Support/VRCX/VRCX.sqlite3`|

## Last words
Remember. Only trust the code as much as you trust me. It's always good to double check code if you don't 100% trust the person that hands it out. And I take no responsibilities for any damages this could cause.
