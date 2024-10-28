# prairietest-log-parser
Log parser for PT using Selenium for web scraping
- Needs a CWL username and password
- Runs Chrome and simulates inputs for username and password
- Requires Duo 2FA but retains Chrome profile after this so future logins will not ask for 2FA
- Navigates to PT logs and scrapes the added dates based on "add session" tags
