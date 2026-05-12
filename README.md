Yo.
I made this with at least python 3.9. Have that installed.

Make sure you keep settings.json and cookie.json private. Like please do.

run the run.bat/run.sh to run it.

To make a list of worlds you want to go through. edit world_ids.txt and just add one world id per line.

wrld_4d71aea2-ba58-473e-b291-e8cfbcf8f096
wrld_896ec7da-0a9c-422a-a86d-5829aecb596f
wrld_153c2727-0a21-4ce5-96ce-bddec4ce3e03
wrld_b963eef3-55ef-4f43-b152-7f169b410fed
wrld_8316f834-752b-4b9b-b1f3-fb70077d00a3

worldhoppers.txt is where you want other people that should be invited. One user ID per line. This can be changed without restarting the script.

If you run this on linux and want to be able to add favorites to the vrcx database. You have to change the vrcx_db_path in the settings.json. 
These should be the default paths for the SQLite database. Remember to back up your database before testing.
Windows	~/AppData/Roaming/VRCX/VRCX.sqlite3
Linux	~/VRCX/VRCX.sqlite3
macOS	~/Library/Application Support/VRCX/VRCX.sqlite3

And as always. Only trust the code as much as you trust me :)