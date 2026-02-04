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
# KEYWORDS & REGEX
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
    conversation_id: Optional[str] = None
    message: str

class HoneypotResponse(BaseModel):
    scam_detected: bool
    confidence: float
    reply: str

# =========================================================
# CORE DETECTION
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

    for k in SCAM_KEYWORDS:
        if k in msg:
            score += 1

    if ML_MODEL and VECTORIZER:
        try:
            vec = VECTORIZER.transform([msg])
            ml_conf = ML_MODEL.predict_proba(vec)[0][1]
            score += int(ml_conf * 5)
        except:
            pass

    confidence = min((score / 12 + ml_conf) / 2, 1.0)
    return score >= 5 or ml_conf > 0.7, confidence

# =========================================================
# INTEL EXTRACTION
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
    return "Why is my account being suspended?"

# =========================================================
# MAIN HACKATHON API
# =========================================================
@app.post("/")
async def hackathon_api(req: HackathonRequest, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    STATS["total"] += 1
    session_id = req.sessionId

    scam, conf = detect(req.message.text)

    if session_id not in SESSION_INTEL:
        SESSION_INTEL[session_id] = {
            "bankAccounts": [],
            "upiIds": [],
            "phishingLinks": [],
            "phoneNumbers": [],
            "suspiciousKeywords": []
        }

    all_text = req.message.text + " " + " ".join(
        [m.text for m in req.conversationHistory]
    )

    intel = extract_intel(all_text)
    for k in SESSION_INTEL[session_id]:
        SESSION_INTEL[session_id][k] = list(
            set(SESSION_INTEL[session_id][k] + intel[k])
        )

    if scam:
        STATS["scam"] += 1

        if (
            len(req.conversationHistory) >= 3 and
            session_id not in SESSION_CALLBACK_SENT
        ):
            payload = {
                "sessionId": session_id,
                "scamDetected": True,
                "totalMessagesExchanged": len(req.conversationHistory) + 1,
                "extractedIntelligence": SESSION_INTEL[session_id],
                "agentNotes": "Urgency + financial redirection detected"
            }
            try:
                requests.post(GUVI_CALLBACK, json=payload, timeout=5)
                SESSION_CALLBACK_SENT.add(session_id)
            except:
                pass

        return {
            "status": "success",
            "reply": agent_reply()
        }

    STATS["safe"] += 1
    return {
        "status": "success",
        "reply": "Hello, how can I help you?"
    }

# =========================================================
# OLD UI (SAME ROUTES, JUST BEAUTIFIED)
# =========================================================
@app.get("/", response_class=HTMLResponse)
def landing():
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
a:hover{transform:scale(1.1)}
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
 out.innerHTML = d.scam_detected ?
 "⚠️ SCAM ("+Math.round(d.confidence*100)+"%)" :
 "✅ SAFE ("+Math.round(d.confidence*100)+"%)";
}
</script>
<br><a href="/">⬅ Back</a>
</div>
</body>
</html>
"""

@app.get("/admin", response_class=HTMLResponse)
def admin():
    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Admin | RAKSHAK AI</title>
<style>
body{background:#020617;color:white;font-family:Arial;padding:40px}
.card{background:#111827;padding:20px;border-radius:12px;max-width:400px}
</style>
</head>
<body>
<h2>Admin Dashboard</h2>
<div class="card">
<p>Total Requests: {STATS['total']}</p>
<p>Scams Detected: {STATS['scam']}</p>
<p>Safe Messages: {STATS['safe']}</p>
</div>
<br><a href="/">⬅ Back</a>
</body>
</html>
"""

# =========================================================
# ORIGINAL HONEYPOT API
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