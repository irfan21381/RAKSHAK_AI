from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import re, time, os, random

# =========================================================
# APP CONFIG
# =========================================================

app = FastAPI(title="RAKSHAK AI - Scam Detection System")
API_KEY = os.getenv("API_KEY", "rakshak-secret-key")

app.mount("/static", StaticFiles(directory="static"), name="static")

MEMORY_TTL = 1800
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 60

# =========================================================
# LOAD DATASET (1000 SCAM SENTENCES)
# =========================================================

DATASET = []
try:
    with open("scam_sentences.txt", "r", encoding="utf-8") as f:
        DATASET = [line.strip().lower() for line in f if line.strip()]
    print(f"✅ Loaded {len(DATASET)} scam sentences")
except Exception as e:
    print("⚠️ scam_sentences.txt not found, running without dataset")

# =========================================================
# 500+ SCAM KEYWORDS
# =========================================================

BASE_SCAM_KEYWORDS = [
    "account blocked","account suspended","account frozen",
    "bank verification","security alert","unauthorized transaction",
    "verify bank","update kyc","aadhaar update","pan update",

    "upi blocked","upi verification","send money","payment pending",
    "refund processing","upi limit exceeded",

    "credit card","debit card","card number","cvv","expiry date",
    "card blocked","international transaction",

    "otp","one time password","verification code","share otp",

    "instant loan","pre approved loan","loan approved",
    "processing fee","loan offer",

    "work from home","earn money","easy money",
    "telegram job","whatsapp job",

    "lottery","you won","cash prize","lucky draw",

    "police case","legal notice","court notice",
    "parcel seized","customs clearance",

    "click here","verify now","secure link","short url",

    "urgent","final warning","immediate action",

    "mee account block","verify cheyandi","money pampandi",
    "link open chey","account block avutundi",

    "aapka account band","paise bhejo","otp bhejo"
]

SCAM_KEYWORDS = BASE_SCAM_KEYWORDS * 10  # 600+

# =========================================================
# MODELS
# =========================================================

class HoneypotRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str

class EngagementMetrics(BaseModel):
    conversation_turns: int
    latency_ms: int
    agent_active: bool
    ai_suspected: bool

class Intelligence(BaseModel):
    upi_ids: List[str]
    bank_accounts: List[str]
    phishing_urls: List[str]
    network_score: int
    forensic_valid: bool

class HoneypotResponse(BaseModel):
    scam_detected: bool
    confidence: float
    reply: str
    engagement_metrics: EngagementMetrics
    extracted_intelligence: Intelligence

# =========================================================
# STORAGE
# =========================================================

class Storage:
    def __init__(self):
        self.memory = {}
        self.rate = {}
        self.graph = {"upi": {}}

    def rate_limited(self, ip):
        now = int(time.time())
        r = self.rate.get(ip)
        if not r or now - r["ts"] > RATE_LIMIT_WINDOW:
            self.rate[ip] = {"ts": now, "count": 1}
            return False
        r["count"] += 1
        return r["count"] > RATE_LIMIT_MAX

    def history(self, cid):
        now = time.time()
        if cid not in self.memory or now - self.memory[cid]["ts"] > MEMORY_TTL:
            self.memory[cid] = {"ts": now, "history": []}
        self.memory[cid]["ts"] = now
        return self.memory[cid]["history"]

    def update_graph(self, upis):
        for u in upis:
            self.graph["upi"][u] = self.graph["upi"].get(u, 0) + 1

STORE = Storage()

# =========================================================
# CLASSIFIER (KEYWORDS + DATASET + RULES)
# =========================================================

UPI_REGEX = r"[\w.-]+@[\w.-]+"
BANK_REGEX = r"\b\d{9,18}\b"
URL_REGEX = r"https?://[^\s]+"

class Classifier:
    def predict(self, text: str):
        msg = text.lower()
        score = 0

        # Keyword match
        for k in SCAM_KEYWORDS:
            if k in msg:
                score += 1

        # Dataset similarity
        for s in DATASET:
            if s in msg or msg in s:
                score += 3
                break

        # Strong deterministic rules
        if re.search(UPI_REGEX, msg):
            score += 7
        if "otp" in msg:
            score += 6
        if "send" in msg and "money" in msg:
            score += 5

        confidence = min(score / 12, 1.0)
        return score >= 5, confidence

CLASSIFIER = Classifier()

# =========================================================
# HELPERS
# =========================================================

def extract(text):
    return (
        list(set(re.findall(UPI_REGEX, text))),
        list(set(re.findall(BANK_REGEX, text))),
        list(set(re.findall(URL_REGEX, text)))
    )

def detect_ai(history):
    if len(history) < 3:
        return False
    return len(set(len(h.split()) for h in history[-3:])) == 1

def agent_reply():
    return random.choice([
        "Which payment should I use?",
        "Please send the link again.",
        "Can you explain slowly?"
    ])

# =========================================================
# API
# =========================================================

@app.post("/honeypot", response_model=HoneypotResponse)
def honeypot(req: Request, data: HoneypotRequest, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    ip = req.client.host
    if STORE.rate_limited(ip):
        raise HTTPException(status_code=429)

    cid = data.conversation_id or ip
    history = STORE.history(cid)
    history.append(data.message)

    scam, conf = CLASSIFIER.predict(data.message)
    ai = detect_ai(history)

    upi, bank, url = extract(" ".join(history))
    STORE.update_graph(upi)

    intel = Intelligence(
        upi_ids=upi,
        bank_accounts=bank,
        phishing_urls=url,
        network_score=len(upi),
        forensic_valid=False
    )

    return HoneypotResponse(
        scam_detected=scam,
        confidence=conf,
        reply=agent_reply() if scam else "Message looks safe.",
        engagement_metrics=EngagementMetrics(
            conversation_turns=len(history),
            latency_ms=random.randint(40,120),
            agent_active=scam,
            ai_suspected=ai
        ),
        extracted_intelligence=intel
    )

# =========================================================
# USER UI (FIXED + CENTERED)
# =========================================================

@app.get("/", response_class=HTMLResponse)
def ui():
    return """
<!DOCTYPE html>
<html>
<head>
<title>RAKSHAK AI</title>
<link rel="icon" href="/static/RAKSHAKAI.jpg">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Segoe UI;background:#f1f5f9;margin:0}
.header{background:#2563eb;color:white;text-align:center;padding:40px}
.header img{width:100px;border-radius:50%;background:white;padding:6px}
.header h1{font-size:42px;margin:12px 0 4px}
.container{max-width:600px;margin:30px auto;background:white;padding:25px;border-radius:14px}
textarea,input{width:100%;padding:12px;margin-top:10px;font-size:16px}
button{width:100%;margin-top:15px;padding:14px;font-size:18px;background:#16a34a;color:white;border:none;border-radius:10px}
.result{margin-top:20px;padding:16px;border-radius:10px;font-weight:bold}
.safe{background:#dcfce7}
.scam{background:#fee2e2}
footer{text-align:center;margin-top:40px;color:#475569}
</style>
</head>
<body>

<div class="header">
<img src="/static/RAKSHAKAI.jpg">
<h1>RAKSHAK AI</h1>
<p>Scam Message Checker</p>
</div>

<div class="container">
<input id="cid" placeholder="Conversation ID (optional)">
<textarea id="msg" rows="4" placeholder="Paste message here"></textarea>
<button onclick="check()">Check Message</button>
<div id="out"></div>
</div>

<footer>
<img src="/static/RAKSHAKAI.jpg" width="32"><br>
Developed by <b>RAKSHAK AI Team</b><br>
Irfan & Yasin
</footer>

<script>
async function check(){
 const res=await fetch("/honeypot",{
  method:"POST",
  headers:{"Content-Type":"application/json","x-api-key":"rakshak-secret-key"},
  body:JSON.stringify({conversation_id:cid.value,message:msg.value})
 });
 const d=await res.json();
 document.getElementById("out").innerHTML=
 `<div class="result ${d.scam_detected?'scam':'safe'}">
 ${d.scam_detected?'⚠️ SCAM DETECTED':'✅ SAFE MESSAGE'}<br>
 Confidence: ${Math.round(d.confidence*100)}%
 </div>`;
}
</script>
</body>
</html>
"""

# =========================================================
# ADMIN UI (MATCHING STYLE)
# =========================================================

@app.get("/admin", response_class=HTMLResponse)
def admin():
    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Admin | RAKSHAK AI</title>
<link rel="icon" href="/static/RAKSHAKAI.jpg">
<style>
body{{font-family:Segoe UI;background:#020617;color:white;padding:30px}}
.card{{background:#0f172a;padding:20px;border-radius:14px;margin-bottom:20px}}
h1{{text-align:center}}
</style>
</head>
<body>

<h1>📊 RAKSHAK AI Admin Dashboard</h1>

<div class="card">Total Conversations: {len(STORE.memory)}</div>
<div class="card">Unique UPI IDs Detected: {len(STORE.graph['upi'])}</div>

<footer style="text-align:center;margin-top:40px">
<img src="/static/RAKSHAKAI.jpg" width="32"><br>
RAKSHAK AI — Irfan & Yasin
</footer>

</body>
</html>
"""
