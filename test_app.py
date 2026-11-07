"""Offline tests: audit network calls are mocked. Run: .venv/bin/python -m pytest -q test_app.py"""
import os, tempfile, io, json
import pytest
_test_db_dir = tempfile.TemporaryDirectory()
os.environ["SOLVFIX_DB"] = os.path.join(_test_db_dir.name, "tests.db"); os.environ.pop("SOLVFIX_LLM_API_KEY", None)
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


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLVFIX_DB", str(tmp_path / "app.db"))
    monkeypatch.delenv("SOLVFIX_OWNER_EMAIL", raising=False)
    return appmod.app.test_client()

def service_post(client, path, data):
    assert client.get(path).status_code == 200
    with client.session_transaction() as sess: token = sess["form_token"]
    return client.post(path, data={**data, "form_token": token})

def inquiry_data(**updates):
    return dict(name="Owner", email="owner@example.com", phone="", business="Main Street Salon", city="Oakland",
                plan="growth", message="Please help with our listings", **updates)

def test_growth_public_pages_and_pricing(client):
    for path in ("/", "/services", "/gbp", "/reviews/request", "/request-reviews", "/competitors", "/inquire", "/contact", "/inquire/thanks"):
        assert client.get(path).status_code == 200, path
    home = client.get("/").data
    for text in (b"$49", b"$99", b"$199", b"$299", b"Most popular", b"og:description", b"name=\"description\"", b"does not connect"):
        assert text in home
    assert b"Pricing will be confirmed" not in home
    for plan in ("starter", "growth", "done-for-you"):
        assert ("/inquire?plan=" + plan).encode() in home
    assert b'value="growth" selected' in client.get("/inquire?plan=growth").data

def test_inquiry_capture_validation_and_csrf(client):
    assert client.post("/inquire", data=inquiry_data()).status_code == 400
    bad = inquiry_data(); bad["email"] = "not-an-email"
    assert b"valid email" in service_post(client, "/inquire", bad).data
    bad["email"] = "valid@example.com"; bad["plan"] = "made-up"
    service_post(client, "/inquire", bad)
    with appmod.app.app_context(): assert appmod.db.q("SELECT COUNT(*) n FROM inquiries", one=True)["n"] == 0
    response = service_post(client, "/inquire", inquiry_data())
    assert response.status_code == 302 and response.location.endswith("/inquire/thanks")
    assert b"request is saved" in client.get(response.location).data
    with appmod.app.app_context():
        row = appmod.db.q("SELECT * FROM inquiries", one=True)
        assert row["business"] == "Main Street Salon" and row["plan"] == "growth" and row["user_id"] is None
    too_long = inquiry_data(); too_long["message"] = "x" * 4001
    assert b"shorten" in service_post(client, "/inquire", too_long).data

def test_leads_authorization_and_order(client, monkeypatch):
    service_post(client, "/inquire", inquiry_data())
    assert client.get("/leads").status_code == 302
    client.post("/signup", data=dict(email="owner@example.com", password="test-pass-123"))
    assert client.get("/leads").status_code == 403  # owner env unset
    monkeypatch.setenv("SOLVFIX_OWNER_EMAIL", "OWNER@EXAMPLE.COM")
    data = inquiry_data(); data["business"] = "Second business"; data["message"] = "<script>alert(1)</script>"
    service_post(client, "/contact", data)
    response = client.get("/leads")
    assert response.status_code == 200
    assert response.data.index(b"Second business") < response.data.index(b"Main Street Salon")
    assert b"&lt;script&gt;" in response.data and b"<script>alert" not in response.data
    assert b"Pacific Time" in response.data and b"/leads" in client.get("/dashboard").data
    client.get("/logout")
    client.post("/signup", data=dict(email="not-owner@example.com", password="test-pass-123"))
    assert client.get("/leads").status_code == 403
    # A stale/forged session email does not grant access: check the actual account.
    with client.session_transaction() as sess: sess["email"] = "owner@example.com"
    assert client.get("/leads").status_code == 403
    assert b'href="/leads"' not in client.get("/dashboard").data

def test_gbp_personalized_checklist(client):
    assert b"Enter your business" in service_post(client, "/gbp", dict(name="", city="")).data
    r = service_post(client, "/gbp", dict(name="Oak Salon", city="Oakland"))
    assert r.status_code == 200
    for text in (b"Oak Salon", b"Oakland", b"Categories", b"Hours", b"Photos", b"Products and services", b"Questions and answers", b"Posts", b"Review replies", b"Accurate name", b"done-for-you"):
        assert text in r.data, text

def test_review_request_kit_and_safe_link(client):
    link = "https://g.page/r/my-real-link/review"
    r = service_post(client, "/reviews/request", dict(name="Oak Salon", review_link=link))
    assert r.status_code == 200
    for text in (b"SMS", b"Email", b"In-person", link.encode(), b"Only ask real customers", b"not just from happy customers", b"QR code"):
        assert text in r.data
    r = service_post(client, "/request-reviews", dict(name="Oak Salon"))
    assert b"[paste your own Google review link here]" in r.data
    for bad in ("javascript:alert(1)", "https://evil.example/review", "https://google.com.evil.example/r", "https://[bad"):
        r = service_post(client, "/reviews/request", dict(name="Oak Salon", review_link=bad))
        assert r.status_code == 200 and b"No other links" in r.data
        assert b"Ready-to-copy SMS" not in r.data

def competitor_data():
    return dict(your_name="Yours", your_city="Oakland", their_name="Theirs", their_address="10 Main St", nosearch="1")

def test_competitor_gap_comparison(client, monkeypatch):
    calls = []
    def fake(biz, use_search=True):
        calls.append((biz, use_search))
        results = [dict(source="Yelp", status="Not listed" if biz["name"] == "Yours" else "Listed", score=90),
                   dict(source="Facebook", status="Error" if biz["name"] == "Yours" else "Listed", score=80)]
        return dict(business=biz, overall=20 if biz["name"] == "Yours" else 80, listed=0 if biz["name"] == "Yours" else 2,
                    checked=1 if biz["name"] == "Yours" else 2, results=results)
    monkeypatch.setattr(appmod, "run_audit", fake)
    r = service_post(client, "/competitors", competitor_data())
    assert r.status_code == 200 and b"20%" in r.data and b"80%" in r.data
    section = r.data.split(b"Potential directory gaps")[1]
    assert b"<li>Yelp</li>" in section and b"<li>Facebook</li>" not in section
    assert len(calls) == 2 and all(not search for _, search in calls)
    assert calls[0][0]["address"]  # city fallback
    data = competitor_data(); data.pop("nosearch")
    service_post(client, "/competitors", data)
    assert all(search for _, search in calls[-2:])

def test_competitor_invalid_timeout_and_failure(client, monkeypatch):
    assert b"Enter a name" in service_post(client, "/competitors", dict(your_name="Missing location")).data
    with monkeypatch.context() as patch:
        patch.setattr(appmod, "wait", lambda jobs, timeout: (set(), set(jobs)))
        assert b"timed out" in service_post(client, "/competitors", competitor_data()).data
    def broken(*args, **kwargs): raise RuntimeError("private provider details")
    monkeypatch.setattr(appmod, "run_audit", broken)
    r = service_post(client, "/competitors", competitor_data())
    assert b"provider is unavailable" in r.data and b"private provider details" not in r.data

def test_report_and_dashboard_upgrade_prompts(client):
    r = client.post("/audit", data=dict(name="Oak Salon", address="10 Main St", phone="1234567890"))
    assert b"Get this fixed for me" in r.data and b"guest report is not stored" in r.data
    assert b"plan=starter" in r.data and b"plan=growth" in r.data
    client.post("/signup", data=dict(email="tools@example.com", password="test-pass-123"))
    r = client.get("/dashboard")
    for path in (b"/gbp", b"/reviews/request", b"/competitors", b"Request a plan"):
        assert path in r.data


def test_audit_provider_failure_is_unavailable_not_missing(monkeypatch):
    import audit
    def broken(biz): raise RuntimeError("upstream unavailable")
    monkeypatch.setattr(audit, "google_places", broken)
    monkeypatch.setattr(audit, "yelp", lambda biz: dict(source="Yelp (Fusion API)", status="Skipped"))
    monkeypatch.setattr(audit, "osm", lambda biz: dict(source="OpenStreetMap", status="Not listed"))
    result = audit.run_audit(dict(name="Business", address="10 Main St", phone="", city="Oakland"), use_search=False)
    assert result["results"][0]["status"] == "Error"
    assert result["checked"] == 1 and result["overall"] == 0

def test_new_forms_reject_missing_csrf(client):
    for path in ("/gbp", "/reviews/request", "/competitors", "/contact"):
        assert client.post(path, data={}).status_code == 400

# Business Exposure Scan: the actual report is public before optional email capture.
def scan_context(client):
    import re, html
    response = client.post('/audit', data=dict(name='Current Salon', address='10 Main St', city='Oakland', phone='5105550100'))
    assert response.status_code == 200
    page = response.data.decode()
    with client.session_transaction() as sess: csrf = sess['form_token']
    context = html.unescape(re.search(r'name="report_context" value="([^"]+)"', page).group(1))
    return response, dict(form_token=csrf, report_context=context)


def test_scan_score_is_real_and_not_email_gated(client):
    response, _ = scan_context(client)
    assert b'40%' in response.data and b'Current Salon' in response.data
    assert b'Business Exposure Scan' in response.data
    assert response.data.index(b'40%') < response.data.index(b'Email me this report')
    assert b'72%' not in response.data and b'Example Bakery' not in response.data
    with appmod.app.app_context():
        assert appmod.db.q('SELECT COUNT(*) n FROM inquiries', one=True)['n'] == 0
        assert appmod.db.q('SELECT COUNT(*) n FROM audits', one=True)['n'] == 0


@pytest.mark.parametrize('csrf', ['', 'incorrect'])
def test_scan_capture_csrf_required(client, csrf):
    _, data = scan_context(client)
    data.update(email='guest@example.com', form_token=csrf)
    assert client.post('/audit/email-report', data=data).status_code == 400
    with appmod.app.app_context(): assert appmod.db.q('SELECT COUNT(*) n FROM inquiries', one=True)['n'] == 0


@pytest.mark.parametrize('email', ['', 'not-an-email', 'bad@address', 'a b@example.com', 'x'*250+'@example.com'])
def test_scan_capture_email_validation_keeps_report(client, email):
    _, data = scan_context(client)
    response = client.post('/audit/email-report', data={**data, 'email': email})
    assert response.status_code == 400
    assert b'Enter a valid email' in response.data and b'Current Salon' in response.data and b'40%' in response.data
    with appmod.app.app_context(): assert appmod.db.q('SELECT COUNT(*) n FROM inquiries', one=True)['n'] == 0


def test_guest_scan_capture_stores_inquiry_not_audit(client):
    _, data = scan_context(client)
    response = client.post('/audit/email-report', data={**data, 'email': 'Guest@Example.com', 'name': 'Forged business'})
    assert response.status_code == 200
    for text in (b'Your email is saved.', b'No email has been sent.', b'Your report stays on this page.', b'40%', b'Current Salon'):
        assert text in response.data
    with appmod.app.app_context():
        row = appmod.db.q('SELECT * FROM inquiries', one=True)
        assert row['plan'] == 'free-scan' and row['email'] == 'guest@example.com' and row['user_id'] is None
        assert row['business'] == row['name'] == 'Current Salon' and row['city'] == 'Oakland' and row['phone'] == '5105550100'
        assert '10 Main St' in row['message'] and 'guest (report not stored)' in row['message']
        assert appmod.db.q('SELECT COUNT(*) n FROM audits', one=True)['n'] == 0


def test_saved_scan_capture_references_owned_audit(client):
    client.post('/signup', data=dict(email='scan@example.com', password='test-password'))
    _, data = scan_context(client)
    response = client.post('/audit/email-report', data={**data, 'email': 'scan@example.com'})
    assert b'It is already saved to your dashboard.' in response.data
    with appmod.app.app_context():
        row = appmod.db.q('SELECT * FROM inquiries', one=True)
        audit = appmod.db.q('SELECT * FROM audits', one=True)
        assert row['user_id'] == audit['user_id'] and f"Audit id: {audit['id']}" in row['message']
    saved = client.get('/audits/1')
    assert saved.status_code == 200 and b'Email me this report' in saved.data


def test_scan_capture_rejects_modified_or_expired_context(client, monkeypatch):
    _, data = scan_context(client)
    assert client.post('/audit/email-report', data={**data, 'email': 'a@example.com', 'report_context': data['report_context']+'x'}).status_code == 400
    import itsdangerous.timed
    original_time = itsdangerous.timed.time.time
    with monkeypatch.context() as patch:
        patch.setattr(itsdangerous.timed.time, 'time', lambda: original_time()+86401)
        assert client.post('/audit/email-report', data={**data, 'email': 'a@example.com'}).status_code == 400
    with appmod.app.app_context(): assert appmod.db.q('SELECT COUNT(*) n FROM inquiries', one=True)['n'] == 0


def test_scan_capture_context_cannot_cross_accounts(client):
    client.post('/signup', data=dict(email='scan-a@example.com', password='test-password'))
    _, data = scan_context(client)
    client.get('/logout')
    client.post('/signup', data=dict(email='scan-b@example.com', password='test-password'))
    client.get('/audit')
    with client.session_transaction() as sess: data['form_token'] = sess['form_token']
    assert client.post('/audit/email-report', data={**data, 'email': 'b@example.com'}).status_code == 400


def test_production_design_assets_and_links(client):
    for path in ('/', '/audit', '/services', '/gbp', '/reviews/request', '/competitors', '/inquire', '/login', '/signup', '/brand'):
        response = client.get(path)
        assert response.status_code == 200
        for forbidden in (b'DESIGN PREVIEW', b'Local prototype', b'Not the live app', b'href="audit.html', b'app.js'):
            assert forbidden not in response.data
        assert b'/static/product.js' in response.data and b'/static/styles.css' in response.data
    home = client.get('/').data
    assert b'Illustration' in home and b'not live fixes' in home
    css = client.get('/static/styles.css')
    assert css.status_code == 200 and css.data.startswith(b"@import url('fonts.css');\n")
    fonts = client.get('/static/fonts.css')
    assert fonts.status_code == 200
    import re
    for asset in re.findall(rb'url\(([^)]+)\)', fonts.data):
        assert client.get('/static/'+asset.decode()).status_code == 200
