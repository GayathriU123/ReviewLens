from pathlib import Path
from datetime import date, timedelta
import html
import os
import pandas as pd
import plotly.express as px
import streamlit as st
from engine import csv_bytes
from insights import build_bundle, aspect_summary, SUGGESTIONS, reply_draft, html_report, TaskStore

ROOT=Path(__file__).parent
st.set_page_config(page_title='ReviewLens · Customer insights',page_icon='◉',layout='wide')
st.markdown('''<style>

html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif}
.stApp{background:#f7f8f4;color:#213c35}
.block-container{padding-top:2.4rem;padding-bottom:3rem;max-width:1440px}
[data-testid="stSidebar"]{background:#ecf1e8;border-right:1px solid #dbe5d7}
h1,h2,h3{letter-spacing:-.035em}h1{font-weight:700!important}
.brand{font-size:27px;font-weight:700;letter-spacing:-1px;color:#174c3e;margin:8px 0 4px}
.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#5b7569;font-weight:700}
.hero{background:#173f35;border-radius:22px;padding:30px 34px;color:#f7f8ef;margin:10px 0 25px}
.hero h1{color:#fff;font-size:36px;line-height:1.15;margin:10px 0}.hero p{color:#cfdfd1;max-width:690px;margin-bottom:0}.hero .eyebrow{color:#b5d895}
[data-testid="stMetric"]{background:#fff;border:1px solid #e0e7dc;border-radius:16px;padding:18px 22px}
[data-testid="stMetricValue"]{font-size:32px;color:#174c3e}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px}
.step{padding:20px;background:#fff;border:1px solid #e0e7dc;border-radius:16px;min-height:128px}.step b{color:#214e3b}.step p{font-size:14px;color:#62776d;margin:8px 0 0}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:#205b46;border:0;color:#fff;border-radius:10px}
[data-testid="stSidebar"] .stRadio label  {padding-top:5px;padding-bottom:5px}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
[data-testid="stSidebar"] .stRadio label p,
[data-testid="stSidebar"] [data-baseweb="select"] *,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    color: #29483c !important;
}

[data-testid="stSidebar"] .brand {
    color: #174c3e !important;
}

[data-testid="stSidebar"] .eyebrow {
    color: #5b7569 !important;
}
@media(max-width:700px){.block-container{padding:1rem}.hero{padding:23px}.hero h1{font-size:28px}}
</style>''',unsafe_allow_html=True)


def demo():
    result=build_bundle(pd.read_csv(ROOT/'data/demo_reviews.csv'),'review','date','rating','location',business='The Green Table · Demo')
    result['demo']=True
    return result


def nav_to(page):
    st.session_state['page']=page


def button_to(label,page,key=None):
    st.button(label,on_click=nav_to,args=(page,),key=key,type='primary')


def chart_style(fig,height=290):
    fig.update_layout(height=height,margin=dict(l=10,r=10,t=15,b=10),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(color='#29483c',family='Arial'),legend_title_text='')
    return fig

if st.session_state.pop('go_overview',False):
    st.session_state['page']='Overview'

if 'bundle' not in st.session_state:
    st.session_state.bundle=demo()
bundle=st.session_state.bundle
store=TaskStore(os.environ.get('REVIEWLENS_DB',str(ROOT/'private_data/actions.sqlite3')))
with st.sidebar:
    st.markdown('<div class="brand">◉ ReviewLens</div><div class="eyebrow">Listen. Understand. Improve.</div>',unsafe_allow_html=True)
    st.divider()
    page=st.radio('Workspace',['Overview','Add reviews','Explore reviews','Action plan','Reports & help'],key='page')
    st.divider()
    st.caption('CURRENT BUSINESS')
    st.write(bundle['business'])
    st.caption('Demo workspace · invented data' if bundle.get('demo') else 'Your uploaded feedback')
    st.caption('English reviews • Analysis runs locally')
    if page!='Add reviews':
        st.markdown('**Narrow your view**')
        location=st.selectbox('Location',['All locations']+sorted(x for x in bundle['data'].location.unique() if x!='All locations'),key=f"location_{bundle['id']}")
        period=st.selectbox('Review dates',['All dates','Last 30 days in file','Custom range'],key=f"period_{bundle['id']}")
        data=bundle['data'].copy()
        if location!='All locations':
            data=data[data.location.eq(location)]
        date_scope='All dates'
        if period!='All dates':
            valid=bundle['data'].date.dropna()
            if valid.empty:
                st.info('Add a date column to use date filters.')
            else:
                if period=='Last 30 days in file':
                    end=valid.max().date(); start=end-timedelta(days=29)
                else:
                    chosen=st.date_input('Choose start and end',value=(valid.min().date(),valid.max().date()),key=f"range_{bundle['id']}")
                    if len(chosen)!=2:
                        st.info('Choose both dates to see results.');st.stop()
                    start,end=chosen
                data=data[data.date.between(pd.Timestamp(start),pd.Timestamp(end))]
                date_scope=f'{start} to {end}'
                st.caption('Undated reviews are excluded from date-filtered results.')
        scope=f'{location} · {date_scope}'
    st.divider()
    st.caption('01 Add feedback  →  02 Find patterns  →  03 Take action')

if page=='Add reviews':
    st.markdown('<div class="eyebrow">STEP 01 / BRING YOUR FEEDBACK</div>',unsafe_allow_html=True)
    st.title('Start with what your customers say.')
    st.write('Upload a spreadsheet or paste reviews. We’ll guide you through the rest.')
    cols=st.columns(3)
    for col,number,title,desc in zip(cols,['1','2','3'],['Add your reviews','Match the columns','Open your dashboard'],['Upload a CSV or paste one review per line.','Review text is required. Dates and ratings are optional.','Click Analyze reviews when the preview looks right.']):
        col.markdown(f'<div class="step"><b>{number} · {title}</b><p>{desc}</p></div>',unsafe_allow_html=True)
    st.write('')
    left,right=st.columns([2,1],gap='large')
    with left:
        business=st.text_input('Business name',value='My café',max_chars=100)
        method=st.radio('How would you like to add reviews?',['Upload a CSV','Paste reviews'],horizontal=True,key='input_method')
        frame=None
        if method=='Upload a CSV':
            uploaded=st.file_uploader('Upload your review spreadsheet',type='csv',help='UTF-8 CSV, up to 5 MB and 10,000 rows. Export from Excel using CSV UTF-8.')
            if uploaded:
                if uploaded.size>5*1024*1024:
                    st.error('This file is over 5 MB. Split it into smaller files.')
                else:
                    try:
                        frame=pd.read_csv(uploaded,nrows=10001)
                    except (pd.errors.ParserError,pd.errors.EmptyDataError,UnicodeDecodeError):
                        st.error('We could not read this file. Save it as CSV UTF-8 with a header row and try again.')
        else:
            text=st.text_area('Paste one review per line',height=170,placeholder='The food was excellent, but the service was terrible.\nLovely atmosphere and friendly staff.',max_chars=200000)
            if text.strip():
                frame=pd.DataFrame({'review':text.splitlines()})
        if frame is not None:
            st.markdown('**Check your data**')
            st.dataframe(frame.head(5),hide_index=True,width='stretch')
            options=list(frame.columns)
            review_col=st.selectbox('Which column contains the review text?',options,index=options.index('review') if 'review' in options else 0)
            with st.expander('Optional: add dates, star ratings, and locations',expanded=method=='Upload a CSV'):
                optional=['Not included']+options
                def mapping(label,name):
                    return st.selectbox(label,optional,index=optional.index(name) if name in options else 0)
                d=mapping('Date column · YYYY-MM-DD','date')
                r=mapping('Rating column · numbers from 1 to 5','rating')
                l=mapping('Location or branch column','location')
            with st.expander('Advanced analysis settings'):
                maximum=st.slider('Maximum recurring topics',2,8,5)
            st.caption('Use feedback you have permission to analyze. Remove names, phone numbers, and email addresses first.')
            if st.button('Analyze reviews →',type='primary'):
                try:
                    selected=[x for x in [review_col,d,r,l] if x!='Not included']
                    if len(selected)!=len(set(selected)):
                        raise ValueError('Choose a different column for each field, or choose Not included.')
                    with st.spinner('Reading feedback and finding patterns…'):
                        result=build_bundle(frame,review_col,*[None if x=='Not included' else x for x in [d,r,l]],max_topics=maximum,business=business)
                        result['demo']=False
                    st.session_state.bundle=result
                    st.session_state['go_overview']=True
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        else:
            st.info('Your current dashboard stays available while you prepare a new upload.')
    with right:
        with st.container(border=True):
            st.subheader('No spreadsheet yet?')
            st.write('Use this example as a starting point. Replace its two sample rows with your own feedback.')
            st.download_button('Download CSV template',b'review,date,rating,location\n"Excellent coffee and friendly staff.",2026-09-01,5,Main branch\n"The service was terrible.",2026-09-02,1,Main branch\n','review_template.csv','text/csv')
            st.caption('Dates and ratings unlock extra charts. You can leave them out.')
        with st.container(border=True):
            st.subheader('Just exploring?')
            st.write('Try a complete fictional restaurant dataset before uploading your own.')
            if st.button('Load sample workspace'):
                st.session_state.bundle=demo();st.session_state['go_overview']=True;st.rerun()
    st.stop()

# Redirect imports on the next run before the sidebar widget is constructed (handled below via callback flag).
if data.empty:
    st.title('No reviews match these filters')
    st.info('Choose All locations and All dates in the sidebar to bring your reviews back.')
    st.stop()
evidence=bundle['aspects'][bundle['aspects'].source_row.isin(data.source_row)]
summary=aspect_summary(evidence)
negative=int(data.sentiment.eq('negative').sum())
if bundle.get('demo'):
    st.caption('SAMPLE WORKSPACE · All reviews, dates, and ratings shown here are invented. Add your own reviews to see your business.')
else:
    info=bundle['info']
    issues=[]
    if info['removed_rows']:issues.append(f"{info['removed_rows']} blank or duplicate reviews excluded")
    if info['invalid_dates']:issues.append(f"{info['invalid_dates']} missing/invalid dates excluded from trends")
    if info['invalid_ratings']:issues.append(f"{info['invalid_ratings']} missing/invalid ratings excluded from averages")
    if issues:st.info('Data check: '+ '; '.join(issues)+'.')
st.caption(scope)

if page=='Overview':
    st.markdown(f'<div class="hero"><div class="eyebrow">YOUR CUSTOMER EXPERIENCE, AT A GLANCE</div><h1>Better feedback.<br>Clearer next steps.</h1><p>Understand what guests love, spot recurring concerns, and turn insights into a plan for {html.escape(bundle["business"])}.</p></div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric('Reviews analyzed',f'{len(data):,}')
    b.metric('Positive feedback',f'{100*data.sentiment.eq("positive").mean():.0f}%',help='Estimated from the full review text, not the star rating.')
    c.metric('Negative feedback',f'{negative:,}',help='Estimated negative reviews in your current selection.')
    d.metric('Average star rating',f'{data.rating.mean():.1f} / 5' if data.rating.notna().any() else '—',help=f'Based on {data.rating.notna().sum()} valid customer ratings.')
    st.write('')
    left,right=st.columns([1,1.5],gap='large')
    with left,st.container(border=True):
        st.subheader('How guests are feeling')
        counts=data.sentiment.value_counts().reindex(['positive','neutral','negative'],fill_value=0).rename_axis('Sentiment').reset_index(name='Reviews')
        fig=px.pie(counts,names='Sentiment',values='Reviews',hole=.72,color='Sentiment',color_discrete_map={'positive':'#438c66','neutral':'#c6d6ae','negative':'#d9957c'})
        fig.update_traces(textinfo='percent',textposition='outside')
        st.plotly_chart(chart_style(fig),width='stretch',config={'displayModeBar':False})
        st.caption('Sentiment is an estimate. Read the original reviews before deciding what to change.')
    with right,st.container(border=True):
        st.subheader('Where to focus first')
        concerns=summary[summary.negative.gt(0)] if not summary.empty else summary
        if concerns.empty:
            st.success('No negative aspect estimates found in this selection.')
            st.caption('This does not guarantee every guest was satisfied. Review the evidence for missed concerns.')
        else:
            fig=px.bar(concerns.sort_values('negative'),x='negative',y='aspect',orientation='h',text='negative',color_discrete_sequence=['#315f48'],labels={'negative':'Reviews with negative mentions','aspect':''})
            fig.update_traces(textposition='outside')
            st.plotly_chart(chart_style(fig),width='stretch',config={'displayModeBar':False})
        st.caption('Food, service, cleanliness, value, atmosphere, and delivery are estimated from keywords and clauses. One review can appear in several areas.')
    st.write('')
    l,r=st.columns([1.6,1],gap='large')
    with l,st.container(border=True):
        st.subheader('Feedback over time')
        dated=data.dropna(subset=['date']).copy()
        if dated.empty:
            st.info('Add an optional date column to see weekly review trends here.')
            button_to('Add dated reviews','Add reviews','dates_cta')
        else:
            dated['Week starting']=dated.date.dt.to_period('W').dt.start_time
            weekly=dated.groupby(['Week starting','sentiment']).size().unstack(fill_value=0).reindex(columns=['positive','neutral','negative'],fill_value=0)
            weekly=weekly.reindex(pd.date_range(weekly.index.min(),weekly.index.max(),freq='7D'),fill_value=0).rename_axis('Week starting').reset_index()
            fig=px.bar(weekly,x='Week starting',y=['positive','neutral','negative'],color_discrete_map={'positive':'#438c66','neutral':'#c6d6ae','negative':'#d9957c'},labels={'value':'Reviews','variable':'Sentiment'})
            st.plotly_chart(chart_style(fig,270),width='stretch',config={'displayModeBar':False})
            if dated.rating.notna().any():
                ratings=dated.groupby('Week starting').rating.agg(['mean','count']).reset_index()
                ratings=ratings[ratings['count'].gt(0)]
                rating_fig=px.line(ratings,x='Week starting',y='mean',markers=True,hover_data=['count'],labels={'mean':'Average star rating','count':'Ratings'},color_discrete_sequence=['#315f48'])
                rating_fig.update_yaxes(range=[1,5])
                st.plotly_chart(chart_style(rating_fig,210),width='stretch',config={'displayModeBar':False})
            st.caption(f'{len(dated)} dated reviews. Changes in volume or customer mix can affect these charts; they do not prove an action caused improvement.')
    with r,st.container(border=True):
        st.subheader('Your next move')
        if len(concerns):
            top=concerns.iloc[0]
            st.markdown(f'**Investigate {top.aspect.lower()}**')
            st.write(f'{int(top.negative)} of {int(top.mentions)} reviews mentioning this area contain a negative estimate.')
            st.write(SUGGESTIONS[top.aspect])
        else:
            st.write('Read a few customer reviews and decide which experience you want to improve next.')
        button_to('Build an action plan →','Action plan','action_cta')
        st.divider()
        st.markdown('**Need a quick walkthrough?**')
        st.write('Start with the charts, inspect the original words, then give one improvement an owner and a due date.')
        button_to('Explore the reviews','Explore reviews','review_cta')

elif page=='Explore reviews':
    st.markdown('<div class="eyebrow">STEP 02 / UNDERSTAND THE DETAILS</div>',unsafe_allow_html=True)
    st.title('Every insight starts with a real review.')
    st.write('Search the feedback, inspect mixed opinions, and prepare a reply you can edit.')
    a,b,c=st.columns([2,1,1])
    query=a.text_input('Search reviews',placeholder='Try “coffee” or “waiting”')
    sentiments=b.multiselect('Sentiment',['positive','neutral','negative'],default=['positive','neutral','negative'])
    aspect=c.selectbox('Service area',['All areas']+list(SUGGESTIONS))
    mismatch=st.checkbox('Only show star-rating and sentiment mismatches',help='Flags negative text with 4–5 stars, or positive text with 1–2 stars. These need a human check.')
    filtered=data[data.sentiment.isin(sentiments)&data.review.str.contains(query,case=False,regex=False)]
    if aspect!='All areas':filtered=filtered[filtered.source_row.isin(evidence[evidence.aspect.eq(aspect)].source_row)]
    if mismatch:filtered=filtered[filtered.rating_conflict]
    st.caption(f'{len(filtered)} matching reviews · {int(data.rating_conflict.sum())} rating mismatches in the current sidebar selection')
    if filtered.empty:
        st.info('No reviews match. Clear your search or widen the filters.')
    else:
        st.dataframe(filtered[['source_row','review','sentiment','rating','date','location']],hide_index=True,width='stretch',column_config={'source_row':'Source record','review':'Customer review','sentiment':'Estimated sentiment','rating':st.column_config.NumberColumn('Stars',format='%.1f'),'date':st.column_config.DateColumn('Date'),'location':'Location'})
        st.download_button('Export matching reviews',csv_bytes(filtered),'filtered_reviews.csv','text/csv')
        record=st.selectbox('Choose a review to inspect or reply to',filtered.source_row.tolist(),format_func=lambda x:f'Record {x} · {filtered.loc[filtered.source_row.eq(x),"review"].iloc[0][:80]}')
        row=filtered[filtered.source_row.eq(record)].iloc[0]
        l,r=st.columns(2,gap='large')
        with l,st.container(border=True):
            st.subheader('What the customer said')
            st.text(row.review)
            details=evidence[evidence.source_row.eq(record)]
            if len(details):
                st.dataframe(details[['aspect','sentiment','evidence']],hide_index=True,width='stretch')
            else:st.info('No known service-area keywords detected. Read this review manually.')
            st.caption('Aspect estimates use clause splitting + keyword rules. Several aspects in one clause may receive the same estimate; sarcasm and indirect references can be missed.')
        with r,st.container(border=True):
            st.subheader('Prepare a reply')
            st.caption('Editable template based on overall sentiment. Nothing is sent or posted automatically.')
            tone=st.selectbox('Reply tone',['Warm','Professional'])
            draft=st.text_area('Review and personalize before using',value=reply_draft(row.sentiment,bundle['business'],tone),height=210,key=f"reply_{bundle['id']}_{record}_{tone}")
            st.download_button('Download edited reply',draft,'review_reply.txt','text/plain')
    with st.expander('Discover other recurring topics'):
        st.caption('These TF-IDF / K-Means topics were learned from the whole uploaded dataset. Counts below reflect your sidebar selection; topic keywords stay fixed.')
        topics=data.groupby(['topic_id','topic']).agg(reviews=('review','size'),negative=('sentiment',lambda s:s.eq('negative').sum())).reset_index()
        st.dataframe(topics.sort_values('negative',ascending=False),hide_index=True,width='stretch')

elif page=='Action plan':
    st.markdown('<div class="eyebrow">STEP 03 / TURN FEEDBACK INTO FOLLOW-THROUGH</div>',unsafe_allow_html=True)
    st.title('Small improvements. Clear ownership.')
    st.write('Choose an issue, assign a next step, and track what your team has done.')
    st.caption('Tasks are saved on this computer for this business and dataset. Sidebar filters do not hide tasks. Re-upload the same cleaned dataset with the same business name to reopen its plan. A changed dataset starts a new plan.')
    left,right=st.columns([1,1.25],gap='large')
    with left,st.container(border=True):
        st.subheader('Add an improvement')
        issue=st.selectbox('Choose a starting point',['Write my own']+list(SUGGESTIONS))
        if issue!='Write my own':st.info('Suggested check: '+SUGGESTIONS[issue])
        with st.form('add_action',clear_on_submit=True):
            title=st.text_input('What will you do?',placeholder='Example: measure waiting time during the lunch rush',max_chars=300)
            owner=st.text_input('Who is responsible?',placeholder='Name or team',max_chars=100)
            due=st.date_input('Due date',value=date.today()+timedelta(days=7))
            submitted=st.form_submit_button('Add to action plan',type='primary')
        if submitted:
            try:store.add(bundle['id'],title,owner,due);st.success('Action saved on this computer.')
            except ValueError as error:st.error(str(error))
    tasks=store.list(bundle['id'])
    with right,st.container(border=True):
        st.subheader('Progress board')
        if tasks.empty:st.info('Your plan is empty. Add one practical improvement to get started.')
        else:
            a,b,c=st.columns(3)
            for col,status in zip([a,b,c],['To do','In progress','Done']):col.metric(status,int(tasks.status.eq(status).sum()))
            for task in tasks.itertuples():
                overdue=task.status!='Done' and task.due<date.today().isoformat()
                with st.expander(f'{task.status} · {task.title}',expanded=len(tasks)==1):
                    st.write(f'Owner: {task.owner or "Unassigned"} · Due: {task.due}'+(' · Overdue' if overdue else ''))
                    with st.form(f'update_{task.id}'):
                        status=st.selectbox('Status',['To do','In progress','Done'],index=['To do','In progress','Done'].index(task.status),key=f'status_{task.id}')
                        notes=st.text_area('Progress notes',value=task.notes,key=f'notes_{task.id}',max_chars=3000)
                        if st.form_submit_button('Save changes'):
                            store.update(bundle['id'],task.id,status,notes);st.rerun()
            st.download_button('Export action plan',csv_bytes(tasks.drop(columns='id')),'action_plan.csv','text/csv')

elif page=='Reports & help':
    st.markdown('<div class="eyebrow">SHARE THE FINDINGS / LEARN THE WORKFLOW</div>',unsafe_allow_html=True)
    st.title('Useful reports. No extra work.')
    a,b=st.columns(2)
    with a,st.container(border=True):
        st.subheader('Owner brief')
        st.write('A clean, printable report with service-area priorities and supporting feedback. It uses your current sidebar filters.')
        st.download_button('Download owner brief',html_report(bundle,data,summary,scope),'reviewlens_owner_brief.html','text/html',type='primary')
        st.caption('Open the downloaded HTML in a browser. Use Print → Save as PDF for a PDF copy.')
    with b,st.container(border=True):
        st.subheader('Analysis spreadsheet')
        st.write('Take the selected reviews, sentiment estimates, star ratings, dates, and topic labels into Excel.')
        st.download_button('Download analyzed reviews',csv_bytes(data),'reviewlens_analysis.csv','text/csv')
        st.download_button('Download aspect evidence',csv_bytes(evidence),'reviewlens_aspect_evidence.csv','text/csv')
    st.subheader('A simple way to use ReviewLens')
    for title,body in [('1 · Add reviews','Choose Add reviews. Upload a CSV or paste one review per line. Match the text column, optionally add dates, ratings, and locations, then click Analyze reviews.'),('2 · Understand the findings','Read Overview, then inspect the original reviews in Explore reviews. Compare the automated estimates with what customers actually wrote.'),('3 · Take one action','Use Action plan to write a specific improvement, assign an owner, and set a date. Actions and notes are saved locally.'),('4 · Share and follow up','Download the owner brief and action plan. Later feedback can help you monitor progress; it does not prove that a particular action caused a change.')]:
        with st.expander(title):st.write(body)
    with st.expander('What is estimated, and what is measured?'):
        st.write('Sentiment: VADER rules and vocabulary. Aspects: keyword matches in sentence/contrast clauses, with VADER sentiment per clause. Topic discovery: TF-IDF + K-Means, selecting candidate cluster count by cosine silhouette. Star ratings and dates come from the uploaded file. Counts are calculated after blank and duplicate text removal. These methods have not been evaluated on real customer data here.')
        st.write('Aspect negative/positive counts count unique reviews; mixed reviews may count in both. Suggested checks and reply drafts use fixed templates, not a generative model. Scores are not confidence probabilities.')
    with st.expander('Where does my data go?'):
        st.write('Review analysis runs on the computer hosting this app. Uploaded reviews stay in the current session and are not intentionally saved to disk. Action titles, owners, due dates, statuses, and notes persist in private_data/actions.sqlite3. Keep this folder when updating the app. Reports contain customer text; share them appropriately. Reloading the browser can reset the active dataset to the demo. This is a local single-user application without accounts or payments.')
    with st.expander('Why does a review seem incorrectly classified?'):
        st.write('The current English-only baseline can miss sarcasm, slang, indirect references, and mixed opinions. Several aspects in one clause can share a score incorrectly. Use the original evidence as the source of truth. A rating mismatch is a prompt for human review, not proof that the rating is wrong.')
