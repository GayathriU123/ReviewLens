"""Run only on independently human-labeled feedback, not synthetic demo data."""
import argparse
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="CSV with review and gold_label columns")
    args = parser.parse_args()
    data = pd.read_csv(args.csv)
    if not {"review","gold_label"}.issubset(data.columns):
        raise SystemExit("Required columns: review, gold_label")
    classes = ["negative","neutral","positive"]
    if data.empty or data.review.isna().any() or data.review.astype(str).str.strip().eq("").any() or not data.gold_label.isin(classes).all():
        raise SystemExit("Every row requires nonblank text and a gold_label: negative, neutral, positive")
    model = SentimentIntensityAnalyzer()
    def predict(t):
        score = model.polarity_scores(str(t))["compound"]
        return "positive" if score >= .05 else "negative" if score <= -.05 else "neutral"
    predictions = data.review.map(predict)
    print("Rows:",len(data))
    print(classification_report(data.gold_label,predictions,labels=classes,zero_division=0))
    print("Confusion matrix (true rows, predicted columns):",classes)
    print(confusion_matrix(data.gold_label,predictions,labels=classes))
