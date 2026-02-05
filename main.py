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
# MEMORY
# =========================================================
SESSION_INTEL = {}
SESSION_CALLBACK_SENT = set()
STATS = {"total": 0, "scam": 0, "safe": 0}

# =========================================================
# KEYWORDS & REGEX
# =========================================================
BASE_KEYWORDS = [
    "otp","send money","verify","account blocked",
    "upi id","upi","refund","kyc","urgent",
    "immediately","bank alert","security alert"
]

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
# 🔥 FIXED DETECTION LOGIC
# =========================================================
def detect(msg: str):
    msg = msg.lower().strip()
    score = 0

    # HARD SCAM TRIGGERS
    if "otp" in msg:
        score += 5
    if "upi id" in msg or "upi" in msg:
        score += 5
    if "account blocked" in msg:
        score += 4
    if "send money" in msg:
        score += 4
    if "immediately" in msg or "urgent" in msg:
        score += 3

    # LINKS / IDS
    if re.search(UPI_REGEX, msg):
        score += 5
    if re.search(URL_REGEX, msg):
        score += 3

    # KEYWORD BOOST
    for k in BASE_KEYWORDS:
        if k in msg:
            score += 1

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
        "suspiciousKeywords": [k for k in BASE_KEYWORDS if k in text.lower()]
    }

# =========================================================
# AGENT REPLY
# =========================================================
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

    scam, conf = detect(req.message.text)

    if session_id not in SESSION_INTEL:
        SESSION_INTEL[session_id] = extract_intel("")

    combined_text = req.message.text + " " + " ".join(
        [m.text for m in req.conversationHistory]
    )

    intel = extract_intel(combined_text)
    for k in intel:
        SESSION_INTEL[session_id][k] = list(
            set(SESSION_INTEL[session_id][k] + intel[k])
        )

    if scam:
        STATS["scam"] += 1

        if len(req.conversationHistory) >= 3 and session_id not in SESSION_CALLBACK_SENT:
            payload = {
                "sessionId": session_id,
                "scamDetected": True,
                "totalMessagesExchanged": len(req.conversationHistory) + 1,
                "extractedIntelligence": SESSION_INTEL[session_id],
                "agentNotes": "UPI + urgency based financial scam detected"
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
# HOME PAGE
# =========================================================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>RAKSHAK AI</h1>
    <p>Agentic Scam Detection Honeypot</p>
    <a href="/user">User Portal</a> |
    <a href="/admin">Admin Dashboard</a>
    <p>Developed by Irfan Yasin</p>
    """

# =========================================================
# USER UI
# =========================================================
@app.get("/user", response_class=HTMLResponse)
def user():
    return """
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
      out.innerHTML = d.scam_detected
        ? "🚨 SCAM ("+Math.round(d.confidence*100)+"%)"
        : "🟢 SAFE";
    }
    </script>
    """

# =========================================================
# ADMIN UI
# =========================================================
@app.get("/admin", response_class=HTMLResponse)
def admin():
    return f"""
    <h2>Admin Dashboard</h2>
    <p>Total Requests: {STATS['total']}</p>
    <p>Scams Detected: {STATS['scam']}</p>
    <p>Safe Messages: {STATS['safe']}</p>
    <p>Developed by Irfan Yasin</p>
    """

# =========================================================
# HONEYPOT API (FOR CURL / UI)
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
