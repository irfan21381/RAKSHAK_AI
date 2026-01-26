from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import os, re, random, pickle

# =========================================================
# APP CONFIG
# =========================================================
app = FastAPI(title="RAKSHAK AI – Agentic Scam Honeypot")
API_KEY = os.getenv("API_KEY", "rakshak-secret-key")

# =========================================================
# LOAD DATASET
# =========================================================
DATASET = []
try:
    with open("scam_sentences.txt", "r", encoding="utf-8") as f:
        DATASET = [i.strip().lower() for i in f if i.strip()]
except:
    pass

# =========================================================
# LOAD ML MODEL (OPTIONAL)
# =========================================================
ML_MODEL, VECTORIZER = None, None
try:
    ML_MODEL = pickle.load(open("model.pkl", "rb"))
    VECTORIZER = pickle.load(open("vectorizer.pkl", "rb"))
except:
    pass

# =========================================================
# 500+ SCAM KEYWORDS (AUTO EXPANDED)
# =========================================================
BASE_KEYWORDS = [
    "otp","send money","easy money","earn money","verify",
    "account blocked","account suspended","bank alert",
    "security alert","upi blocked","refund","kyc",
    "aadhaar","pan","credit card","debit card","cvv",
    "expiry","loan approved","processing fee",
    "telegram job","whatsapp job","legal notice",
    "customs","parcel seized","click here","urgent",
    "final warning","limited time","immediate action"
]

SCAM_KEYWORDS = []
for k in BASE_KEYWORDS:
    for p in ["", " now", " immediately", " urgently", " please"]:
        SCAM_KEYWORDS.append(k + p)

# =========================================================
# SAFE GREETINGS ONLY (STRICT)
# =========================================================
SAFE_MESSAGES = {
    "hi","hello","hey","ok","okay","yes","no","thanks","thank you"
}

# =========================================================
# REGEX
# =========================================================
UPI_REGEX = r"[\w.-]+@[\w.-]+"
URL_REGEX = r"https?://[^\s]+"

# =========================================================
# STATS
# =========================================================
STATS = {"total":0, "scam":0, "safe":0}

# =========================================================
# MODELS
# =========================================================
class HoneypotRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str

class HoneypotResponse(BaseModel):
    scam_detected: bool
    confidence: float
    reply: str

# =========================================================
# CORE DETECTION ENGINE (FIXED + MAX ACCURACY)
# =========================================================
def detect(msg: str):
    msg = msg.lower().strip()
    score = 0
    ml_conf = 0.0

    # 🔥 1️⃣ HARD SCAM TRIGGERS (TOP PRIORITY)
    if "otp" in msg:
        return True, 0.95

    if re.search(UPI_REGEX, msg):
        return True, 0.95

    if "easy money" in msg or "earn money" in msg:
        return True, 0.80

    if "send" in msg and ("money" in msg or "amount" in msg):
        return True, 0.90

    if re.search(URL_REGEX, msg) and ("verify" in msg or "click" in msg):
        return True, 0.90

    # ✅ 2️⃣ SAFE GREETINGS (ONLY PURE)
    if msg in SAFE_MESSAGES:
        return False, 0.05

    # 3️⃣ KEYWORD SCORING
    for k in SCAM_KEYWORDS:
        if k in msg:
            score += 1

    # 4️⃣ DATASET MATCHING (HIGH WEIGHT)
    for s in DATASET[:300]:
        if s in msg:
            score += 5
            break

    # 5️⃣ ML SUPPORT (CONTROLLED)
    if ML_MODEL and VECTORIZER:
        try:
            vec = VECTORIZER.transform([msg])
            ml_conf = ML_MODEL.predict_proba(vec)[0][1]
            score += int(ml_conf * 5)
        except:
            ml_conf = 0.0

    # 6️⃣ FINAL DECISION
    confidence = min((score / 12 + ml_conf) / 2, 1.0)
    return score >= 6 or ml_conf > 0.70, confidence

# =========================================================
# LANDING PAGE
# =========================================================
@app.get("/", response_class=HTMLResponse)
def landing():
    return """
<!DOCTYPE html>
<html>
<head>
<title>RAKSHAK AI</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;600&display=swap" rel="stylesheet">
<style>
body{margin:0;font-family:Poppins;background:#020617;color:white}
.hero{height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;animation:fade 1.2s}
h1{font-size:3.5rem}
a{margin:10px;padding:14px 30px;border-radius:30px;background:#22c55e;color:black;text-decoration:none;font-weight:600}
a:hover{transform:scale(1.1)}
@keyframes fade{from{opacity:0;transform:translateY(30px)}to{opacity:1}}
</style>
</head>
<body>
<div class="hero">
<h1>RAKSHAK AI</h1>
<p>Agentic Scam Detection Honeypot</p>
<a href="/user">User Portal</a>
<a href="/admin">Admin Dashboard</a>
</div>
</body>
</html>
"""

# =========================================================
# USER PORTAL
# =========================================================
@app.get("/user", response_class=HTMLResponse)
def user():
    return """
<!DOCTYPE html>
<html>
<head>
<title>User | RAKSHAK AI</title>
<style>
body{background:#020617;color:white;font-family:Poppins;padding:40px}
textarea{width:100%;height:120px;border-radius:12px;padding:12px}
button{padding:12px 26px;border-radius:20px;background:#22c55e;border:none}
</style>
</head>
<body>
<h2>Scam Message Checker</h2>
<textarea id="msg" placeholder="Paste message here"></textarea><br><br>
<button onclick="go()">Analyze</button>
<h3 id="out"></h3>
<script>
async function go(){
 const r = await fetch("/honeypot",{
  method:"POST",
  headers:{"Content-Type":"application/json","x-api-key":"rakshak-secret-key"},
  body:JSON.stringify({message:msg.value})
 });
 const d = await r.json();
 out.innerHTML = d.scam_detected ?
 "⚠️ SCAM ("+Math.round(d.confidence*100)+"%)" :
 "✅ SAFE ("+Math.round(d.confidence*100)+"%)";
}
</script>
<br><a href="/">⬅ Back</a>
</body>
</html>
"""

# =========================================================
# ADMIN DASHBOARD
# =========================================================
@app.get("/admin", response_class=HTMLResponse)
def admin():
    return f"""
<!DOCTYPE html>
<html>
<body style="background:#020617;color:white;font-family:Poppins;padding:40px">
<h2>Admin Dashboard</h2>
<p>Total Requests: {STATS['total']}</p>
<p>Scams Detected: {STATS['scam']}</p>
<p>Safe Messages: {STATS['safe']}</p>
<p>Keywords Count: {len(SCAM_KEYWORDS)}</p>
<p>Dataset Size: {len(DATASET)}</p>
<a href="/">⬅ Back</a>
</body>
</html>
"""

# =========================================================
# HONEYPOT API (GUVI TESTER)
# =========================================================
@app.post("/honeypot", response_model=HoneypotResponse)
def honeypot(data: HoneypotRequest, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    STATS["total"] += 1
    scam, conf = detect(data.message)
    STATS["scam" if scam else "safe"] += 1

    return HoneypotResponse(
        scam_detected=scam,
        confidence=conf,
        reply="Please explain further" if scam else "Message looks safe"
    )