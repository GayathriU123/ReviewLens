import pandas as pd
from insights import build_bundle,aspect_summary,html_report,TaskStore

def test_aspects_dates_and_metadata_alignment():
    frame=pd.DataFrame({'review':['Great food',None,'great FOOD','The food was amazing but the service was terrible.'],
                        'date':['2026-09-01','bad','bad','bad'],'rating':[5,2,3,8],'branch':['A','B','C','D']})
    bundle=build_bundle(frame,'review','date','rating','branch')
    assert bundle['data'].location.tolist()==['A','D']
    assert bundle['info']['invalid_dates']==1
    assert bundle['info']['invalid_ratings']==1
    a=bundle['aspects'];mixed=a[a.source_row.eq(5)]
    assert mixed[mixed.aspect.eq('Food & drinks')].sentiment.iloc[0]=='positive'
    assert mixed[mixed.aspect.eq('Service')].sentiment.iloc[0]=='negative'

def test_report_escapes_user_text():
    b=build_bundle(pd.DataFrame({'review':['Terrible service <script>alert(1)</script>']}),'review',business='<script>')
    report=html_report(b,b['data'],aspect_summary(b['aspects']),'All').decode()
    assert '<script>' not in report
    assert '&lt;script&gt;' in report

def test_tasks_scoped_to_dataset_and_durable(tmp_path):
    path=tmp_path/'tasks.db';store=TaskStore(path)
    store.add('A','Inspect kitchen','Team','2026-10-01')
    assert store.list('B').empty
    store.update('B',1,'Done','Not allowed across datasets')
    assert TaskStore(path).list('A').iloc[0].status=='To do'
    store.update('A',1,'Done','Completed')
    assert TaskStore(path).list('A').iloc[0].status=='Done'
