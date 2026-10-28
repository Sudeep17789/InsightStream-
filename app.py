from flask import Flask, render_template, request, jsonify
from urllib.parse import urlparse
import re
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

# Models are loaded only when the user runs an analysis. First use may download
# model files from Hugging Face and can take several minutes.
_models = {}

def get_pipeline(task, model_name):
    key = (task, model_name)
    if key not in _models:
        from transformers import pipeline
        _models[key] = pipeline(task, model=model_name)
    return _models[key]

def clean_text(text):
    return re.sub(r"\s+", " ", (text or "")).strip()

def fetch_article(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid public article URL beginning with http:// or https://.")
    # Basic guard against accidentally fetching local/private hostnames.
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local"):
        raise ValueError("Local network URLs are not supported.")
    response = requests.get(url, timeout=12, headers={"User-Agent": "InsightStream/1.0 (educational project)"})
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", "").lower():
        raise ValueError("That URL did not return an HTML article page.")
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()
    candidates = soup.find_all(["article", "main"])
    content = " ".join(node.get_text(" ", strip=True) for node in candidates)
    if len(content) < 200:
        paragraphs = soup.find_all("p")
        content = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
    content = clean_text(content)
    if len(content) < 80:
        raise ValueError("Could not extract enough article text. Paste the article text instead.")
    return content[:18000]

def extractive_summary(text, max_sentences=4):
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 25]
    if not sentences:
        return text[:600]
    # Lightweight fallback: pick the first few meaningful sentences.
    return " ".join(sentences[:max_sentences])

def summarize(text):
    try:
        summarizer = get_pipeline("summarization", "facebook/bart-large-cnn")
        result = summarizer(text[:5000], max_length=130, min_length=30, do_sample=False, truncation=True)
        return result[0]["summary_text"], "AI model: facebook/bart-large-cnn (English-focused)"
    except Exception:
        return extractive_summary(text), "Fallback: extractive summary (transformer model unavailable or not yet downloaded)"

def sentiment(text):
    try:
        classifier = get_pipeline("text-classification", "cardiffnlp/twitter-xlm-roberta-base-sentiment")
        result = classifier(text[:1800], truncation=True)
        item = result[0]
        label = item["label"].upper()
        mapping = {"LABEL_0": "NEGATIVE", "LABEL_1": "NEUTRAL", "LABEL_2": "POSITIVE"}
        label = mapping.get(label, label)
        return label, float(item["score"]), "AI model: multilingual XLM-R sentiment"
    except Exception:
        positive = {"good", "great", "success", "improve", "growth", "positive", "benefit", "win", "hope", "progress", "safe"}
        negative = {"bad", "crisis", "fail", "loss", "negative", "danger", "risk", "attack", "war", "death", "problem", "concern"}
        words = re.findall(r"[a-zA-Z]+", text.lower())
        pos = sum(w in positive for w in words)
        neg = sum(w in negative for w in words)
        label = "POSITIVE" if pos > neg else "NEGATIVE" if neg > pos else "NEUTRAL"
        score = max(pos, neg) / max(len(words), 1)
        return label, min(score * 8, 0.99), "Fallback: simple keyword estimate (not an AI model)"

def keywords(text, limit=8):
    stop = set("""the a an and or but if of to in on for from by with as at is are was were be been being it this that these those we they he she you i not have has had will would can could should about into over after before than then their our your its""".split())
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower())
    counts = {}
    for word in words:
        if word not in stop:
            counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]]

def group_articles(texts, threshold=0.58):
    """Group submitted articles by multilingual sentence embeddings when available.
    A simple keyword overlap fallback keeps the feature usable without downloads.
    """
    if not texts:
        return []
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        model = _models.get(("embedding_model", "multilingual"))
        if model is None:
            model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            _models[("embedding_model", "multilingual")] = model
        embeddings = model.encode(texts)
        sim = cosine_similarity(embeddings)
        groups = []
        assigned = set()
        for i, text in enumerate(texts):
            if i in assigned:
                continue
            group = [i]
            assigned.add(i)
            for j in range(i + 1, len(texts)):
                if j not in assigned and sim[i][j] >= threshold:
                    group.append(j)
                    assigned.add(j)
            groups.append(group)
        return groups
    except Exception:
        token_sets = [set(keywords(t, 30)) for t in texts]
        groups, assigned = [], set()
        for i in range(len(texts)):
            if i in assigned:
                continue
            group = [i]
            assigned.add(i)
            for j in range(i + 1, len(texts)):
                if j not in assigned:
                    union = token_sets[i] | token_sets[j]
                    overlap = len(token_sets[i] & token_sets[j]) / max(len(union), 1)
                    if overlap >= 0.15:
                        group.append(j)
                        assigned.add(j)
            groups.append(group)
        return groups

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    if request.method == "POST":
        text = clean_text(request.form.get("article_text", ""))
        url = request.form.get("article_url", "").strip()
        if url:
            try:
                text = fetch_article(url)
            except Exception as exc:
                error = f"Could not read URL: {exc}"
        if not error:
            if len(text) < 80:
                error = "Paste at least a few paragraphs (80 characters or more), or provide a readable article URL."
            else:
                summary, summary_method = summarize(text)
                label, score, sentiment_method = sentiment(text)
                result = {
                    "summary": summary,
                    "sentiment": label,
                    "sentiment_score": round(score * 100),
                    "summary_method": summary_method,
                    "sentiment_method": sentiment_method,
                    "word_count": len(text.split()),
                    "keywords": keywords(text),
                    "preview": text[:500] + ("…" if len(text) > 500 else "")
                }
    return render_template("index.html", result=result, error=error)

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}
    text = clean_text(data.get("text", ""))
    if len(text) < 80:
        return jsonify({"error": "Text must contain at least 80 characters."}), 400
    summary, summary_method = summarize(text)
    label, score, sentiment_method = sentiment(text)
    return jsonify({
        "summary": summary,
        "sentiment": label,
        "sentiment_score": round(score * 100),
        "keywords": keywords(text),
        "summary_method": summary_method,
        "sentiment_method": sentiment_method
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "InsightStream"})

if __name__ == "__main__":
    app.run(debug=True)
