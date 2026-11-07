"""Opt-in live-network smoke test: python test_audit.py (not run at import)."""

def main():
    from app import app
    c = app.test_client()
    r = c.post("/audit", data={"name": "Tartine Bakery", "address": "600 Guerrero St, San Francisco, CA 94110", "city": "San Francisco", "phone": "(415) 487-2600"})
    assert c.get("/").status_code==200 and c.get("/brand").status_code==200 and c.get("/audit").status_code==200
    open("sample_report.html", "wb").write(r.data); print(r.status_code)
    import re; print(re.sub(r"<[^>]+>", " ", r.data.decode())[:3000])

if __name__ == "__main__":
    main()
