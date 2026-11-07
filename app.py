"""SolvFix MVP web app (local only). Run: .venv/bin/python app.py -> http://127.0.0.1:5000"""
import os, json, functools, datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
from werkzeug.security import generate_password_hash, check_password_hash
from audit import run_audit
import db, bots

app = Flask(__name__)
app.secret_key = os.environ.get("SOLVFIX_SECRET", os.urandom(24))
app.teardown_appcontext(db.close)

def login_required(f):
    @functools.wraps(f)
    def w(*a, **k):
        if not session.get("uid"): return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return w

@app.context_processor
def ctx(): return dict(user=session.get("email"))

@app.route("/")
def landing(): return render_template("landing.html")

@app.route("/brand")
def brand(): return render_template("brand.html")

# ---------- auth ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower(); pw = request.form.get("password", "")
        if "@" not in email or len(pw) < 8: flash("Enter a valid email and a password of at least 8 characters.")
        elif db.q("SELECT 1 FROM users WHERE email=?", (email,), one=True): flash("That email already has an account. Log in instead.")
        else:
            uid = db.x("INSERT INTO users(email,pw_hash) VALUES(?,?)", (email, generate_password_hash(pw)))
            session.clear(); session.update(uid=uid, email=email); return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="signup")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = db.q("SELECT * FROM users WHERE email=?", (email,), one=True)
        if u and check_password_hash(u["pw_hash"], request.form.get("password", "")):
            session.clear(); session.update(uid=u["id"], email=email)
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Wrong email or password.")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("landing"))

# ---------- audit (Bot 1) ----------
@app.route("/audit", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        biz = {k: request.form.get(k, "").strip() for k in ("name", "address", "phone", "city")}
        r = run_audit(biz, use_search=not request.form.get("nosearch"))
        aid = None
        if session.get("uid"):
            aid = db.x("INSERT INTO audits(user_id,name,address,phone,city,score,results_json) VALUES(?,?,?,?,?,?,?)",
                       (session["uid"], biz["name"], biz["address"], biz["phone"], biz.get("city", ""), r["overall"], json.dumps(r["results"])))
            for it in bots.fix_checklist(r["results"], biz):
                db.x("INSERT INTO fix_items(audit_id,site,issue,steps,claim_url) VALUES(?,?,?,?,?)", (aid, it["site"], it["issue"], it["steps"], it["claim_url"]))
        return render_template("report.html", r=r, aid=aid)
    return render_template("form.html")

def own_audit(aid):
    a = db.q("SELECT * FROM audits WHERE id=? AND user_id=?", (aid, session["uid"]), one=True)
    if not a: abort(404)
    return a

@app.route("/dashboard")
@login_required
def dashboard():
    audits = db.q("SELECT a.*, (SELECT COUNT(*) FROM fix_items f WHERE f.audit_id=a.id) n, (SELECT COUNT(*) FROM fix_items f WHERE f.audit_id=a.id AND done=1) d "
                  "FROM audits a WHERE user_id=? ORDER BY id DESC", (session["uid"],))
    nrev = db.q("SELECT COUNT(*) c FROM reviews WHERE user_id=?", (session["uid"],), one=True)["c"]
    batches = db.q("SELECT id,business,month,source,created FROM post_batches WHERE user_id=? ORDER BY id DESC", (session["uid"],))
    return render_template("dashboard.html", audits=audits, nrev=nrev, batches=batches)

@app.route("/audits/<int:aid>")
@login_required
def audit_view(aid):
    a = own_audit(aid); res = json.loads(a["results_json"])
    r = dict(business=dict(name=a["name"], address=a["address"], phone=a["phone"]), results=res, overall=a["score"],
             listed=sum(1 for x in res if "score" in x), checked=sum(1 for x in res if x["status"] not in ("Skipped", "Error")))
    return render_template("report.html", r=r, aid=aid, created=a["created"])

# ---------- Bot 2: Fix ----------
@app.route("/audits/<int:aid>/fix", methods=["GET", "POST"])
@login_required
def fix(aid):
    a = own_audit(aid)
    if request.method == "POST":
        db.x("UPDATE fix_items SET done=? WHERE id=? AND audit_id=?", (1 if request.form.get("done") == "1" else 0, request.form.get("item"), aid))
        return redirect(url_for("fix", aid=aid))
    items = db.q("SELECT * FROM fix_items WHERE audit_id=? ORDER BY done, id", (aid,))
    return render_template("fix.html", a=a, items=items)

# ---------- Bot 3: Reviews ----------
def biz_name():
    a = db.q("SELECT name FROM audits WHERE user_id=? ORDER BY id DESC", (session["uid"],), one=True)
    return request.form.get("business") or (a["name"] if a else "our business")

@app.route("/reviews", methods=["GET", "POST"])
@login_required
def reviews():
    uid = session["uid"]
    if request.method == "POST":
        act = request.form.get("action")
        if act == "import":
            f = request.files.get("csv"); csv_text = f.read().decode("utf-8", "replace") if f and f.filename else None
            got = bots.parse_reviews(text=request.form.get("text"), csv_text=csv_text, platform=request.form.get("platform") or "Manual")
            for r in got:
                db.x("INSERT INTO reviews(user_id,platform,author,rating,text) VALUES(?,?,?,?,?)", (uid, r["platform"], r["author"], r["rating"], r["text"]))
            flash(f"Imported {len(got)} review(s).")
        elif act in ("draft", "save", "approve", "unapprove", "delete"):
            rv = db.q("SELECT * FROM reviews WHERE id=? AND user_id=?", (request.form.get("id"), uid), one=True)
            if rv:
                if act == "draft": db.x("UPDATE reviews SET reply=?, status='draft' WHERE id=?", (bots.reply_draft(dict(rv), biz_name()), rv["id"]))
                elif act == "save": db.x("UPDATE reviews SET reply=? WHERE id=?", (request.form.get("reply", ""), rv["id"]))
                elif act == "approve": db.x("UPDATE reviews SET reply=?, status='approved' WHERE id=?", (request.form.get("reply", ""), rv["id"]))
                elif act == "unapprove": db.x("UPDATE reviews SET status='draft' WHERE id=?", (rv["id"],))
                else: db.x("DELETE FROM reviews WHERE id=?", (rv["id"],))
        elif act == "draft_all":
            for rv in db.q("SELECT * FROM reviews WHERE user_id=? AND reply=''", (uid,)):
                db.x("UPDATE reviews SET reply=? WHERE id=?", (bots.reply_draft(dict(rv), biz_name()), rv["id"]))
        return redirect(url_for("reviews"))
    rows = db.q("SELECT * FROM reviews WHERE user_id=? ORDER BY status, id DESC", (uid,))
    return render_template("reviews.html", rows=rows)

@app.route("/reviews.csv")
@login_required
def reviews_csv():
    rows = [dict(r) for r in db.q("SELECT platform,author,rating,text,reply,status FROM reviews WHERE user_id=?", (session["uid"],))]
    return Response(bots.to_csv(rows, ["platform", "author", "rating", "text", "reply", "status"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=solvfix_reviews.csv"})

# ---------- Bot 4: Social ----------
@app.route("/social", methods=["GET", "POST"])
@login_required
def social():
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in ("name", "btype", "city", "tone", "month")}
        posts, src = bots.social_posts(f["name"], f["btype"] or "local business", f["city"], f["tone"] or "friendly", f["month"] or None)
        bid = db.x("INSERT INTO post_batches(user_id,business,btype,city,tone,month,posts_json,source) VALUES(?,?,?,?,?,?,?,?)",
                   (session["uid"], f["name"], f["btype"], f["city"], f["tone"], posts[0]["day"][:7], json.dumps(posts), src))
        return redirect(url_for("social_batch", bid=bid))
    last = db.q("SELECT name,city FROM audits WHERE user_id=? ORDER BY id DESC", (session["uid"],), one=True)
    return render_template("social.html", last=last, month=datetime.date.today().strftime("%Y-%m"), posts=None)

def own_batch(bid):
    b = db.q("SELECT * FROM post_batches WHERE id=? AND user_id=?", (bid, session["uid"]), one=True)
    if not b: abort(404)
    return b

@app.route("/social/<int:bid>")
@login_required
def social_batch(bid):
    b = own_batch(bid); return render_template("social.html", b=b, posts=json.loads(b["posts_json"]))

@app.route("/social/<int:bid>.csv")
@login_required
def social_csv(bid):
    b = own_batch(bid)
    return Response(bots.to_csv(json.loads(b["posts_json"]), ["day", "pillar", "text", "hashtags", "status"]), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=solvfix_posts_{b['month']}.csv"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
