We are creating an admin dashboard with multiple bots.  Each bot will have it's own widget/card on the index page and own detail page.   There will only be one bot/widget/card to start with but you will need to leave room for more.  That bot will scrape table data from these specific pages. 
    
https://syracuse.go2gov.net/faces/accounts?number=0562001300&src=SDG
https://syracuse.go2gov.net/faces/accounts?number=1626103200&src=SDG
https://syracuse.go2gov.net/faces/accounts?number=0716100700&src=SDG

Those pages have an odd behavior in that it 302 redirects to a page about the "number" value in the url params, but no longer shows the number value in the url, so we cannot get any link that goes directly to the table data we ultimately want to scrape.  You need to examine how it will be possible to reliably wait for the redirect to happen and finally see the table that needs to be copied in whatever tool we use for the data scraping.

From the scraped data we should save all table data to the database by property address (ie. 104 MOONEY AVE.) and be time stamped. 

The Admin Dashboard widget should only show the latest info from the database. 

There should be a button to refresh the data from all provided urls. This updates the database first, and then updates the info displayed in real time, and gives detailed information for debugging if the refresh fails for any reason.  Not retrieving structured table data is considered a failure. 

I want to send a text message - for free - to `NOTIFICATION_TEXT_PHONE` value from the env. 
---

## Execution Notes (2026-02-14)

- Implemented Agent Admin Dashboard v2 with no outbound email/text notification features.
- Added Docker-first backend/frontend/db stack with bind mounts and frontend exposed at `http://localhost:${DASHBOARD_PORT}`.
- Implemented fixed Syracuse URL scraping with redirect-aware waits, artifacts capture, and strict failure when structured tables are not extracted.
- Added persisted property snapshots by property address and timestamp (`tax_property_snapshots`) plus run diagnostics in `bot_runs`.
- Implemented required v2 API surface for bot list/detail, latest rows, property history, refresh runs, run details, and SSE events.
- Implemented index and detail dashboard views with real-time run event timeline and diagnostics.
- Added deterministic backend tests for smoke, runner success/failure commit behavior, and scraper helper extraction.
