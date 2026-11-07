"""Offline tests: audit network calls are mocked. Run: .venv/bin/python -m pytest -q test_app.py"""
import os, tempfile, io, json
os.environ["SOLVFIX_DB"] = tempfile.mktemp(suffix=".db"); os.environ.pop("SOLVFIX_LLM_API_KEY", None)
import app as appmod, bots
FAKE = dict(business={}, overall=40, listed=2, checked=3, results=[
  dict(source="OpenStreetMap", status="Listed", url="https://osm.org/x", found_name="Joe's", score=70, details=dict(name=100, address=50, phone=0), missing=["website"]),
  dict(source="Yelp", status="Not listed"),
  dict(source="Facebook", status="Listed", score=100, details=dict(name=100, address=100, phone=100), missing=[])])
appmod.run_audit = lambda biz, use_search=True: {**FAKE, "business": biz}
c = appmod.app.test_client()

def signup(email="a@b.com"):
    return c.post("/signup", data=dict(email=email, password="password123"), follow_redirects=True)

def test_public_pages():
    for p in ["/", "/brand", "/audit", "/login", "/signup"]: assert c.get(p).status_code == 200, p
    assert c.get("/dashboard").status_code == 302

def test_auth_hashing_and_login():
    assert b"Your dashboard" in signup("h@x.com").data
    with appmod.app.app_context():
        u = appmod.db.q("SELECT pw_hash FROM users WHERE email='h@x.com'", one=True)
        assert u["pw_hash"] != "password123" and u["pw_hash"].startswith(("scrypt:", "pbkdf2:"))
    c.get("/logout")
    assert b"Wrong email" in c.post("/login", data=dict(email="h@x.com", password="nope12345")).data
    assert c.post("/login", data=dict(email="h@x.com", password="password123")).status_code == 302

def test_audit_saved_fix_and_history():
    signup("d@x.com")
    r = c.post("/audit", data=dict(name="Joe's Pizza", address="1 Main St, San Francisco, CA", phone="4155551212"))
    assert r.status_code == 200 and b"fix checklist" in r.data
    d = c.get("/dashboard"); assert b"Joe&#39;s Pizza" in d.data and b"40%" in d.data
    f = c.get("/audits/1/fix"); assert f.status_code == 200 and b"Not listed" in f.data and b"biz.yelp.com" in f.data
    assert b"phone mismatch" in f.data and b"missing website" in f.data and b"Facebook" not in f.data.split(b"<main")[1]
    c.post("/audits/1/fix", data=dict(item=1, done=1)); assert b"1 of" in c.get("/audits/1/fix").data
    assert c.get("/audits/1").status_code == 200

def test_other_user_cannot_see_audit():
    c.get("/logout"); signup("other@x.com"); assert c.get("/audits/1").status_code == 404

def test_social_30_drafts_and_csv():
    posts, src = bots.social_posts("Joe's", "pizzeria", "San Francisco", "playful", "2026-02")
    assert len(posts) == 30 and src == "template" and len({p["pillar"] for p in posts}) == len(bots.PILLARS)
    assert all(p["status"] == "draft" for p in posts)
    r = c.post("/social", data=dict(name="Joe's", btype="pizzeria", city="San Francisco", tone="friendly", month="2026-11"), follow_redirects=True)
    assert r.status_code == 200 and r.data.count(b"pill dr") == 30
    csv = c.get("/social/1.csv"); assert csv.mimetype == "text/csv" and len(csv.data.decode().strip().splitlines()) == 31

def test_reviews_inbox():
    txt = "Maria G - 5\nBest pizza in town!\n\nTom - 1/5\nCold and late."
    c.post("/reviews", data=dict(action="import", platform="Google", text=txt))
    c.post("/reviews", data={"action": "import", "csv": (io.BytesIO(b"platform,author,rating,text\nYelp,Ann,4,Nice staff\n"), "r.csv")}, content_type="multipart/form-data")
    page = c.get("/reviews").data; assert b"Best pizza" in page and b"Nice staff" in page and b"Cold and late" in page
    c.post("/reviews", data=dict(action="draft_all", business="Joe's"))
    page = c.get("/reviews").data.decode(); assert "thank you so much" in page and "sorry it fell short" in page
    c.post("/reviews", data=dict(action="approve", id=1, reply="Thanks Maria!")); assert "approved" in c.get("/reviews").data.decode()
    assert c.get("/reviews.csv").data.count(b"\n") == 4

def test_parse_reviews_ratings():
    r = bots.parse_reviews(text="Sam - 4\nGood.\n\nJust a review with no header")
    assert r[0]["author"] == "Sam" and r[0]["rating"] == 4 and r[1]["rating"] is None
