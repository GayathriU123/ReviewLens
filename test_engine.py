import pandas as pd
import pytest
from engine import analyze, clean, csv_bytes, report

def test_empty_and_duplicate_cleanup():
    data, removed = clean(pd.DataFrame({"review":[None,"", "Good food", " good   food "]}),"review")
    assert len(data)==1 and removed==3
    assert data.source_row.tolist()==[4]

def test_empty_input():
    with pytest.raises(ValueError):
        analyze(pd.DataFrame({"review":[None, " "]}),"review")

@pytest.mark.parametrize("reviews", [["the and"], ["Great food!"], ["food", "FOOD", "food!"]])
def test_small_or_no_vocabulary(reviews):
    data, topics, info = analyze(pd.DataFrame({"review":reviews}),"review")
    assert topics.reviews.sum()==len(data)

def test_real_pipeline_and_evidence():
    frame = pd.read_csv("data/demo_reviews.csv")
    data, topics, info = analyze(frame,"review")
    assert len(topics)>=2
    assert -1<=info["silhouette"]<=1
    assert data.sentiment_score.between(-1,1).all()
    for _, topic in topics.iterrows():
        assert data.loc[data.source_row.eq(topic.evidence_source_row),"review"].iloc[0]==topic.evidence
    assert "FEEDBACK REPORT" in report(data,topics,info)

def test_csv_formula_escaping():
    result = csv_bytes(pd.DataFrame({"review":["=SUM(1)"," @evil", "ordinary"]})).decode("utf-8-sig")
    assert "'=SUM(1)" in result and "' @evil" in result

def test_limits():
    with pytest.raises(ValueError):
        clean(pd.DataFrame({"review":["x"*5001]}),"review")
