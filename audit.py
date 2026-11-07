"""SolvFix Bot 1 (Audit) - MVP. Checks only sources usable without scraping site pages:
OpenStreetMap Nominatim (free, 1 req/s policy), web-search snippets (ddgs), and optional
Google Places / Yelp Fusion when API keys are set in env."""
import os, re, time, difflib, requests, threading
UA = {"User-Agent": "SolvFix-MVP/0.1 (local prototype)"}

# site-search directories: we only read the search engine's result title/snippet, never the site itself
SEARCH_SITES = [("Yelp", "yelp.com"), ("Facebook", "facebook.com"), ("Instagram", "instagram.com"),
    ("LinkedIn", "linkedin.com"), ("Yellow Pages", "yellowpages.com"), ("BBB", "bbb.org"),
    ("Nextdoor", "nextdoor.com"), ("Foursquare", "foursquare.com"), ("MapQuest", "mapquest.com"),
    ("Manta", "manta.com"), ("Tripadvisor", "tripadvisor.com"), ("Angi", "angi.com")]

def digits(s): return re.sub(r"\D", "", s or "")[-10:]
def norm(s): return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()

def score(biz, name=None, addr=None, phone=None, text=None):
    """Return (pct, details, missing). If text given (snippet), check presence inside text."""
    det, missing, pts = {}, [], 0
    if text is not None:
        t = text.lower(); td = re.sub(r"\D", "", text)
        n = difflib.SequenceMatcher(None, biz["name"].lower(), (name or "").lower()).ratio()
        n = max(n, 1.0 if biz["name"].lower() in t else 0)
        p = bool(digits(biz["phone"])) and digits(biz["phone"]) in td
        street = norm(biz["address"])[:2]
        a = 1.0 if street and all(w in t.split() or w in norm(t) for w in street) else 0.0
    else:
        n = difflib.SequenceMatcher(None, biz["name"].lower(), (name or "").lower()).ratio()
        p = bool(phone) and digits(phone) == digits(biz["phone"])
        bt, at = set(norm(biz["address"])), set(norm(addr))
        a = len(bt & at) / max(len(bt), 1) if addr else 0.0
    det["name"] = round(n * 100); det["address"] = round(a * 100); det["phone"] = 100 if p else 0
    if text is None:
        if not addr: missing.append("address")
        if not phone: missing.append("phone")
    pct = round(0.4 * det["name"] + 0.35 * det["address"] + 0.25 * det["phone"])
    return pct, det, missing

# Concurrent comparisons share Nominatim's one-request-per-second limit.
_osm_lock = threading.Lock()
_osm_last_request = 0.0

def _osm_get(params):
    global _osm_last_request
    with _osm_lock:
        delay = 1.05 - (time.monotonic() - _osm_last_request)
        if delay > 0: time.sleep(delay)
        _osm_last_request = time.monotonic()
        return requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=5, params=params)

def osm(biz):
    q = f'{biz["name"]}, {biz["address"]}'
    try:
        r = _osm_get({"q": q, "format": "jsonv2", "extratags": 1, "addressdetails": 1, "limit": 3})
        res = r.json()
        if not res:  # fallback: name only near city
            time.sleep(1)
            r = _osm_get({"q": biz["name"], "format": "jsonv2", "extratags": 1, "limit": 3})
            res = r.json()
    except Exception as e:
        return dict(source="OpenStreetMap", status="Error", note=str(e))
    best = None
    for x in res:
        nm = x.get("name") or x.get("display_name", "").split(",")[0]
        ph = (x.get("extratags") or {}).get("phone") or (x.get("extratags") or {}).get("contact:phone")
        pct, det, miss = score(biz, nm, x.get("display_name"), ph)
        if not best or pct > best["score"]:
            ex = x.get("extratags") or {}
            for k in ("website", "opening_hours"):
                if not ex.get(k) and not ex.get("contact:" + k): miss.append(k)
            best = dict(source="OpenStreetMap", status="Listed", url=f'https://www.openstreetmap.org/{x["osm_type"]}/{x["osm_id"]}',
                        found_name=nm, found_address=x.get("display_name"), found_phone=ph, score=pct, details=det, missing=miss)
    if not best or best["details"]["name"] < 60:
        return dict(source="OpenStreetMap", status="Not listed")
    return best

def web_search(biz):
    out = []
    try:
        from ddgs import DDGS
        d = DDGS(timeout=4)
        deadline = time.monotonic() + 12
    except Exception as e:
        return [dict(source=s, status="Error", note=str(e)) for s, _ in SEARCH_SITES]
    for label, dom in SEARCH_SITES:
        if time.monotonic() >= deadline:
            out.append(dict(source=label, status="Skipped", note="Search time budget reached; retry later."))
            continue
        try:
            hits = d.text(f'"{biz["name"]}" {biz["city"]} site:{dom}', max_results=3) or []
        except Exception as e:
            st = "Not listed" if "No results" in str(e) else "Error"
            out.append(dict(source=label, status=st, note=str(e)[:80])); continue
        best = None
        for h in hits:
            if dom not in h.get("href", ""): continue
            txt = f'{h.get("title","")} {h.get("body","")}'
            pct, det, _ = score(biz, h.get("title", ""), text=txt)
            if det["name"] >= 60 and (not best or pct > best["score"]):
                best = dict(source=label, status="Listed (search result)", url=h["href"], found_name=(h.get("title") or "")[:90],
                            score=pct, details=det, missing=[], note="Snippet-only score: 0% address/phone means not visible in the search snippet, not necessarily wrong. Verify on the listing.")
        out.append(best or dict(source=label, status="Not listed", note="No matching search result"))
        time.sleep(0.7)
    return out

def google_places(biz):
    key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not key: return dict(source="Google Business Profile", status="Skipped", note="Set GOOGLE_PLACES_API_KEY")
    r = requests.post("https://places.googleapis.com/v1/places:searchText", timeout=15,
        headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.regularOpeningHours,places.googleMapsUri,places.rating,places.userRatingCount"},
        json={"textQuery": f'{biz["name"]} {biz["address"]}'}).json()
    p = (r.get("places") or [None])[0]
    if not p: return dict(source="Google Business Profile", status="Not listed")
    nm = p["displayName"]["text"]; pct, det, miss = score(biz, nm, p.get("formattedAddress"), p.get("nationalPhoneNumber"))
    if not p.get("websiteUri"): miss.append("website")
    if not p.get("regularOpeningHours"): miss.append("hours")
    return dict(source="Google Business Profile", status="Listed", url=p.get("googleMapsUri"), found_name=nm,
        found_address=p.get("formattedAddress"), found_phone=p.get("nationalPhoneNumber"), score=pct, details=det, missing=miss,
        note=f'Rating {p.get("rating")} ({p.get("userRatingCount")} reviews)')

def yelp(biz):
    key = os.getenv("YELP_API_KEY")
    if not key: return dict(source="Yelp (Fusion API)", status="Skipped", note="Set YELP_API_KEY")
    r = requests.get("https://api.yelp.com/v3/businesses/search", headers={"Authorization": f"Bearer {key}"},
        params={"term": biz["name"], "location": biz["address"], "limit": 3}, timeout=15).json()
    best = None
    for b in r.get("businesses", []):
        addr = " ".join(b.get("location", {}).get("display_address", []))
        pct, det, miss = score(biz, b["name"], addr, b.get("phone"))
        if not best or pct > best["score"]:
            best = dict(source="Yelp (Fusion API)", status="Listed", url=b.get("url"), found_name=b["name"], found_address=addr,
                        found_phone=b.get("display_phone"), score=pct, details=det, missing=miss)
    return best if best and best["details"]["name"] >= 60 else dict(source="Yelp (Fusion API)", status="Not listed")

def run_audit(biz, use_search=True):
    biz["city"] = biz.get("city") or (biz["address"].split(",")[-2].strip() if biz["address"].count(",") >= 2 else "")
    results = []
    for label, check in (("Google Business Profile", google_places), ("Yelp (Fusion API)", yelp), ("OpenStreetMap", osm)):
        try: results.append(check(biz))
        except Exception:
            results.append(dict(source=label, status="Error", note="Provider unavailable; retry later."))
    if use_search: results += web_search(biz)
    scored = [r for r in results if "score" in r]
    checked = [r for r in results if r["status"] not in ("Skipped", "Error")]
    overall = round(sum(r["score"] for r in scored) / len(checked)) if checked else 0
    return dict(business=biz, results=results, overall=overall, listed=len(scored), checked=len(checked))
