import json
out = {}
for f in ['users.csv','subscribe.csv','orders.csv','transactions.csv','proxy_user_connection_logs.csv']:
    d=open('data/'+f,encoding='utf-8-sig',errors='ignore').readline().strip()
    s=open('data/db_structure/'+f,encoding='utf-8-sig',errors='ignore').readline().strip()
    out[f] = {'data_first': d[:300], 'schema_first': s[:300]}
with open('analysis/output/headers.json','w',encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print('ok')
