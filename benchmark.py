"""Compare VADER and a trained TF-IDF + logistic regression baseline on held-out labels."""
import argparse
import json
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


def benchmark(data):
    if not {'review','gold_label'}.issubset(data.columns):
        raise ValueError('CSV requires review and gold_label columns.')
    data = data[['review','gold_label']].copy()
    data['review'] = data.review.fillna('').astype(str).str.strip()
    classes = ['negative','neutral','positive']
    if data.empty or data.review.eq('').any() or not data.gold_label.isin(classes).all():
        raise ValueError('Use nonblank reviews and gold_label values: negative, neutral, positive.')
    data['key'] = data.review.str.lower().str.replace(r'\s+', ' ', regex=True)
    if data.groupby('key').gold_label.nunique().gt(1).any():
        raise ValueError('Some identical reviews have conflicting labels. Resolve these first.')
    data = data.drop_duplicates('key')
    counts = data.gold_label.value_counts().reindex(classes,fill_value=0)
    if counts.min() < 10:
        raise ValueError('Need at least 10 distinct reviews in each of the three classes; 100+ per class is preferred.')
    train, test = train_test_split(data, test_size=.2, stratify=data.gold_label, random_state=42)
    model = make_pipeline(TfidfVectorizer(ngram_range=(1,2),max_features=20000),
                          LogisticRegression(max_iter=1000,class_weight='balanced',random_state=42))
    model.fit(train.review,train.gold_label)
    vader = SentimentIntensityAnalyzer()
    def predict(text):
        score = vader.polarity_scores(text)['compound']
        return 'positive' if score >= .05 else 'negative' if score <= -.05 else 'neutral'
    result={'train_rows':len(train),'test_rows':len(test),'seed':42,'label_order':classes,
            'note':'Fixed 80/20 split after exact normalized deduplication. Near duplicates and source leakage need manual review. Do not tune on this test set.'}
    for name, predictions in [('vader',test.review.map(predict)),('tfidf_logistic',model.predict(test.review))]:
        result[name]={'report':classification_report(test.gold_label,predictions,labels=classes,output_dict=True,zero_division=0),
                      'confusion_matrix':confusion_matrix(test.gold_label,predictions,labels=classes).tolist()}
    return result

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('csv')
    args=parser.parse_args()
    try:
        print(json.dumps(benchmark(pd.read_csv(args.csv)),indent=2))
    except ValueError as error:
        raise SystemExit(str(error))
