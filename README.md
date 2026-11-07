# SolvFix MVP web app (Bots 1-4) — local only, not deployed

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
Real platform connections (Google Business Profile / Facebook APIs) for automatic fixes and review import, password reset, email verification, CSRF protection, billing, and deployment.

## Files
audit.py (Bot 1), bots.py (Bots 2-4 + LLM hook), db.py (SQLite), app.py (Flask routes), templates/ (base, landing, brand, auth, form, report, dashboard, fix, reviews, social), test_app.py, test_audit.py (live network), sample_report.html (output from the test run).
