# SolvFix Solutions — local business visibility tools

## Run
    cd /workspace/solvfix/mvp
    python3 -m venv .venv && .venv/bin/pip install flask requests ddgs
    .venv/bin/python app.py        # open http://127.0.0.1:5000 (landing), /audit (free audit form), /brand (brand guide)
    .venv/bin/pip install pytest && .venv/bin/python -m pytest -q test_app.py   # offline app tests (audit mocked)
    .venv/bin/python test_audit.py # headless test -> sample_report.html (Tartine Bakery, SF)

## What works with no keys
- OpenStreetMap via Nominatim (free, max 1 request/sec, custom User-Agent required). Full NAP and missing-field check (website, hours).
- Web search (DuckDuckGo through the `ddgs` package) using `"Name" City site:domain` queries for 12 sites: Yelp, Facebook, Instagram, LinkedIn, Yellow Pages, BBB, Nextdoor, Foursquare, MapQuest, Manta, Tripadvisor, Angi. Only the search engine's title and snippet are read. The directory pages themselves are never fetched or scraped. Scores are therefore approximate: if an address or phone scores 0%, it may just be missing from the snippet. ddgs is an unofficial client, so for production use a paid search API such as Brave Search API (free tier) or Google Programmable Search JSON API.
- NAP score per listing: name 40% (fuzzy match), address 35% (token overlap), phone 25% (last 10 digits). The overall score is the average across the sources checked, with Not listed counting as 0.
- Missing sources show **Not listed**.

## Optional modules (env keys)
- `GOOGLE_PLACES_API_KEY`: Google Places API (New) Text Search, which returns NAP, website, hours, and rating. It needs a Google Cloud billing account. Monthly free usage is included.
- `YELP_API_KEY`: Yelp Fusion business search. Check Yelp's current plan and trial terms.

## Web app (v2)
Pages: `/` landing, `/brand`, `/signup`, `/login`, `/logout`, `/audit`, `/dashboard`, `/audits/<id>`, `/audits/<id>/fix`, `/reviews`, `/reviews.csv`, `/social`, `/social/<id>`, `/social/<id>.csv`.
- **Accounts**: email + password, hashed with Werkzeug (scrypt), SQLite file `solvfix.db` (`SOLVFIX_DB` to override). Set `SOLVFIX_SECRET` for stable sessions.
- **Dashboard**: every audit run while logged in is saved (name, address, phone, score, per-site results JSON) and listed with fix progress.
- **Bot 2 Fix v1**: checklist built from Not listed rows and rows with a name/address/phone match under 90% or missing fields, plus Apple Maps and Bing Places (not audited yet). Each item has the site's claim/edit link and a done toggle. The owner makes the changes; no site logins or APIs are used.
- **Bot 3 Reviews v1**: owner pastes reviews or uploads CSV (platform, author, rating, text) into one inbox. Reply drafts are template-based by rating (or LLM). Status draft/approved, copy button, CSV export. Never generates reviews, never posts replies.
- **Bot 4 Social**: 30 drafts per month across 8 rotating content pillars, 4 tones, hashtags. Copy per post, CSV download. Never posts.
- **Optional LLM**: set `SOLVFIX_LLM_API_KEY` (and optionally `SOLVFIX_LLM_URL`, any OpenAI-compatible chat-completions endpoint, and `SOLVFIX_LLM_MODEL`, default gpt-4o-mini). If unset or the call fails, templates are used.

## Not done yet
Real platform connections (Google Business Profile / Facebook APIs) for automatic fixes and review import, password reset, email verification, full-app CSRF protection (new service forms are protected), billing, and automated recurring work.

## Files
audit.py (Bot 1), bots.py (Bots 2-4 + LLM hook), db.py (SQLite), app.py (Flask routes), templates/ (base, landing, brand, auth, form, report, dashboard, fix, reviews, social), test_app.py, test_audit.py (live network), sample_report.html (output from the test run).


## Local-business growth services
- `/services`: tool directory and local citation guidance using the saved audit Fix Bot checklist.
- `/gbp` (GET/POST): personalized, prioritized Google Business Profile self-assessment; no live Google access.
- `/reviews/request` or `/request-reviews` (GET/POST): copy-ready SMS/email/in-person review requests; only real customers, no review gating or incentives. Optional owner-supplied HTTPS Google review link; no messages are sent and QR creation is explained, not outsourced.
- `/competitors` (GET/POST): two audits with optional directory search, score/coverage comparison, and potential gaps. Only explicitly Not listed sources count as gaps; unavailable sources do not. Runs are concurrent with a 20-second response deadline. Comparisons are not saved; run an individual audit while logged in to retain history.
- `/inquire` or `/contact` (GET/POST): validated contact and plan/service requests saved in the new `inquiries` SQLite table; `/inquire/thanks` confirms storage. No email is sent automatically.
- `/leads`: owner-only inquiries, newest first, with Pacific timestamps. Set `SOLVFIX_OWNER_EMAIL` to the owner's existing account email (case-insensitive). Unset means no access; guests redirect to login and non-owners receive 403. Protect and verify that owner account before enabling this view; the app does not yet verify signup emails.

Pricing: Free Audit $0; Starter $49/mo; Growth $99/mo; Done-for-you $199/mo + $299 setup. Paid CTAs preselect the requested plan on the inquiry form. Requests are not purchases; there is no Stripe checkout, billing, automatic subscription, or scheduled audit worker. Monthly audits / weekly re-check support and manual claims/fixes must be arranged and fulfilled by the team. No profitability, leads, or ranking guarantees.

Storage initializes additive tables automatically. **Production:** back up SQLite and use persistent storage (`SOLVFIX_DB` on an attached disk) before accepting real inquiries; Render's default filesystem is ephemeral. Keep `SOLVFIX_SECRET` stable. Never commit `.env`, database files, logs, `.venv`, or real/demo credentials.

Offline verification: `.venv/bin/python -m pytest -q test_app.py`. `test_audit.py` is an opt-in live-network smoke script; its main guard prevents network calls and generated report changes during pytest collection.
