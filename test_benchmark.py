import pandas as pd
import pytest
from benchmark import benchmark

def test_benchmark_rejects_conflicting_labels():
    with pytest.raises(ValueError, match='conflicting'):
        benchmark(pd.DataFrame({'review':['same',' SAME '],'gold_label':['positive','negative']}))

def test_benchmark_split_and_reports():
    # Synthetic fixtures test execution only; these scores are not quality evidence.
    rows=[{'review':f'{phrase} visit number {i}', 'gold_label':label}
          for label, phrase in [('positive','Wonderful food'),('negative','Terrible food'),('neutral','The restaurant opens at noon')]
          for i in range(12)]
    result=benchmark(pd.DataFrame(rows))
    assert result['train_rows']+result['test_rows']==36
    for model in ['vader','tfidf_logistic']:
        assert 'macro avg' in result[model]['report']
        assert len(result[model]['confusion_matrix'])==3
