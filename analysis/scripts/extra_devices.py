import pandas as pd, json, os
BASE=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..'))
DATA=os.path.join(BASE,'data')
OUT=os.path.join(BASE,'analysis','output')
def schema_cols(name):
    p=os.path.join(DATA,'db_structure',name)
    line=open(p,encoding='utf-8-sig').readline().strip()
    return [c.strip() for c in line.split(';') if c.strip()]
cols=schema_cols('devices.csv')
df=pd.read_csv(os.path.join(DATA,'devices.csv'),sep=';',header=None,names=cols,dtype=str,encoding='utf-8-sig',low_memory=False)
res={}
res['rows']=len(df)
res['cols']=list(df.columns)
for c in ['client_type','os','brand','in_sub']:
    if c in df.columns: res[c]=df[c].value_counts(dropna=False).head(20).to_dict()
if 'user_id' in df.columns:
    dpu=df.groupby('user_id').size()
    res['devices_per_user']={'mean':float(dpu.mean()),'median':float(dpu.median()),'p90':float(dpu.quantile(0.9)),'p95':float(dpu.quantile(0.95)),'max':int(dpu.max())}
    res['users_multi_devices']=int((dpu>1).sum())
    res['users_total_with_device']=int(dpu.shape[0])
with open(os.path.join(OUT,'devices_extra.json'),'w',encoding='utf-8') as f:
    json.dump(res,f,ensure_ascii=False,indent=2)
print('ok')
