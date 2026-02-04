from fastapi import FastAPI, Header, HTTPException, Request
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
# KEYWORDS
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

SAFE_MESSAGES = {
    "hi","hello","hey","ok","okay","yes","no","thanks","thank you"
}

UPI_REGEX = r"[\w.-]+@[\w.-]+"
URL_REGEX = r"https?://[^\s]+"

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
# CORE DETECTION ENGINE
# =========================================================
def detect(msg: str):
    msg = msg.lower().strip()
    score = 0
    ml_conf = 0.0

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

    if msg in SAFE_MESSAGES:
        return False, 0.05

    for k in SCAM_KEYWORDS:
        if k in msg:
            score += 1

    for s in DATASET[:300]:
        if s in msg:
            score += 5
            break

    if ML_MODEL and VECTORIZER:
        try:
            vec = VECTORIZER.transform([msg])
            ml_conf = ML_MODEL.predict_proba(vec)[0][1]
            score += int(ml_conf * 5)
        except:
            ml_conf = 0.0

    confidence = min((score / 12 + ml_conf) / 2, 1.0)
    return score >= 6 or ml_conf > 0.70, confidence

# =========================================================
# 🔥 HACKATHON REQUIRED ENDPOINT (ONLY ADDITION)
# =========================================================
@app.post("/")
async def hackathon_api(request: Request, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    body = await request.json()
    text = body.get("message", {}).get("text", "")
    scam, conf = detect(text)

    return {
        "status": "success",
        "reply": "Why is my account being suspended?"
    }

# =========================================================
# LANDING PAGE (YOUR OLD UI)
# =========================================================
@app.get("/", response_class=HTMLResponse)
def landing():
    return """
<!DOCTYPE html>
<html>
<body style="background:#020617;color:white;font-family:Poppins;text-align:center;padding-top:100px">
<h1>RAKSHAK AI</h1>
<p>Agentic Scam Detection Honeypot</p>
<a href="/user">User Portal</a> | <a href="/admin">Admin Dashboard</a>
</body>
</html>
"""

# =========================================================
# USER PORTAL (UNCHANGED)
# =========================================================
@app.get("/user", response_class=HTMLResponse)
def user():
    return """
<!DOCTYPE html>
<html>
<body style="background:#020617;color:white;font-family:Poppins;padding:40px">
<h2>Scam Message Checker</h2>
<textarea id="msg" style="width:100%;height:120px"></textarea><br><br>
<button onclick="go()">Analyze</button>
<h3 id="out"></h3>
<script>
async function go(){
 const r = await fetch("/honeypot",{
  method:"POST",
  headers:{
    "Content-Type":"application/json",
    "x-api-key":"rakshak-secret-key"
  },
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
# ADMIN DASHBOARD (UNCHANGED)
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
# ORIGINAL HONEYPOT API (UNCHANGED)
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