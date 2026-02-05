from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import os, re, pickle, requests

# =========================================================
# APP CONFIG
# =========================================================
app = FastAPI(title="RAKSHAK AI – Agentic Scam Honeypot")
API_KEY = os.getenv("API_KEY", "rakshak-secret-key")
GUVI_CALLBACK = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

# =========================================================
# MEMORY (MULTI-TURN)
# =========================================================
SESSION_INTEL = {}
SESSION_CALLBACK_SENT = set()

# =========================================================
# KEYWORDS & REGEX
# =========================================================
BASE_KEYWORDS = [
    "otp","send money","verify","account blocked","account suspended",
    "bank alert","upi","refund","kyc","aadhaar","pan",
    "credit card","debit card","cvv","loan","processing fee",
    "telegram job","whatsapp job","urgent","click here"
]

UPI_REGEX = r"[\w.-]+@[\w.-]+"
URL_REGEX = r"https?://[^\s]+"
PHONE_REGEX = r"\+?\d{10,13}"

STATS = {"total":0, "scam":0, "safe":0}

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
# DETECTION LOGIC (FIXED FALSE POSITIVE)
# =========================================================
def detect(msg: str):
    msg = msg.lower().strip()
    score = 0

    for k in BASE_KEYWORDS:
        if k in msg:
            score += 1

    if re.search(UPI_REGEX, msg): score += 3
    if re.search(URL_REGEX, msg): score += 2
    if "otp" in msg: score += 4

    confidence = min(score / 8, 1.0)
    scam = score >= 4

    return scam, confidence

# =========================================================
# INTELLIGENCE EXTRACTION
# =========================================================
def extract_intel(text: str):
    return {
        "bankAccounts": [],
        "upiIds": re.findall(UPI_REGEX, text),
        "phishingLinks": re.findall(URL_REGEX, text),
        "phoneNumbers": re.findall(PHONE_REGEX, text),
        "suspiciousKeywords": [k for k in BASE_KEYWORDS if k in text.lower()]
    }

# =========================================================
# AGENT REPLY
# =========================================================
def agent_reply():
    return "Sir/Madam, why is my account being suspended?"

# =========================================================
# GET / → GOVT HOME PAGE
# =========================================================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>RAKSHAK AI | Government of India</title>
<style>
body{margin:0;font-family:Verdana;background:#f8fafc}
header{background:#0f172a;color:white;padding:20px}
nav a{color:white;margin:0 15px;text-decoration:none;font-weight:bold}
.main{padding:50px;text-align:center}
.card{background:white;padding:30px;border-radius:10px;
max-width:700px;margin:auto;box-shadow:0 0 10px #ccc}
footer{background:#0f172a;color:white;text-align:center;padding:10px;margin-top:40px}
button{padding:12px 30px;background:#1d4ed8;color:white;border:none;border-radius:6px}
</style>
</head>
<body>
<header>
<h2>RAKSHAK AI – National Cyber Safety Initiative</h2>
<nav>
<a href="/user">Citizen Portal</a>
<a href="/admin">Admin Dashboard</a>
</nav>
</header>

<div class="main">
<div class="card">
<h1>Agentic Scam Detection System</h1>
<p>Official AI Honeypot System to Detect and Engage Online Scams</p>
<a href="/user"><button>Check Message</button></a>
</div>
</div>

<footer>
© Government of India | Cyber Safety Division
</footer>
</body>
</html>
"""

# =========================================================
# POST / → HACKATHON API
# =========================================================
@app.post("/")
async def hackathon_api(req: HackathonRequest, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    STATS["total"] += 1
    scam, conf = detect(req.message.text)

    session_id = req.sessionId
    if session_id not in SESSION_INTEL:
        SESSION_INTEL[session_id] = extract_intel(req.message.text)

    if scam:
        STATS["scam"] += 1

        if len(req.conversationHistory) >= 2 and session_id not in SESSION_CALLBACK_SENT:
            payload = {
                "sessionId": session_id,
                "scamDetected": True,
                "totalMessagesExchanged": len(req.conversationHistory) + 1,
                "extractedIntelligence": SESSION_INTEL[session_id],
                "agentNotes": "Urgency and credential harvesting detected"
            }
            try:
                requests.post(GUVI_CALLBACK, json=payload, timeout=5)
                SESSION_CALLBACK_SENT.add(session_id)
            except:
                pass

        return {"status":"success","reply":agent_reply()}

    STATS["safe"] += 1
    return {"status":"success","reply":"Hello, how may I assist you?"}

# =========================================================
# USER PORTAL
# =========================================================
@app.get("/user", response_class=HTMLResponse)
def user():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Citizen Portal | RAKSHAK AI</title>
<style>
body{font-family:Verdana;background:#eef2ff;padding:40px}
.box{background:white;padding:30px;border-radius:10px;max-width:600px;margin:auto}
textarea{width:100%;height:120px}
button{padding:10px 25px;background:#1d4ed8;color:white;border:none;border-radius:6px}
#out{margin-top:20px;font-size:18px}
</style>
</head>
<body>
<div class="box">
<h2>Scam Message Verification</h2>
<textarea id="msg"></textarea><br><br>
<button onclick="go()">Analyze</button>
<div id="out"></div>
<script>
async function go(){
 const r = await fetch("/honeypot",{
  method:"POST",
  headers:{"Content-Type":"application/json","x-api-key":"rakshak-secret-key"},
  body:JSON.stringify({message:msg.value})
 });
 const d = await r.json();
 out.innerHTML = d.scam_detected ?
 "🚨 <b>SCAM DETECTED</b> ("+Math.round(d.confidence*100)+"%)" :
 "🟢 SAFE MESSAGE";
}
</script>
</div>
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
<head>
<title>Admin | RAKSHAK AI</title>
<style>
body{{font-family:Verdana;background:#f1f5f9;padding:40px}}
.card{{background:white;padding:25px;border-radius:10px;max-width:400px}}
</style>
</head>
<body>
<h2>System Statistics</h2>
<div class="card">
<p>Total Requests: {STATS['total']}</p>
<p>Scams Detected: {STATS['scam']}</p>
<p>Safe Messages: {STATS['safe']}</p>
</div>
</body>
</html>
"""

# =========================================================
# HONEYPOT API (UI)
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