"""PDF certificate rendering (ReportLab)."""
import io, os, random, hashlib
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "GreatVibes-Regular.ttf")
try:
    pdfmetrics.registerFont(TTFont("Signature", FONT_PATH)); HAS_SIG_FONT = True
except Exception:
    HAS_SIG_FONT = False

NAVY, GOLD, INK, MUTED, BLUE = HexColor("#14213d"), HexColor("#c8a24a"), HexColor("#1f2937"), HexColor("#6b7280"), HexColor("#1d3a8a")
TIERS = [(90, "Excellence"), (75, "Distinction"), (60, "Merit"), (0, "Completion")]
DEFAULT_SIGNERS = [("Rajesh Menon", "Chief Executive Officer"), ("Anitha Krishnan", "Head of People & Culture")]
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")   # uploaded: logo, seal, sig1, sig2


def find_asset(kind):
    for ext in ("png", "jpg", "jpeg"):
        path = os.path.join(ASSET_DIR, f"{kind}.{ext}")
        if os.path.exists(path): return path


def tier_for(score: float) -> str:
    return next(name for cut, name in TIERS if score >= cut)


def cert_id(c: dict) -> str:
    return "CERT-" + hashlib.sha1(f"{c['name']}|{c['email']}|{c['date']}".encode()).hexdigest()[:10].upper()


def _signature(p, x, y, name, idx, w=140):
    """Draw a signature: uploaded PNG (signatures/sig<idx>.png) if present, else a handwritten-style scribble."""
    img = find_asset(f"sig{idx}")
    if img:
        p.drawImage(img, x - w / 2, y, width=w, height=44, preserveAspectRatio=True, mask="auto"); return
    if HAS_SIG_FONT:   # signature = the signatory's name in a handwriting font
        size = 34
        while pdfmetrics.stringWidth(name, "Signature", size) > w + 20 and size > 16: size -= 1
        p.saveState(); p.translate(x, y + 6); p.rotate(3)
        p.setFillColor(BLUE); p.setFont("Signature", size); p.drawCentredString(0, 0, name)
        tw = pdfmetrics.stringWidth(name, "Signature", size)
        p.setStrokeColor(BLUE); p.setLineWidth(.8)
        path = p.beginPath(); path.moveTo(-tw / 2, -3); path.curveTo(-tw / 4, -7, tw / 4, 1, tw / 2 + 6, -2)
        p.drawPath(path, stroke=1, fill=0); p.restoreState(); return
    rnd = random.Random(name)
    path = p.beginPath(); cx = x - w / 2; path.moveTo(cx, y + 4)
    n = 5 + len(name) % 3; step = w / n
    for _ in range(n):
        h = rnd.uniform(12, 30)
        path.curveTo(cx + step * .15, y + h, cx + step * .5, y - h * .35, cx + step, y + rnd.uniform(0, 12)); cx += step
    path.curveTo(cx - w * .3, y - 4, cx - w * .6, y + 8, x - w * .5, y - 2)
    p.setStrokeColor(BLUE); p.setLineWidth(1.5); p.drawPath(path, stroke=1, fill=0)


def build_pdf(c: dict, company: str, citation: str, signers=None, heading_mode: str = "tier") -> bytes:
    signers = signers or DEFAULT_SIGNERS
    buf = io.BytesIO(); W, H = landscape(A4)
    p = canvas.Canvas(buf, pagesize=(W, H)); p.setTitle(f"Certificate - {c['name']}")
    tier = tier_for(c["score"])

    # background + frame
    p.setFillColor(HexColor("#fdfbf5")); p.rect(0, 0, W, H, fill=1, stroke=0)
    p.setFillColor(NAVY); p.rect(0, 0, 38, H, fill=1, stroke=0)
    p.setStrokeColor(GOLD); p.setLineWidth(2.5); p.rect(56, 22, W - 78, H - 44)
    p.setLineWidth(0.6); p.rect(62, 28, W - 90, H - 56)
    cx = 38 + (W - 38) / 2

    # company header with monogram logo
    logo = find_asset("logo")
    if logo:
        p.drawImage(logo, cx - 45, H - 92, width=90, height=60, preserveAspectRatio=True, mask="auto", anchor="c")
    else:
        initials = "".join(w[0] for w in company.replace(".", "").split()[:2]).upper()
        p.setFillColor(NAVY); p.circle(cx, H - 62, 20, fill=1, stroke=0)
        p.setStrokeColor(GOLD); p.setLineWidth(1.2); p.circle(cx, H - 62, 23, fill=0, stroke=1)
        p.setFillColor(GOLD); p.setFont("Times-Bold", 15); p.drawCentredString(cx, H - 67, initials)
    p.setFillColor(NAVY); p.setFont("Helvetica-Bold", 15); p.drawCentredString(cx, H - 102, company.upper())

    p.setFillColor(GOLD); p.setFont("Times-Bold", 40); p.drawCentredString(cx, H - 150, "CERTIFICATE")
    p.setFillColor(MUTED); p.setFont("Helvetica", 11)
    tier = tier_for(c["score"])
    sub = "OF INTERNSHIP COMPLETION" if (heading_mode == "completion" or tier == "Completion") else f"OF INTERNSHIP {tier.upper()}"
    p.drawCentredString(cx, H - 171, sub)

    p.setFillColor(INK); p.setFont("Helvetica", 12)
    p.drawCentredString(cx, H - 203, "This certificate is proudly presented to")
    p.setFont("Times-BoldItalic", 34); p.setFillColor(NAVY); p.drawCentredString(cx, H - 245, c["name"])
    p.setStrokeColor(GOLD); p.setLineWidth(1); p.line(cx - 170, H - 255, cx + 170, H - 255)

    # body: role / dept / year
    year = c.get("year", "")
    yr = f" ({year if 'year' in year.lower() else 'Year ' + year} student)" if year else ""
    body = f"for successfully completing the internship as {c['role']} in the {c['department']} department{yr}."
    p.setFillColor(INK); p.setFont("Helvetica", 12); y = H - 281
    for line in simpleSplit(body, "Helvetica", 12, W - 280):
        p.drawCentredString(cx, y, line); y -= 17

    # internship period badge
    if c.get("start") and c.get("end"):
        bw = 330; y -= 6
        p.setStrokeColor(GOLD); p.setFillColor(HexColor("#f7efd9")); p.setLineWidth(1)
        p.roundRect(cx - bw / 2, y - 14, bw, 26, 13, fill=1, stroke=1)
        p.setFillColor(NAVY); p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(cx, y - 5, f"{c['start']}   to   {c['end']}"); y -= 34

    p.setFillColor(INK); p.setFont("Times-Italic", 13)
    for line in simpleSplit(citation, "Times-Italic", 13, W - 270)[:3]:
        p.drawCentredString(cx, y, line); y -= 17

    # signatures
    lx, rx, base = 200, W - 190, 112
    for (sx, (nm, ttl)), i in zip(((lx, signers[0]), (rx, signers[1])), (1, 2)):
        _signature(p, sx, base + 6, nm, i)
        p.setStrokeColor(INK); p.setLineWidth(.7); p.line(sx - 85, base, sx + 85, base)
        p.setFillColor(NAVY); p.setFont("Helvetica-Bold", 11); p.drawCentredString(sx, base - 14, nm)
        p.setFillColor(MUTED); p.setFont("Helvetica", 9); p.drawCentredString(sx, base - 27, ttl)
        p.drawCentredString(sx, base - 39, company)

    # seal: uploaded image or generated gold seal
    seal = find_asset("seal")
    if seal:
        p.drawImage(seal, cx - 42, base + 12 - 42, width=84, height=84, preserveAspectRatio=True, mask="auto", anchor="c")
    else:
        p.setFillColor(GOLD); p.circle(cx, base + 12, 36, fill=1, stroke=0)
        p.setStrokeColor(white); p.setLineWidth(1.2); p.circle(cx, base + 12, 31, fill=0, stroke=1)
        p.setFillColor(NAVY); p.setFont("Helvetica-Bold", 8); p.drawCentredString(cx, base + 22, "OFFICIAL")
        p.setFont("Times-Bold", 12); p.drawCentredString(cx, base + 9, "CERTIFIED"); p.setFont("Helvetica", 8)
        p.drawCentredString(cx, base - 2, c["date"][-4:])

    # footer
    p.setFillColor(MUTED); p.setFont("Helvetica", 9)
    p.drawCentredString(cx, 44, f"Issued on {c['date']}")
    p.drawString(100, 36, f"Certificate ID: {cert_id(c)}")
    w = qr.QrCodeWidget(f"{company}|{cert_id(c)}|{c['name']}|{c['start']}|{c['end']}"); b = w.getBounds(); size = 44
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0]); d.add(w)
    renderPDF.draw(d, p, W - 100, 34)
    p.showPage(); p.save()
    return buf.getvalue()
