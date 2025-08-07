/requirements.txt is for the Windows desktop client
/requirements_headless.txt is for the cross-platform headless Python client
/requirements_web.txt is for the web app
When adding a new package to a requirements*.txt file, first use pip to figure out the latest version, and try and use that.

Organize files in folders as much as possible. 
Avoid clutter in the root folder. 
Put documentation under /docs/.

Testing of the web app in development can happen through /web/start_dev.sh. The development server can be accessed through localhost:8080, not :5000.

After changes to a docker image, 'docker compose restart' will NOT create a new container if the image changed. You need to use 'docker compose up' instead.

If you can't find a file or folder, say an ls or cd command fails, use pwd to check which folder you're in right now, instead of assuming.
Try to keep track of which folder you're in so you don't keep adding a cd to a subfolder at the start of every subsequent command, only to have it fail.

Don't use inline scripts. The final document should not have inline `<script>` tags. Keep in mind: 'Refused to execute inline event handler because it violates the following Content Security Policy directive: "script-src 'self'". Either the 'unsafe-inline' keyword, a hash ('sha256-...'), or a nonce ('nonce-...') is required to enable inline execution. Note that hashes do not apply to event handlers, style attributes and javascript: navigations unless the 'unsafe-hashes' keyword is present.'

Changes to the database schema should be done through bash scripts through sudo, so that databases owned by limited user accounts can be force-updated.