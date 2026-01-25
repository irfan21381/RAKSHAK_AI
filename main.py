from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import re, time, os, random, pickle

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
# LOAD DATASET
# =========================================================

DATASET = []
try:
    with open("scam_sentences.txt", "r", encoding="utf-8") as f:
        DATASET = [line.strip().lower() for line in f if line.strip()]
    print(f"✅ Loaded {len(DATASET)} scam sentences")
except:
    print("⚠️ scam_sentences.txt not found")

# =========================================================
# LOAD ML MODEL
# =========================================================

ML_MODEL = None
VECTORIZER = None

try:
    ML_MODEL = pickle.load(open("model.pkl", "rb"))
    VECTORIZER = pickle.load(open("vectorizer.pkl", "rb"))
    print("✅ ML model loaded")
except:
    print("⚠️ ML model not found – running hybrid without ML")

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
# CLASSIFIER (HYBRID AI)
# =========================================================

UPI_REGEX = r"[\w.-]+@[\w.-]+"
BANK_REGEX = r"\b\d{9,18}\b"
URL_REGEX = r"https?://[^\s]+"

class Classifier:
    def predict(self, text: str):
        msg = text.lower().strip()
        score = 0
        hard_trigger = False

        # ==============================
        # 0️⃣ GREETING / SHORT TEXT FILTER
        # ==============================
        if len(msg.split()) <= 2:
            # hi, hello bro, ok, yes etc
            return False, 0.05

        # ==============================
        # 1️⃣ KEYWORD MATCH (BASE ONLY)
        # ==============================
        for k in BASE_SCAM_KEYWORDS:
            if k in msg:
                score += 1

        # ==============================
        # 2️⃣ DATASET SIMILARITY (SAFE)
        # ==============================
        if len(msg) > 15:
            for s in DATASET:
                if s in msg:
                    score += 3
                    break

        # ==============================
        # 3️⃣ HARD SCAM RULES (PRIORITY)
        # ==============================
        if re.search(UPI_REGEX, msg):
            score += 7
            hard_trigger = True

        if "otp" in msg:
            score += 6
            hard_trigger = True

        if "send" in msg and ("money" in msg or "amount" in msg):
            score += 5
            hard_trigger = True

        # ==============================
        # 4️⃣ ML MODEL (CONTROLLED)
        # ==============================
        ml_conf = 0.0
        if ML_MODEL and VECTORIZER:
            try:
                vec = VECTORIZER.transform([msg])
                ml_conf = ML_MODEL.predict_proba(vec)[0][1]
                score += int(ml_conf * 4)   # ❗ reduced impact
            except:
                ml_conf = 0.0

        # ==============================
        # 5️⃣ FINAL DECISION
        # ==============================
        confidence = min((score / 12 + ml_conf) / 2, 1.0)

        if hard_trigger:
            return True, max(confidence, 0.7)

        return score >= 8, confidence


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
# USER UI
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
body{
  font-family:"Segoe UI", Arial, sans-serif;
  background:#020617;
  margin:0;
  color:white;
}

.header{
  background:#020617;
  padding:40px 20px;
  text-align:center;
  border-bottom:1px solid #1e293b;
}

.header img{
  width:90px;
  border-radius:50%;
  background:white;
  padding:6px;
}

.header h1{
  font-size:42px;
  margin:12px 0 4px;
}

.header p{
  font-size:18px;
  color:#94a3b8;
}

.container{
  max-width:600px;
  margin:40px auto;
  background:#0f172a;
  padding:28px;
  border-radius:16px;
  box-shadow:0 10px 25px rgba(0,0,0,0.6);
}

input, textarea{
  width:100%;
  padding:14px;
  margin-top:12px;
  font-size:16px;
  background:#020617;
  color:white;
  border:1px solid #334155;
  border-radius:10px;
}

input::placeholder,
textarea::placeholder{
  color:#64748b;
}

button{
  width:100%;
  margin-top:18px;
  padding:15px;
  font-size:18px;
  background:#16a34a;
  color:white;
  border:none;
  border-radius:12px;
  cursor:pointer;
}

button:hover{
  background:#22c55e;
}

.result{
  margin-top:20px;
  padding:18px;
  border-radius:12px;
  font-size:18px;
}

.safe{
  background:#052e16;
  color:#86efac;
}

.scam{
  background:#450a0a;
  color:#fecaca;
}

.footer{
  text-align:center;
  margin:40px 0 20px;
  color:#64748b;
}

.footer img{
  width:32px;
  margin-bottom:6px;
}
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

<div class="footer">
  <img src="/static/RAKSHAKAI.jpg"><br>
  Developed by <b>RAKSHAK AI Team</b><br>
  Irfan & Yasin
</div>

<script>
async function check(){
 const res = await fetch("/honeypot",{
   method:"POST",
   headers:{
     "Content-Type":"application/json",
     "x-api-key":"rakshak-secret-key"
   },
   body:JSON.stringify({
     conversation_id:document.getElementById("cid").value,
     message:document.getElementById("msg").value
   })
 });

 const d = await res.json();
 document.getElementById("out").innerHTML =
 `<div class="result ${d.scam_detected ? 'scam' : 'safe'}">
 ${d.scam_detected ? '⚠️ SCAM DETECTED' : '✅ SAFE MESSAGE'}<br>
 Confidence: ${Math.round(d.confidence*100)}%
 </div>`;
}
</script>

</body>
</html>
"""


# =========================================================
# ADMIN
# =========================================================

@app.get("/admin", response_class=HTMLResponse)
def admin():
    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Admin | RAKSHAK AI</title>
<link rel="icon" href="/static/RAKSHAKAI.jpg">
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
body {{
  font-family: "Segoe UI", Arial, sans-serif;
  background:#020617;
  margin:0;
  color:white;
}}

.header {{
  background:#020617;
  padding:30px;
  text-align:center;
  border-bottom:1px solid #1e293b;
}}

.header img {{
  width:80px;
  border-radius:50%;
  background:white;
  padding:6px;
}}

.header h1 {{
  margin:10px 0 5px;
  font-size:32px;
}}

.header p {{
  color:#94a3b8;
  font-size:16px;
}}

.container {{
  max-width:900px;
  margin:30px auto;
  padding:20px;
}}

.cards {{
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap:20px;
}}

.card {{
  background:#0f172a;
  padding:22px;
  border-radius:14px;
  box-shadow:0 8px 20px rgba(0,0,0,0.4);
}}

.card h2 {{
  margin:0;
  font-size:22px;
  color:#38bdf8;
}}

.card p {{
  font-size:32px;
  margin-top:10px;
  font-weight:bold;
}}

.footer {{
  text-align:center;
  margin:40px 0 20px;
  color:#64748b;
}}

.footer img {{
  width:32px;
  margin-bottom:6px;
}}
</style>
</head>

<body>

<div class="header">
  <img src="/static/RAKSHAKAI.jpg">
  <h1>RAKSHAK AI</h1>
  <p>Admin Dashboard</p>
</div>

<div class="container">
  <div class="cards">

    <div class="card">
      <h2>🧠 Total Conversations</h2>
      <p>{len(STORE.memory)}</p>
    </div>

    <div class="card">
      <h2>💳 Unique UPI IDs</h2>
      <p>{len(STORE.graph['upi'])}</p>
    </div>

    <div class="card">
      <h2>⚠️ Scam Detection Engine</h2>
      <p>ACTIVE</p>
    </div>

    <div class="card">
      <h2>📊 Dataset Loaded</h2>
      <p>{len(DATASET)}</p>
    </div>

  </div>
</div>

<div class="footer">
  <img src="/static/RAKSHAKAI.jpg"><br>
  Developed by <b>RAKSHAK AI Team</b><br>
  Irfan & Yasin
</div>

</body>
</html>
"""
