# InsightStream — Multilingual News Summarizer & Sentiment Analyzer

InsightStream is an educational NLP portfolio project that summarizes article text, estimates sentiment, extracts frequent keywords, and includes a semantic article-grouping function.

## Features
- Paste article text or try to extract text from a public article URL
- Transformer-based article summarization (English-focused model)
- Multilingual sentiment classification
- Keyword extraction
- JSON REST endpoint at `POST /api/analyze`
- Semantic article grouping helper using multilingual sentence embeddings, with a lightweight fallback
- Responsive Flask web interface

## Tech stack
Python, Flask, Hugging Face Transformers, PyTorch, Sentence Transformers, scikit-learn, HTML, CSS, JavaScript.

## Run locally
Requires Python 3.10+ and an internet connection for installing packages and downloading models.

1. Open a terminal in this folder.
2. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   ```
3. Activate it:
   - Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
   - Windows CMD: `.venv\\Scripts\\activate.bat`
   - macOS/Linux: `source .venv/bin/activate`
4. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
5. Start the app:
   ```bash
   python app.py
   ```
6. Open `http://127.0.0.1:5000`.

The first transformer/model use may download several GB depending on installed PyTorch and model cache; it may take time and needs disk space. The app includes fallback summary/sentiment behavior if models fail to load, and it labels those fallback results.

## REST API example
Send a POST request to `/api/analyze` with JSON:
```json
{"text":"Paste an article of at least 80 characters here..."}
```
The endpoint returns summary, sentiment, score, keywords, and method labels.

## Semantic grouping
`group_articles(texts)` in `app.py` groups article strings using multilingual sentence embeddings when available. It is included as a reusable function; this first version does not yet expose a dedicated UI for multi-article grouping.

## Important limitations
- The summarization model is English-focused, so the project is not fully multilingual end-to-end yet.
- Sentiment scores are model confidence, not a calibrated probability of truth.
- Article extraction can fail when websites block automated requests or require JavaScript/login.
- Keyword frequency is a simple baseline, not a full topic model.
- This is an educational prototype. Do not treat outputs as verified facts.
- Before public deployment, disable Flask debug mode, use a production WSGI server, configure environment secrets, add request rate limits, and review URL-fetching security.
- Do not publish API secrets or private article content.
