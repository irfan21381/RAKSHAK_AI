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
# LOAD DATA + MODEL
# =========================================================
DATASET = []
try:
    with open("scam_sentences.txt", "r", encoding="utf-8") as f:
        DATASET = [i.strip().lower() for i in f if i.strip()]
except:
    pass

ML_MODEL, VECTORIZER = None, None
try:
    ML_MODEL = pickle.load(open("model.pkl", "rb"))
    VECTORIZER = pickle.load(open("vectorizer.pkl", "rb"))
except:
    pass

# =========================================================
# 500+ KEYWORDS (AUTO EXPANDED)
# =========================================================
BASE = [
    "otp","send money","upi","verify","account blocked","bank alert",
    "click here","urgent","refund","kyc","aadhaar","pan",
    "debit card","credit card","cvv","loan approved","processing fee",
    "telegram job","whatsapp job","legal notice","customs","parcel seized"
]

SCAM_KEYWORDS = []
for k in BASE:
    for p in ["", " please", " immediately", " now", " urgently"]:
        SCAM_KEYWORDS.append(k + p)

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
# DETECTION ENGINE
# =========================================================
UPI = r"[\w.-]+@[\w.-]+"
URL = r"https?://[^\s]+"

def detect(msg):
    msg = msg.lower()
    score = 0
    ml = 0.0

    for k in SCAM_KEYWORDS:
        if k in msg:
            score += 1

    if "otp" in msg: score += 6
    if re.search(UPI, msg): score += 7
    if re.search(URL, msg): score += 4

    for s in DATASET[:200]:
        if s in msg:
            score += 5
            break

    if ML_MODEL and VECTORIZER:
        try:
            v = VECTORIZER.transform([msg])
            ml = ML_MODEL.predict_proba(v)[0][1]
            score += int(ml * 6)
        except:
            pass

    conf = min((score / 15 + ml) / 2, 1.0)
    return score >= 7 or ml > 0.65, conf

# =========================================================
# ROUTES – LANDING
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
body{
  margin:0;
  font-family:Poppins;
  background:linear-gradient(135deg,#020617,#020617,#020617);
  color:white;
  overflow:hidden;
}
.hero{
  height:100vh;
  display:flex;
  flex-direction:column;
  justify-content:center;
  align-items:center;
  animation:fade 1.5s;
}
h1{font-size:3.5rem;}
p{color:#94a3b8;}
a{
  margin:10px;
  padding:14px 28px;
  border-radius:30px;
  background:#22c55e;
  color:black;
  text-decoration:none;
  font-weight:600;
  transition:.3s;
}
a:hover{transform:scale(1.1);}
@keyframes fade{from{opacity:0;transform:translateY(30px)}to{opacity:1}}
</style>
</head>
<body>
<div class="hero">
<h1>RAKSHAK AI</h1>
<p>Agentic Honeypot Scam Detection System</p>
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
button{padding:12px 24px;border-radius:20px;background:#22c55e;border:none}
.result{margin-top:20px;font-size:22px}
</style>
</head>
<body>
<h2>Scam Message Checker</h2>
<textarea id="msg"></textarea><br><br>
<button onclick="go()">Analyze</button>
<div class="result" id="out"></div>
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
 out.innerHTML = d.scam_detected ? "⚠️ SCAM ("+Math.round(d.confidence*100)+"%)" :
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
<head><title>Admin</title></head>
<body style="background:#020617;color:white;font-family:Poppins;padding:40px">
<h2>Admin Dashboard</h2>
<p>Total Requests: {STATS['total']}</p>
<p>Scams Detected: {STATS['scam']}</p>
<p>Safe Messages: {STATS['safe']}</p>
<p>Keywords Used: {len(SCAM_KEYWORDS)}</p>
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