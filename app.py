"""CertForge - Excel -> PDF certificate automation. Run: python app.py"""
import io, zipfile, uuid, datetime as dt
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, abort
from certificate import build_pdf, tier_for, cert_id, DEFAULT_SIGNERS, ASSET_DIR, find_asset
import os
from ai import generate_citation

VERSION = "2.3"
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
STORE: dict[str, dict] = {}   # in-memory session store: {sid: {"company":..., "rows":[...]}}

REQUIRED = {"name": ["name", "candidate", "candidate name"], "email": ["email", "mail"],
            "role": ["role", "position", "designation"], "department": ["department", "dept", "team"],
            "score": ["score", "performance", "performance score"], "attendance": ["attendance", "attendance %"],
            "rating": ["rating", "company performance", "company rating"], "date": ["date", "issue date"],
            "year": ["year of study", "year", "study year"], "start": ["start date", "start", "from"], "end": ["end date", "end", "to"]}

def normalise(df: pd.DataFrame):
    cols = {str(c).strip().lower(): c for c in df.columns}
    mapping, missing = {}, []
    for key, aliases in REQUIRED.items():
        hit = next((cols[a] for a in aliases if a in cols), None)
        if hit is None and key not in ("date", "attendance", "rating", "email", "year", "start", "end"):
            missing.append(key)
        mapping[key] = hit
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))
    rows, errors = [], []
    today = dt.date.today().strftime("%d %b %Y")
    for i, r in df.iterrows():
        g = lambda k, d="": (r[mapping[k]] if mapping[k] is not None and pd.notna(r[mapping[k]]) else d)
        try:
            score = float(g("score"))
            if not 0 <= score <= 100: raise ValueError("score must be 0-100")
            fmt = lambda v: pd.to_datetime(v).strftime("%d %b %Y") if v != "" else ""
            start, end = fmt(g("start")), fmt(g("end"))
            d = fmt(g("date")) or end or today
            c = dict(id=len(rows), name=str(g("name")).strip(), email=str(g("email", "n/a")).strip(), role=str(g("role")).strip(),
                     department=str(g("department")).strip(), score=score, attendance=float(g("attendance", 100)),
                     rating=str(g("rating", "Meets Expectations")).strip(), date=d,
                     year=str(g("year")).replace(".0", "").strip(), start=start, end=end)
            if not c["name"]: raise ValueError("empty name")
            c["tier"] = tier_for(score); c["cert_id"] = cert_id(c); c["citation"] = ""
            rows.append(c)
        except Exception as e:
            errors.append(f"Row {i + 2}: {e}")
    return rows, errors

@app.get("/")
def index(): return render_template("index.html", version=VERSION)

@app.after_request
def no_cache(r):
    r.headers["Cache-Control"] = "no-store"; return r

KINDS = ("logo", "seal", "sig1", "sig2")

@app.get("/api/assets")
def assets(): return jsonify({k: bool(find_asset(k)) for k in KINDS})

@app.post("/api/asset/<kind>")
def upload_asset(kind):
    f = request.files.get("file")
    ext = (f.filename.rsplit(".", 1)[-1].lower() if f and "." in f.filename else "")
    if kind not in KINDS or ext not in ("png", "jpg", "jpeg"): return jsonify(error="PNG or JPG only"), 400
    os.makedirs(ASSET_DIR, exist_ok=True); _rm(kind)
    f.save(os.path.join(ASSET_DIR, f"{kind}.{ext}")); return jsonify(ok=True)

def _rm(kind):
    for e in ("png", "jpg", "jpeg"):
        p = os.path.join(ASSET_DIR, f"{kind}.{e}")
        if os.path.exists(p): os.remove(p)

@app.delete("/api/asset/<kind>")
def delete_asset(kind):
    if kind in KINDS: _rm(kind)
    return jsonify(ok=True)

@app.get("/api/sample")
def sample():
    df = pd.DataFrame([
        ["Aarav Sharma", "aarav@mail.com", "Data Analyst", "Analytics", 94, 98, "Outstanding", "2026-09-30"],
        ["Meera Iyer", "meera@mail.com", "UX Designer", "Design", 82, 95, "Exceeds Expectations", "2026-09-30"],
        ["Karthik Raj", "karthik@mail.com", "Backend Engineer", "Engineering", 68, 90, "Meets Expectations", "2026-09-30"],
        ["Divya Nair", "divya@mail.com", "QA Engineer", "Engineering", 55, 84, "Needs Improvement", "2026-09-30"]],
        columns=["Name", "Email", "Role", "Department", "Score", "Attendance", "Company Rating", "Date"])  # legacy sample
    b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0)
    return send_file(b, as_attachment=True, download_name="candidates_sample.xlsx")

@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f: return jsonify(error="No file uploaded"), 400
    try:
        df = pd.read_excel(f) if f.filename.lower().endswith((".xlsx", ".xls")) else pd.read_csv(f)
        rows, errors = normalise(df)
    except Exception as e:
        return jsonify(error=str(e)), 400
    if not rows: return jsonify(error="No valid rows found", warnings=errors), 400
    sid = uuid.uuid4().hex
    STORE[sid] = {"company": "Nexora Technologies Pvt. Ltd.", "rows": rows}
    return jsonify(sid=sid, rows=rows, warnings=errors)

def _get(sid, cid=None):
    s = STORE.get(sid) or abort(404)
    if cid is None: return s, None
    row = next((r for r in s["rows"] if r["id"] == cid), None) or abort(404)
    return s, row

@app.post("/api/citation/<sid>/<int:cid>")
def citation(sid, cid):
    s, row = _get(sid, cid)
    s["company"] = (request.json or {}).get("company") or s["company"]
    row["citation"], source = generate_citation(row, s["company"])
    return jsonify(citation=row["citation"], source=source)

@app.post("/api/citation/<sid>/<int:cid>/save")
def save_citation(sid, cid):
    _, row = _get(sid, cid); row["citation"] = (request.json or {}).get("citation", ""); return jsonify(ok=True)

def _signers():
    g = request.args.get
    return [(g("s1n") or DEFAULT_SIGNERS[0][0], g("s1t") or DEFAULT_SIGNERS[0][1]),
            (g("s2n") or DEFAULT_SIGNERS[1][0], g("s2t") or DEFAULT_SIGNERS[1][1])]

def _pdf(s, row, company):
    if not row["citation"]: row["citation"], _ = generate_citation(row, company)
    return build_pdf(row, company, row["citation"], _signers(), request.args.get("hm", "tier"))

@app.get("/api/pdf/<sid>/<int:cid>")
def one_pdf(sid, cid):
    s, row = _get(sid, cid); company = request.args.get("company") or s["company"]
    return send_file(io.BytesIO(_pdf(s, row, company)), mimetype="application/pdf",
                     download_name=f"{row['name'].replace(' ', '_')}_certificate.pdf")

@app.get("/api/zip/<sid>")
def zip_all(sid):
    s, _ = _get(sid); company = request.args.get("company") or s["company"]
    ids = request.args.get("ids"); sel = {int(i) for i in ids.split(",")} if ids else None
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for r in s["rows"]:
            if sel is None or r["id"] in sel:
                z.writestr(f"{r['name'].replace(' ', '_')}_{r['cert_id']}.pdf", _pdf(s, r, company))
    b.seek(0)
    return send_file(b, mimetype="application/zip", download_name="certificates.zip")

if __name__ == "__main__":
    import os
    print(f"\n=== CertForge v{VERSION} running from: {os.path.dirname(os.path.abspath(__file__))} ===")
    print("Open http://127.0.0.1:5000  (press Ctrl+F5 in the browser)\n")
    app.run(debug=False, port=5000)
