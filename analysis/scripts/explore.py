import pandas as pd, json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

def show(name, sep=';', n=3):
    p=f'data/{name}'
    if not os.path.exists(p):
        print(f'== {name} MISSING'); return
    df=pd.read_csv(p, sep=sep, dtype=str, keep_default_na=False)
    print(f'\n== {name} rows={len(df)} cols={list(df.columns)}')
    print(df.head(n).to_string(index=False))
    for c in df.columns:
        vc=df[c].value_counts().head(5)
        if len(vc)<=5 or df[c].nunique()<20:
            print(f'  {c}: nunique={df[c].nunique()} top={vc.to_dict()}')

for f in ['users.csv','subscribe.csv','orders.csv','transactions.csv','product.csv','product_trial.csv','product_periods.csv','product_period_discounts.csv','advertising_ids.csv','external_accounts.csv','device_code.csv','proxy_user_connection_logs.csv','task_history.csv','user_blocks.csv','referral_history.csv','saved_payment_methods.csv','nodes.csv','locations.csv','mobile_version.csv']:
    show(f)
