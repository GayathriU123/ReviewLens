"""Explainable restaurant feedback helpers. Aspect estimates use rules, not a trained ABSA model."""
import hashlib
import html
import re
import sqlite3
from pathlib import Path
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from engine import analyze

ASPECTS = {
    'Food & drinks': r'\b(food|meal|pizza|pasta|bread|coffee|tea|cake|dessert|dish|dishes|chicken|rice|biryani|drink|drinks|cappuccino)\b',
    'Service': r'\b(service|staff|waiter|waitress|server|wait|waited|waiting|queue|order|orders)\b',
    'Cleanliness': r'\b(clean|cleanliness|dirty|filthy|hygiene|washroom|toilet|plates|sticky|spotless)\b',
    'Value & billing': r'\b(price|prices|expensive|cheap|affordable|bill|billing|overpriced|value|charges|portion|portions|money)\b',
    'Atmosphere': r'\b(atmosphere|ambience|ambiance|music|noise|noisy|seating|chairs|decor|comfortable|crowded)\b',
    'Delivery': r'\b(delivery|delivered|packaging|package|spilled|courier|takeaway)\b',
}
SUGGESTIONS = {
    'Food & drinks': 'Check preparation and serving quality for the dishes mentioned in the reviews.',
    'Service': 'Review the service complaints with the team and test one change to the ordering or waiting process.',
    'Cleanliness': 'Inspect the areas mentioned and review the cleaning checklist with the team.',
    'Value & billing': 'Check bill accuracy and whether menu prices and portion sizes are clearly communicated.',
    'Atmosphere': 'Inspect the seating, sound, or comfort issues mentioned by customers.',
    'Delivery': 'Review packing and delivery handoff for the specific issues customers reported.',
}

def polarity(score):
    return 'positive' if score >= .05 else 'negative' if score <= -.05 else 'neutral'


def aspect_feedback(data):
    analyzer = SentimentIntensityAnalyzer()
    rows = []
    for row in data.itertuples():
        # Split contrast clauses so food praise and service criticism can be separate.
        clauses = [x.strip(' ,') for x in re.split(r'[.!?;\n]+|\b(?:but|however|although|whereas|yet)\b', row.review, flags=re.I) if x.strip(' ,')]
        for clause in clauses:
            score = analyzer.polarity_scores(clause)['compound']
            for aspect, pattern in ASPECTS.items():
                if re.search(pattern, clause, re.I):
                    rows.append({'source_row':row.source_row,'aspect':aspect,'sentiment':polarity(score),'score':score,'evidence':clause})
    return pd.DataFrame(rows, columns=['source_row','aspect','sentiment','score','evidence'])


def aspect_summary(evidence):
    rows = []
    if evidence.empty:
        return pd.DataFrame(columns=['aspect','mentions','negative','positive','mixed','negative_percent'])
    for aspect, group in evidence.groupby('aspect'):
        sentiments = group.groupby('source_row').sentiment.agg(set)
        neg = sum('negative' in s for s in sentiments)
        pos = sum('positive' in s for s in sentiments)
        rows.append({'aspect':aspect,'mentions':len(sentiments),'negative':neg,'positive':pos,
                     'mixed':sum({'positive','negative'}.issubset(s) for s in sentiments),
                     'negative_percent':round(100*neg/len(sentiments),1)})
    return pd.DataFrame(rows).sort_values(['negative','mentions'],ascending=False)


def build_bundle(frame, text_col, date_col=None, rating_col=None, location_col=None, max_topics=5, business='My business'):
    data, topics, info = analyze(frame,text_col,max_topics)
    original = frame.iloc[(data.source_row-2).to_numpy()].reset_index(drop=True)
    data['date'] = pd.to_datetime(original[date_col],format='%Y-%m-%d',errors='coerce') if date_col else pd.NaT
    raw_rating = pd.to_numeric(original[rating_col],errors='coerce') if rating_col else pd.Series(float('nan'),index=data.index)
    data['rating'] = raw_rating.where(raw_rating.between(1,5))
    data['location'] = original[location_col].fillna('Unspecified').astype(str).str.strip().replace('','Unspecified') if location_col else 'All locations'
    data['rating_conflict'] = ((data.rating.ge(4)&data.sentiment.eq('negative')) | (data.rating.le(2)&data.sentiment.eq('positive')))
    info.update({'invalid_dates':int(data.date.isna().sum()) if date_col else 0,
                 'invalid_ratings':int(data.rating.isna().sum()) if rating_col else 0,
                 'has_dates':bool(date_col),'has_ratings':bool(rating_col),'input_rows':len(frame)})
    signature = business.strip()+'\n'+data[['review','date','rating','location']].astype(str).to_csv(index=False)
    return {'data':data,'topics':topics,'info':info,'aspects':aspect_feedback(data),'business':business.strip() or 'My business',
            'id':hashlib.sha256(signature.encode()).hexdigest()[:24]}


def reply_draft(sentiment, business, tone='Warm'):
    opening = 'Thank you for sharing your experience.' if tone=='Professional' else 'Thanks for taking the time to leave us a review!'
    body = {'positive':"We’re glad you enjoyed your visit and appreciate your feedback. We hope to welcome you again.",
            'negative':"We’re sorry your experience did not meet your expectations. We’d appreciate the chance to understand what happened. Please contact our team directly with the details of your visit.",
            'neutral':"Your feedback helps us understand our guests’ experiences. If there is anything you would like us to improve, please let our team know."}[sentiment]
    return f'{opening}\n\n{body}\n\n— {business}'


def html_report(bundle, data, summary, scope):
    esc=lambda x:html.escape(str(x))
    rating=f'{data.rating.mean():.1f}/5' if data.rating.notna().any() else 'Not supplied'
    lines=['<!doctype html><html><head><meta charset="utf-8"><title>ReviewLens report</title>',
           '<style>body{font:16px system-ui;max-width:900px;margin:50px auto;padding:24px;color:#18342d}h1{font-size:38px}small{color:#526860}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd}blockquote{background:#f3f6f1;padding:16px}@media print{body{margin:0}button{display:none}}</style></head><body>',
           '<small>REVIEWLENS / OWNER BRIEF</small>',f'<h1>{esc(bundle["business"])}</h1>',f'<p>{esc(scope)}</p>',
           f'<p><b>{len(data)} reviews</b> · {data.sentiment.eq("negative").sum()} estimated negative · Average rating: {rating}</p>',
           '<h2>Areas to investigate</h2><p>Counts are unique reviews containing negative clause estimates. One review can mention multiple areas.</p>',
           summary.to_html(index=False,escape=True) if len(summary) else '<p>No recognized aspect keywords in this selection.</p>',
           '<h2>Supporting customer feedback</h2>']
    for row in data[data.sentiment.eq('negative')].head(10).itertuples():
        lines.append(f'<blockquote>{esc(row.review)}<br><small>Source CSV record {row.source_row}</small></blockquote>')
    lines+=['<h2>How to use this report</h2><p>Read the evidence, choose one issue, assign an owner, and compare later feedback. Suggestions are checks to consider, not verified causes.</p>',
            '<p><small>English-only prototype. VADER estimates sentiment; keyword and clause rules estimate aspects. Sarcasm, mixed clauses, and unfamiliar wording can be wrong. No accuracy or revenue impact is claimed. Ratings are customer-supplied, not model scores. Repeated review texts are deduplicated.</small></p></body></html>']
    return ''.join(lines).encode('utf-8')


class TaskStore:
    """Local single-user action storage. No uploaded review text is persisted."""
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, dataset TEXT NOT NULL, title TEXT NOT NULL, owner TEXT, due TEXT, status TEXT, notes TEXT)')
    def connect(self):
        return sqlite3.connect(self.path)
    def add(self,dataset,title,owner,due):
        if not title.strip():
            raise ValueError('Enter an action first.')
        with self.connect() as db:
            db.execute('INSERT INTO tasks(dataset,title,owner,due,status,notes) VALUES (?,?,?,?,?,?)',(dataset,title.strip(),owner.strip(),str(due),'To do',''))
    def list(self,dataset):
        with self.connect() as db:
            return pd.read_sql_query('SELECT id,title,owner,due,status,notes FROM tasks WHERE dataset=? ORDER BY id DESC',db,params=(dataset,))
    def update(self,dataset,task_id,status,notes):
        if status not in ['To do','In progress','Done']:
            raise ValueError('Invalid status.')
        with self.connect() as db:
            db.execute('UPDATE tasks SET status=?,notes=? WHERE dataset=? AND id=?',(status,notes,dataset,int(task_id)))
