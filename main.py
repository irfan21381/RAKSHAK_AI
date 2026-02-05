from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import os, re, requests

# =========================================================
# APP CONFIG
# =========================================================
app = FastAPI(title="RAKSHAK AI – Agentic Scam Honeypot")
API_KEY = os.getenv("API_KEY", "rakshak-secret-key")
GUVI_CALLBACK = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

# =========================================================
# MEMORY + STATS
# =========================================================
SESSION_INTEL = {}
SESSION_CALLBACK_SENT = set()
STATS = {"total": 0, "scam": 0, "safe": 0}

# =========================================================
# PATTERNS
# =========================================================
UPI_REGEX = r"[\w.-]+@[\w.-]+"
URL_REGEX = r"https?://[^\s]+"
PHONE_REGEX = r"\+?\d{10,13}"

# =========================================================
# MODELS
# =========================================================
class Message(BaseModel):
    sender: str
    text: str
    timestamp: Optional[int] = None

class HackathonRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[Message] = []
    metadata: Optional[dict] = {}

class HoneypotRequest(BaseModel):
    message: str

class HoneypotResponse(BaseModel):
    scam_detected: bool
    confidence: float
    reply: str

# =========================================================
# 🔥 FINAL FIXED DETECTION LOGIC
# =========================================================
def detect(msg: str):
    msg = msg.lower().strip()
    score = 0

    # HARD SCAM SIGNALS
    if "otp" in msg: score += 6
    if "upi" in msg or "upi id" in msg: score += 6
    if "account blocked" in msg: score += 5
    if "verify" in msg: score += 4
    if "send money" in msg: score += 5
    if "urgent" in msg or "immediately" in msg or "today" in msg:
        score += 4

    # PHISHING LINK LOGIC (IMPORTANT FIX)
    if re.search(URL_REGEX, msg):
        score += 3
        if any(k in msg for k in ["verify", "bank", "account", "login", "click"]):
            score += 6

    # RAW PATTERNS
    if re.search(UPI_REGEX, msg): score += 6
    if re.search(PHONE_REGEX, msg): score += 2

    confidence = min(score / 12, 1.0)
    return score >= 5, confidence

# =========================================================
# INTELLIGENCE EXTRACTION
# =========================================================
def extract_intel(text: str):
    return {
        "bankAccounts": [],
        "upiIds": re.findall(UPI_REGEX, text),
        "phishingLinks": re.findall(URL_REGEX, text),
        "phoneNumbers": re.findall(PHONE_REGEX, text),
        "suspiciousKeywords": [
            k for k in [
                "otp","upi","verify","account blocked",
                "urgent","immediately","click","bank"
            ] if k in text.lower()
        ]
    }

def agent_reply():
    return "Why is my account being suspended?"

# =========================================================
# MAIN HACKATHON API (POST /)
# =========================================================
@app.post("/")
async def hackathon_api(req: HackathonRequest, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    STATS["total"] += 1
    session_id = req.sessionId
    scam, _ = detect(req.message.text)

    if session_id not in SESSION_INTEL:
        SESSION_INTEL[session_id] = extract_intel("")

    combined = req.message.text + " " + " ".join(m.text for m in req.conversationHistory)
    intel = extract_intel(combined)

    for k in intel:
        SESSION_INTEL[session_id][k] = list(set(SESSION_INTEL[session_id][k] + intel[k]))

    if scam:
        STATS["scam"] += 1

        if len(req.conversationHistory) >= 3 and session_id not in SESSION_CALLBACK_SENT:
            payload = {
                "sessionId": session_id,
                "scamDetected": True,
                "totalMessagesExchanged": len(req.conversationHistory) + 1,
                "extractedIntelligence": SESSION_INTEL[session_id],
                "agentNotes": "OTP + UPI + phishing + urgency scam detected"
            }
            try:
                requests.post(GUVI_CALLBACK, json=payload, timeout=5)
                SESSION_CALLBACK_SENT.add(session_id)
            except:
                pass

        return {"status": "success", "reply": agent_reply()}

    STATS["safe"] += 1
    return {"status": "success", "reply": "Okay, tell me more."}

# =========================================================
# HOME – OLD DARK UI RESTORED
# =========================================================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>RAKSHAK AI</title>
<style>
body{margin:0;font-family:Arial;background:#020617;color:white;text-align:center}
.hero{height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center}
h1{font-size:3.5rem}
a{margin:10px;padding:14px 28px;border-radius:30px;
background:#22c55e;color:black;text-decoration:none;font-weight:600}
a:hover{transform:scale(1.08)}
.footer{margin-top:30px;color:#94a3b8}
</style>
</head>
<body>
<div class="hero">
<h1>RAKSHAK AI</h1>
<p>Agentic Scam Detection Honeypot</p>
<a href="/user">User Portal</a>
<a href="/admin">Admin Dashboard</a>
<div class="footer">Developed by Irfan Yasin</div>
</div>
</body>
</html>
"""

# =========================================================
# USER UI (OLD STYLE)
# =========================================================
@app.get("/user", response_class=HTMLResponse)
def user():
    return """
<!DOCTYPE html>
<html>
<head>
<title>User | RAKSHAK AI</title>
<style>
body{background:#020617;color:white;font-family:Arial;padding:40px}
.container{max-width:600px;margin:auto}
textarea{width:100%;height:120px;border-radius:10px;padding:12px}
button{padding:12px 26px;border-radius:20px;background:#22c55e;border:none}
.result{margin-top:20px;font-size:1.5rem}
</style>
</head>
<body>
<div class="container">
<h2>Scam Message Checker</h2>
<textarea id="msg" placeholder="Paste suspicious message..."></textarea><br><br>
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
 out.innerHTML = d.scam_detected
 ? "🚨 SCAM ("+Math.round(d.confidence*100)+"%)"
 : "🟢 SAFE";
}
</script>
<br><a href="/">⬅ Back</a>
</div>
</body>
</html>
"""

# =========================================================
# ADMIN UI (LIVE STATS)
# =========================================================
@app.get("/admin", response_class=HTMLResponse)
def admin():
    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Admin | RAKSHAK AI</title>
<style>
body{{background:#020617;color:white;font-family:Arial;padding:40px}}
.card{{background:#111827;padding:20px;border-radius:12px;max-width:400px}}
</style>
</head>
<body>
<h2>Admin Dashboard</h2>
<div class="card">
<p>Total Requests: {STATS['total']}</p>
<p>Scams Detected: {STATS['scam']}</p>
<p>Safe Messages: {STATS['safe']}</p>
</div>
<br><p>Developed by Irfan Yasin</p>
<a href="/">⬅ Back</a>
</body>
</html>
"""

# =========================================================
# HONEYPOT API (CURL / UI)
# =========================================================
@app.post("/honeypot", response_model=HoneypotResponse)
def honeypot(data: HoneypotRequest, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    scam, conf = detect(data.message)
    return HoneypotResponse(
        scam_detected=scam,
        confidence=conf,
        reply="Please explain further" if scam else "Message looks safe"
    )
