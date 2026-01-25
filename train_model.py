import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# Load dataset
with open("scam_sentences.txt", "r", encoding="utf-8") as f:
    scam_texts = [line.strip().lower() for line in f if line.strip()]

# Create labels (1 = scam)
X = scam_texts
y = [1] * len(X)

# Add some SAFE examples
safe_samples = [
    "hello how are you",
    "meeting at 5 pm",
    "happy birthday",
    "let us study together",
    "see you tomorrow"
]

X.extend(safe_samples)
y.extend([0] * len(safe_samples))

# Vectorizer
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1,2)
)
X_vec = vectorizer.fit_transform(X)

# Model
model = LogisticRegression()
model.fit(X_vec, y)

# Save
pickle.dump(model, open("model.pkl", "wb"))
pickle.dump(vectorizer, open("vectorizer.pkl", "wb"))

print("✅ ML model trained and saved")
