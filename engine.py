"""Local NLP analysis; no paid APIs or network inference."""
import io
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


def clean(frame, column):
    if column not in frame.columns:
        raise ValueError("Choose a review text column.")
    if len(frame) > 10000:
        raise ValueError("Use at most 10,000 rows per file.")
    text = frame[column].fillna("").astype(str).str.strip()
    if text.str.len().gt(5000).any():
        raise ValueError("Each review must be at most 5,000 characters.")
    out = pd.DataFrame({"source_row": range(2, len(frame)+2), "review": text.to_numpy()})
    out = out[out.review.ne("")].copy()
    out["key"] = out.review.str.lower().str.replace(r"\s+", " ", regex=True)
    out = out.drop_duplicates("key").drop(columns="key").reset_index(drop=True)
    if out.empty:
        raise ValueError("No non-empty reviews found.")
    return out, len(frame)-len(out)


def analyze(frame, column, max_topics=5):
    data, removed = clean(frame, column)
    analyzer = SentimentIntensityAnalyzer()
    data["sentiment_score"] = data.review.map(lambda t: analyzer.polarity_scores(t)["compound"])
    data["sentiment"] = np.select([data.sentiment_score.ge(.05), data.sentiment_score.le(-.05)],
                                  ["positive", "negative"], default="neutral")
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=4000)
    quality = None
    try:
        matrix = vectorizer.fit_transform(data.review)
    except ValueError:
        matrix = None
    labels = np.zeros(len(data), dtype=int)
    terms = {}
    if matrix is not None:
        # Bound k by distinct feature vectors, avoiding degenerate repeated vectors.
        signatures = {(tuple(matrix[i].indices), tuple(matrix[i].data.round(8))) for i in range(len(data))}
        upper = min(int(max_topics), len(signatures), len(data)-1)
        best = -2.0
        for k in range(2, upper+1):
            model = KMeans(n_clusters=k, random_state=42, n_init=10)
            candidate = model.fit_predict(matrix)
            if len(set(candidate)) < 2:
                continue
            score = silhouette_score(matrix, candidate, metric="cosine", sample_size=min(len(data),1000), random_state=42)
            if score > best:
                best, labels, quality = score, candidate, float(score)
        vocab = vectorizer.get_feature_names_out()
        for label in sorted(set(labels)):
            center = np.asarray(matrix[labels == label].mean(axis=0)).ravel()
            indices = center.argsort()[::-1]
            terms[label] = ", ".join(vocab[i] for i in indices[:4] if center[i] > 0)
    data["topic_id"] = labels+1
    data["topic"] = [terms.get(label) or "Unclassified feedback" for label in labels]
    rows = []
    for topic_id, group in data.groupby("topic_id"):
        negative = group[group.sentiment.eq("negative")]
        # Volume-based priority is transparent; not predicted financial impact.
        rows.append({"topic_id":int(topic_id), "keywords":group.topic.iloc[0], "reviews":len(group),
                     "negative_reviews":len(negative), "negative_percent":round(100*len(negative)/len(group),1),
                     "evidence_source_row":int((negative if len(negative) else group).iloc[0].source_row),
                     "evidence":(negative if len(negative) else group).iloc[0].review})
    topics = pd.DataFrame(rows).sort_values(["negative_reviews","reviews"], ascending=False)
    return data, topics, {"removed_rows":removed, "silhouette":quality}


def csv_bytes(frame):
    safe = frame.copy()
    # Prevent uploaded text becoming spreadsheet formulas in downloaded reports.
    for column in safe.select_dtypes(include=["object", "string"]).columns:
        safe[column] = safe[column].map(lambda x: "'"+x if isinstance(x,str) and x.lstrip().startswith(("=","+","-","@")) else x)
    return safe.to_csv(index=False).encode("utf-8-sig")


def report(data, topics, info):
    lines = ["REVIEWLENS — FEEDBACK REPORT", f"Analyzed {len(data)} unique reviews; excluded {info['removed_rows']} empty/duplicate rows.",
             "English-only NLP baseline. Sentiment is estimated, not human-verified.",
             "Topics are ranked by negative-review count; rankings do not estimate revenue impact.", ""]
    for _, row in topics.iterrows():
        lines += [f"Topic {row.topic_id}: {row.keywords}",
                  f"{row.negative_reviews}/{row.reviews} reviews classified negative ({row.negative_percent}%).",
                  f"Evidence (source CSV row {row.evidence_source_row}): {row.evidence}",
                  "Next step: validate the examples with the owner, choose one change, and compare future feedback.", ""]
    return "\n".join(lines)
