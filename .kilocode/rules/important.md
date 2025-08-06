/requirements.txt is for the Windows desktop client
/requirements_headless.txt is for the cross-platform headless Python client
/requirements_web.txt is for the web app
When adding a new package to a requirements*.txt file, first use pip to figure out the latest version, and try and use that.

Organize files in folders as much as possible. 
Avoid clutter in the root folder. 
Put documentation under /docs/.

Testing of the web app in development can happen through /web/start_dev.sh.

After changes to a docker image, 'docker compose restart' will NOT create a new container if the image changed. You need to use 'docker compose up' instead.

If you can't find a file or folder, say an ls or cd command fails, use pwd to check which folder you're in right now, instead of assuming.
Try to keep track of which folder you're in so you don't keep adding a cd to a subfolder at the start of every subsequent command, only to have it fail.