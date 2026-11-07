"""SolvFix Bots 2-4 (v1). Template-based, work with no API key. Optional LLM via env:
SOLVFIX_LLM_API_KEY (+ SOLVFIX_LLM_URL, default OpenAI chat completions; SOLVFIX_LLM_MODEL, default gpt-4o-mini).
Nothing here ever posts or publishes anything; all output is drafts."""
import os, csv, io, json, calendar, datetime, random, requests

def llm(prompt, max_tokens=1500):
    """Return LLM text or None if no key / any error (callers fall back to templates)."""
    key = os.environ.get("SOLVFIX_LLM_API_KEY")
    if not key: return None
    try:
        r = requests.post(os.environ.get("SOLVFIX_LLM_URL", "https://api.openai.com/v1/chat/completions"), timeout=60,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": os.environ.get("SOLVFIX_LLM_MODEL", "gpt-4o-mini"), "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]})
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None

# ---------------- Bot 4: Social ----------------
PILLARS = ["Behind the scenes", "Tip / how-to", "Product or service spotlight", "Community & local", "Customer appreciation",
           "FAQ", "Offer / call to action", "Team & story"]
TEMPLATES = {
 "Behind the scenes": ["Ever wondered what a day at {name} looks like? Here's a peek behind the scenes. {cta}",
                       "Before we open in {city}, this is how the {btype} work gets done. {cta}"],
 "Tip / how-to": ["Quick tip from {name}: one small thing that makes a big difference when choosing a {btype}. What's your question? Ask below.",
                  "{city} folks: here's our #1 tip from years in the {btype} business. Save this post for later."],
 "Product or service spotlight": ["Spotlight: one of our favorite things we do at {name}. Ask us about it next time you visit. {cta}",
                  "What makes our {btype} service different? We'll show you this week. {cta}"],
 "Community & local": ["Proud to be part of {city}. Which local spot should we give a shout-out to next?",
                       "Supporting {city} businesses is what we're about. Tag a local favorite below!"],
 "Customer appreciation": ["Thank you, {city}! Every visit to {name} means a lot to our small team.",
                           "To everyone who has trusted {name}: thank you. We read every review and it helps us improve."],
 "FAQ": ["FAQ: \"Do you offer [service]?\" Here's the answer from {name}. Got another question? Drop it in the comments.",
         "Our most-asked question this month at {name}, answered. {cta}"],
 "Offer / call to action": ["Planning ahead? {name} is ready to help. {cta}",
                            "Looking for a trusted {btype} in {city}? We'd love to meet you. {cta}"],
 "Team & story": ["Meet the people behind {name}. [Add a team member's name and fun fact.]",
                  "How {name} started: [add your story in 2-3 sentences]. Thanks for being part of it."],
}
TONES = {"friendly": ("😊", "Stop by or send us a message!"), "professional": ("", "Call or book online today."),
         "playful": ("🎉", "Come say hi, we don't bite!"), "warm": ("💛", "We'd love to see you soon.")}
TAGS = ["#{c}", "#Shop{c}", "#{b}", "#SmallBusiness", "#Local{b}", "#SupportLocal"]

def social_posts(name, btype, city, tone="friendly", month=None, seed=None):
    """Return (posts, source). 30 drafts, one per day starting on the 1st of `month` (YYYY-MM)."""
    month = month or datetime.date.today().strftime("%Y-%m")
    y, m = map(int, month.split("-")); ndays = calendar.monthrange(y, m)[1]
    days = [datetime.date(y, m, min(i + 1, ndays)) for i in range(30)]
    out = llm(f"Write exactly 30 short social media post drafts (one per line, no numbering, no fake statistics, no fake reviews, "
              f"no ranking promises) for {name}, a {btype} in {city}. Tone: {tone}. Rotate pillars: {', '.join(PILLARS)}. "
              f"Format each line as: PILLAR | POST TEXT | HASHTAGS")
    if out:
        lines = [l.split("|") for l in out.splitlines() if l.count("|") >= 2][:30]
        if len(lines) == 30:
            return [dict(day=str(d), pillar=a.strip(), text=b.strip(), hashtags=c.strip(), status="draft")
                    for d, (a, b, c, *_) in zip(days, lines)], "llm"
    rnd = random.Random(seed if seed is not None else f"{name}{month}")
    emoji, cta = TONES.get(tone, TONES["friendly"])
    c, b = "".join(w.capitalize() for w in city.split()), "".join(w.capitalize() for w in btype.split())
    posts = []
    for i, d in enumerate(days):
        p = PILLARS[i % len(PILLARS)]; t = TEMPLATES[p][(i // len(PILLARS)) % len(TEMPLATES[p])]
        text = t.format(name=name, btype=btype, city=city, cta=cta) + (f" {emoji}" if emoji else "")
        tags = " ".join(rnd.sample([x.format(c=c, b=b) for x in TAGS], 3))
        posts.append(dict(day=str(d), pillar=p, text=text, hashtags=tags, status="draft"))
    return posts, "template"

def to_csv(rows, fields):
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows); return s.getvalue()

# ---------------- Bot 3: Reviews ----------------
def parse_reviews(text=None, csv_text=None, platform="Manual"):
    """Parse owner-supplied reviews. CSV columns (any case): platform, author, rating, text/review.
    Plain text: one review per block separated by blank lines; optional first line 'Author - 4' or '4/5'."""
    out = []
    if csv_text:
        for r in csv.DictReader(io.StringIO(csv_text)):
            r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            body = r.get("text") or r.get("review") or r.get("comment")
            if body: out.append(dict(platform=r.get("platform") or platform, author=r.get("author") or r.get("name") or "",
                                     rating=_rating(r.get("rating") or r.get("stars")), text=body))
    if text:
        for block in [b.strip() for b in text.replace("\r", "").split("\n\n") if b.strip()]:
            lines = block.split("\n"); author, rating = "", None
            if len(lines) > 1 and len(lines[0]) < 60:
                head = lines[0]; rating = _rating(head)
                author = head.split(" - ")[0].strip() if " - " in head else ("" if rating else head.strip())
                lines = lines[1:]
            out.append(dict(platform=platform, author=author, rating=rating, text=" ".join(lines).strip()))
    return out

def _rating(s):
    import re
    s = (s or "").strip()
    if re.fullmatch(r"[1-5](\.0)?", s): return int(s[0])
    m = re.search(r"([1-5])\s*(?:/\s*5|stars?|★)", s, re.I) or re.search(r"-\s*([1-5])\s*$", s)
    return int(m.group(1)) if m else None

def reply_draft(review, business):
    first = (review.get("author") or "").split(" ")[0] or "there"
    out = llm(f"Draft a short, honest, polite reply from the owner of {business} to this customer review. Don't offer refunds or "
              f"promises unless the owner adds them. Don't invent facts. Review ({review.get('rating') or '?'} stars): {review['text']}", 300)
    if out: return out.strip()
    r = review.get("rating")
    if r and r >= 4: return f"Hi {first}, thank you so much for the kind words! We're glad you had a great experience at {business} and hope to see you again soon."
    if r and r <= 2: return (f"Hi {first}, thank you for telling us about this, and we're sorry it fell short. We'd like to make it right. "
                             f"Please contact us directly so we can learn more. — The {business} team")
    return f"Hi {first}, thanks for taking the time to share your feedback. We're always working to improve at {business}, and we appreciate you."

# ---------------- Bot 2: Fix ----------------
CLAIM = {
 "Google Places (API)": "https://business.google.com/", "Google": "https://business.google.com/",
 "Yelp": "https://biz.yelp.com/", "Yelp (Fusion API)": "https://biz.yelp.com/",
 "OpenStreetMap": "https://www.openstreetmap.org/edit", "Facebook": "https://www.facebook.com/pages/create",
 "Instagram": "https://business.instagram.com/", "LinkedIn": "https://www.linkedin.com/company/setup/new/",
 "Yellow Pages": "https://adsolutions.yp.com/free-listing", "BBB": "https://www.bbb.org/get-listed",
 "Nextdoor": "https://business.nextdoor.com/", "Foursquare": "https://foursquare.com/add-place",
 "MapQuest": "https://www.mapquest.com/", "Manta": "https://www.manta.com/claim",
 "Tripadvisor": "https://www.tripadvisor.com/Owners", "Angi": "https://www.angi.com/pro/",
 "Apple Maps": "https://businessconnect.apple.com/", "Bing Places": "https://www.bingplaces.com/",
}
ALWAYS = ["Apple Maps", "Bing Places"]  # major sources the audit can't check yet

def fix_checklist(results, biz):
    items = []
    for r in results:
        site, url = r["source"], CLAIM.get(r["source"], "")
        if r["status"] == "Not listed":
            items.append(dict(site=site, issue="Not listed", claim_url=url,
                steps=f"Create or claim a listing on {site}. Use exactly: {biz['name']} | {biz['address']} | {biz['phone']}. Verify ownership (often by phone, postcard, or email)."))
        elif r.get("details"):
            bad = [k for k, v in r["details"].items() if v < 90]
            miss = r.get("missing") or []
            if bad or miss:
                issue = "; ".join(([f"{k} mismatch ({r['details'][k]}%)" for k in bad]) + ([f"missing {m}" for m in miss]))
                items.append(dict(site=site, issue=issue, claim_url=url,
                    steps=f"Log in or claim the listing on {site}{' ('+r['url']+')' if r.get('url') else ''}. Update to: {biz['name']} | {biz['address']} | {biz['phone']}"
                          + (f". Add: {', '.join(miss)}." if miss else ".") + " Snippet-based scores can be wrong: check the live page first."))
    for s in ALWAYS:
        items.append(dict(site=s, issue="Not checked by audit yet", claim_url=CLAIM[s], steps=f"Search for your business on {s} and claim or create it with the exact same NAP."))
    return items
