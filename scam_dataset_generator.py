import random

TEMPLATES = [
    "Your {entity} is {status}. Please {action}.",
    "Dear customer, your {entity} has been {status}. {action} immediately.",
    "We noticed suspicious activity in your {entity}. {action}.",
    "Congratulations! You have won a {reward}. {action}.",
    "Your {entity} will be blocked today. {action}.",
    "Police case registered regarding your {entity}. {action}.",
    "Your refund of ₹{amount} is pending. {action}.",
    "Work from home job available. Earn ₹{amount} daily. {action}.",
]

ENTITIES = [
    "bank account","UPI account","credit card","debit card",
    "mobile number","PAN card","Aadhaar","loan account"
]

STATUS = [
    "blocked","suspended","on hold","under verification",
    "flagged","disabled"
]

ACTIONS = [
    "click the link","verify now","share OTP",
    "send money","update KYC","confirm details",
    "call this number","reply immediately"
]

REWARDS = [
    "lottery prize","cash reward","bonus amount",
    "lucky draw prize"
]

def generate_sentences(n=1000):
    sentences = []
    for _ in range(n):
        s = random.choice(TEMPLATES).format(
            entity=random.choice(ENTITIES),
            status=random.choice(STATUS),
            action=random.choice(ACTIONS),
            reward=random.choice(REWARDS),
            amount=random.randint(500, 50000)
        )
        sentences.append(s)
    return sentences


if __name__ == "__main__":
    data = generate_sentences(1000)
    with open("scam_sentences.txt", "w", encoding="utf-8") as f:
        for i, s in enumerate(data, 1):
            f.write(f"{i}. {s}\n")

    print("✅ Generated 1000 scam sentences")
