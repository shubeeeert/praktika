import pandas as pd, json, os
BASE=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..'))
DATA=os.path.join(BASE,'data'); OUT=os.path.join(BASE,'analysis','output')
def schema_cols(name):
    p=os.path.join(DATA,'db_structure',name)
    line=open(p,encoding='utf-8-sig').readline().strip()
    return [c.strip() for c in line.split(';') if c.strip()]
res={}
# adv_view_history
try:
    cols=schema_cols('adv_view_history.csv')
    df=pd.read_csv(os.path.join(DATA,'adv_view_history.csv'),sep=';',header=None,names=cols,dtype=str,encoding='utf-8-sig',low_memory=False)
    df['created_at']=pd.to_datetime(df['created_at'],errors='coerce',utc=True)
    res['adv_rows']=len(df); res['adv_users']=int(df['user_id'].nunique())
    df['date']=df['created_at'].dt.date
    pud=df.groupby(['user_id','date']).size()
    pum=df.groupby(['user_id',df['created_at'].dt.to_period('M').astype(str)]).size()
    res['adv_per_user_day']={'mean':float(pud.mean()),'median':float(pud.median()),'p90':float(pud.quantile(0.9)),'p95':float(pud.quantile(0.95)),'max':int(pud.max())}
    res['adv_per_user_month']={'mean':float(pum.mean()),'median':float(pum.median()),'p90':float(pum.quantile(0.9)),'p95':float(pum.quantile(0.95)),'max':int(pum.max())}
    res['adv_total_users_share_of_all']=res['adv_users']/1844880
except Exception as e:
    res['adv_error']=str(e)
# sessions
try:
    cols=schema_cols('sessions.csv')
    df=pd.read_csv(os.path.join(DATA,'sessions.csv'),sep=';',header=None,names=cols,dtype=str,encoding='utf-8-sig',low_memory=False)
    for c in ['created_at','last_accessed_at','revoked_at','expired_at']:
        if c in df.columns: df[c]=pd.to_datetime(df[c],errors='coerce',utc=True)
    res['sess_rows']=len(df); res['sess_users']=int(df['user_id'].nunique())
    spu=df.groupby('user_id').size()
    res['sessions_per_user']={'mean':float(spu.mean()),'median':float(spu.median()),'p90':float(spu.quantile(0.9)),'p95':float(spu.quantile(0.95)),'max':int(spu.max())}
    res['sessions_revoked']=int(df['revoked_at'].notna().sum()) if 'revoked_at' in df.columns else None
    res['sessions_cols']=list(df.columns)
except Exception as e:
    res['sess_error']=str(e)
with open(os.path.join(OUT,'adv_sessions_extra.json'),'w',encoding='utf-8') as f: json.dump(res,f,ensure_ascii=False,indent=2)
print('ok')
