from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]

def start(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEWLENS_DB',str(tmp_path/'actions.db'))
    return AppTest.from_file(ROOT/'app.py').run(timeout=30)

def test_navigation_filters_and_reports(tmp_path,monkeypatch):
    app=start(tmp_path,monkeypatch)
    assert not app.exception
    assert len(app.metric)==4
    assert app.metric[0].value=='32'
    app.selectbox[0].set_value('City café').run()
    assert app.metric[0].value=='16'
    for name in ['Explore reviews','Action plan','Reports & help','Add reviews']:
        app.radio(key='page').set_value(name).run(timeout=30)
        assert not app.exception

def test_paste_import_and_mixed_aspects(tmp_path,monkeypatch):
    app=start(tmp_path,monkeypatch)
    app.radio(key='page').set_value('Add reviews').run()
    app.radio(key='input_method').set_value('Paste reviews').run()
    app.text_area[0].set_value('The food was amazing but the service was terrible.\nWonderful coffee and cake!').run()
    next(b for b in app.button if b.label=='Analyze reviews →').click().run(timeout=30)
    assert not app.exception
    assert app.radio(key='page').value=='Overview'
    assert app.metric[0].value=='2'
    assert not app.session_state['bundle']['demo']
    app.radio(key='page').set_value('Explore reviews').run()
    assert not app.exception
    app.text_input[0].set_value('not present anywhere').run()
    assert any('No reviews match' in i.value for i in app.info)

def test_action_persists_and_status_updates(tmp_path,monkeypatch):
    app=start(tmp_path,monkeypatch)
    app.radio(key='page').set_value('Action plan').run()
    app.text_input[0].set_value('Check lunch waiting times')
    app.text_input[1].set_value('Manager')
    next(b for b in app.button if b.label=='Add to action plan').click().run()
    assert not app.exception
    assert app.metric[0].value=='1'
    app.selectbox(key='status_1').set_value('Done')
    next(b for b in app.button if b.label=='Save changes').click().run()
    assert app.metric[2].value=='1'
    fresh=start(tmp_path,monkeypatch)
    fresh.radio(key='page').set_value('Action plan').run()
    assert fresh.metric[2].value=='1'
