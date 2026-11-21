import pandas as pd, numpy as np, json, os, glob, warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(BASE, 'data')
OUT = os.path.join(BASE, 'analysis', 'output')
os.makedirs(OUT, exist_ok=True)

def schema_cols(name):
    p = os.path.join(DATA, 'db_structure', name)
    if not os.path.exists(p):
        return None
    line = open(p, encoding='utf-8-sig').readline().strip()
    return [c.strip() for c in line.split(';') if c.strip()]

def load(name, usecols=None, parse_dates=None, dtype=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        print(f'SKIP {name} (missing)')
        return None
    cols = schema_cols(name)
    try:
        df = pd.read_csv(p, sep=';', header=None, names=cols, dtype=dtype, usecols=usecols,
                         keep_default_na=True, na_values=['', 'NULL', 'null', 'None'], encoding='utf-8-sig', low_memory=False)
    except Exception as e:
        print(f'ERR {name}: {e}')
        return None
    if parse_dates:
        for c in parse_dates:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors='coerce', utc=True)
    print(f'OK {name}: {len(df)} rows')
    return df

results = {}

# ---------- Load core tables ----------
users = load('users.csv', dtype=str)
subscribe = load('subscribe.csv', dtype=str, parse_dates=['expired_time','created_at','disabled_at'])
orders = load('orders.csv', dtype=str, parse_dates=['created_at','updated_at'])
transactions = load('transactions.csv', dtype=str, parse_dates=['created_at','updated_at'])
product = load('product.csv', dtype=str)
product_trial = load('product_trial.csv', dtype=str)
product_periods = load('product_periods.csv', dtype=str)
adv_ids = load('advertising_ids.csv', dtype=str, parse_dates=['created_at'])
external = load('external_accounts.csv', dtype=str, parse_dates=['created_at'])
device_code = load('device_code.csv', dtype=str, parse_dates=['accepted_at','used_at','expires_at','created_at'])
proxy_logs = load('proxy_user_connection_logs.csv', dtype=str, parse_dates=['created_at'])
task_history = load('task_history.csv', dtype=str, parse_dates=['created_at'])
user_blocks = load('user_blocks.csv', dtype=str)
ref_history = load('referral_history.csv', dtype=str, parse_dates=['created_at'])
ref_used = load('referral_code_used.csv', dtype=str, parse_dates=['created_at'])
saved_pm = load('saved_payment_methods.csv', dtype=str, parse_dates=['created_at'])
nodes = load('nodes.csv', dtype=str)
locations = load('locations.csv', dtype=str)

# numeric conversions
for df, cols in [(orders,['amount']),(transactions,['amount']),(product,['amount'])]:
    if df is None: continue
    for c in cols:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
if users is not None:
    for c in ['is_verified','is_was_guest','beta_tester']:
        if c in users.columns: users[c] = users[c].map({'t':True,'f':False,'true':True,'false':False})
    for c in ['created_at','updated_at','deleted_at','logout_at','trial_used_at']:
        if c in users.columns: users[c] = pd.to_datetime(users[c], errors='coerce', utc=True)
    if 'referal_balance' in users.columns: users['referal_balance'] = pd.to_numeric(users['referal_balance'], errors='coerce')
if subscribe is not None:
    for c in ['pre_payment','pre_payment_notification']:
        if c in subscribe.columns: subscribe[c] = subscribe[c].map({'t':True,'f':False})
if orders is not None:
    for c in ['pre_payment','trial']:
        if c in orders.columns: orders[c] = orders[c].map({'t':True,'f':False})

# ---------- General overview ----------
overview = {}
if users is not None:
    overview['users_total'] = int(len(users))
    overview['users_by_role'] = users['role'].value_counts(dropna=False).to_dict() if 'role' in users.columns else {}
    overview['verified'] = int(users['is_verified'].sum()) if 'is_verified' in users.columns else None
    overview['guest'] = int((users['role']=='guest').sum()) if 'role' in users.columns else None
    overview['trial_used'] = int(users['trial_used_at'].notna().sum()) if 'trial_used_at' in users.columns else None
    overview['created_min'] = str(users['created_at'].min())
    overview['created_max'] = str(users['created_at'].max())
if orders is not None:
    overview['orders_total'] = int(len(orders))
    overview['orders_by_status'] = orders['status'].value_counts(dropna=False).to_dict()
    overview['orders_trial'] = int(orders['trial'].sum()) if 'trial' in orders.columns else None
if subscribe is not None:
    overview['subscriptions_total'] = int(len(subscribe))
    overview['subscriptions_by_product'] = subscribe['product_id'].value_counts(dropna=False).to_dict()
if transactions is not None:
    overview['transactions_total'] = int(len(transactions))
    overview['transactions_by_status'] = transactions['status'].value_counts(dropna=False).to_dict()
results['overview'] = overview

# ---------- Hypothesis 1: trial abuse / multiple accounts ----------
h1 = {'title':'Повторная регистрация для использования триала'}
if users is not None:
    # trial users
    trial_users = users[users['trial_used_at'].notna()].copy() if 'trial_used_at' in users.columns else users.iloc[0:0].copy()
    h1['trial_used_users'] = int(len(trial_users))
    # same advertising_id linked to multiple users? advertising_ids is user_id->? schema: id;user_id;created_at? wait check
    if adv_ids is not None:
        # inspect columns
        h1['adv_ids_cols'] = list(adv_ids.columns)
        h1['adv_ids_rows'] = int(len(adv_ids))
        # common patterns: if has advertising_id column
        for cand in ['advertising_id','ad_id','idfa','gaid','device_id']:
            if cand in adv_ids.columns:
                dup = adv_ids.groupby(cand)['user_id'].nunique()
                multi = dup[dup>1]
                h1[f'multi_users_per_{cand}'] = int(len(multi))
                h1[f'max_users_per_{cand}'] = int(multi.max()) if len(multi) else 0
                break
        # also check if id itself is advertising id and user_id maps
        if 'user_id' in adv_ids.columns:
            # first column may be id/ad id
            idcol = [c for c in adv_ids.columns if c!='user_id' and c!='created_at'][0] if any(c not in ['user_id','created_at'] for c in adv_ids.columns) else None
            if idcol:
                dup = adv_ids.groupby(idcol)['user_id'].nunique()
                multi = dup[dup>1]
                h1['adid_col'] = idcol
                h1['multi_user_adids'] = int(len(multi))
                h1['multi_user_adids_share'] = float(len(multi)/dup.shape[0]) if dup.shape[0] else 0
                h1['max_users_per_adid'] = int(multi.max()) if len(multi) else 0
                top = multi.sort_values(ascending=False).head(10)
                h1['top_adids_multi'] = top.to_dict()
    # external accounts: same external id across users?
    if external is not None:
        h1['external_cols'] = list(external.columns)
        h1['external_rows'] = int(len(external))
        # heuristic: columns might include provider, external_id, user_id
        ext_id_col = None
        for c in external.columns:
            if 'external' in c.lower() or c.lower() in ['id_external','account_id','provider_user_id']:
                ext_id_col = c
        if ext_id_col is None and 'user_id' in external.columns:
            # pick non-user_id, non-created_at, non-id
            cands = [c for c in external.columns if c not in ['id','user_id','created_at','updated_at']]
            if cands: ext_id_col = cands[0]
        h1['external_id_col_guess'] = ext_id_col
        if ext_id_col and 'user_id' in external.columns:
            dup = external.groupby(ext_id_col)['user_id'].nunique()
            multi = dup[dup>1]
            h1['multi_user_external_ids'] = int(len(multi))
            h1['max_users_per_external'] = int(multi.max()) if len(multi) else 0
    # device_code: same device used by multiple accepted_by_user_id
    if device_code is not None:
        h1['device_code_cols'] = list(device_code.columns)
        if 'device_id' in device_code.columns and 'accepted_by_user_id' in device_code.columns:
            dc = device_code.dropna(subset=['device_id','accepted_by_user_id'])
            dup = dc.groupby('device_id')['accepted_by_user_id'].nunique()
            multi = dup[dup>1]
            h1['multi_user_devices_via_code'] = int(len(multi))
            h1['max_users_per_device_code'] = int(multi.max()) if len(multi) else 0
    # users with same referrer patterns / many accounts from same email domain patterns? guest users
    if 'role' in users.columns:
        guests = users[users['role']=='guest']
        h1['guest_users'] = int(len(guests))
        h1['guest_share'] = float(len(guests)/len(users))
        if 'trial_used_at' in users.columns:
            h1['guest_trial_used'] = int(guests['trial_used_at'].notna().sum())
    # email domain analysis among non-guest
    if 'email' in users.columns and 'role' in users.columns:
        real = users[users['role']!='guest'].copy()
        real['domain'] = real['email'].str.extract(r'@(.+)$')[0].str.lower()
        h1['top_domains_real'] = real['domain'].value_counts().head(15).to_dict()
results['hypothesis_1_trial_abuse'] = h1

# ---------- Hypothesis 2: free tariff traffic limits ----------
h2 = {'title':'Оптимальные лимиты трафика для бесплатного тарифа'}
if product is not None:
    h2['products'] = product.to_dict(orient='records')
if product_periods is not None:
    h2['product_periods_cols'] = list(product_periods.columns)
    h2['product_periods_rows'] = product_periods.head(20).to_dict(orient='records')
if proxy_logs is not None:
    h2['proxy_logs_cols'] = list(proxy_logs.columns)
    h2['proxy_logs_rows'] = int(len(proxy_logs))
    # analyze usage by subscribe/product through subscribe table
    if subscribe is not None and 'subscribe_id' in proxy_logs.columns:
        sub_prod = subscribe[['id','user_id','product_id']].drop_duplicates('id')
        pl = proxy_logs.merge(sub_prod, left_on='subscribe_id', right_on='id', how='left', suffixes=('','_sub'))
        pl['date'] = pl['created_at'].dt.date
        h2['proxy_logs_with_product'] = int(pl['product_id'].notna().sum())
        # connections per user per day by product
        daily = pl.groupby(['user_id','date','product_id']).size().reset_index(name='connections')
        for pid in daily['product_id'].dropna().unique():
            d = daily[daily['product_id']==pid]['connections']
            h2[f'product_{pid}_daily_conn'] = {'mean':float(d.mean()),'median':float(d.median()),'p90':float(d.quantile(0.9)),'p95':float(d.quantile(0.95)),'max':int(d.max())}
        # also overall per user per day
        daily_u = pl.groupby(['user_id','date']).size().reset_index(name='connections')
        h2['daily_conn_overall'] = {'mean':float(daily_u['connections'].mean()),'median':float(daily_u['connections'].median()),'p90':float(daily_u['connections'].quantile(0.9)),'p95':float(daily_u['connections'].quantile(0.95))}
        # monthly
        pl['month'] = pl['created_at'].dt.to_period('M').astype(str)
        monthly = pl.groupby(['user_id','month','product_id']).size().reset_index(name='connections')
        for pid in monthly['product_id'].dropna().unique():
            m = monthly[monthly['product_id']==pid]['connections']
            h2[f'product_{pid}_monthly_conn'] = {'mean':float(m.mean()),'median':float(m.median()),'p90':float(m.quantile(0.9)),'p95':float(m.quantile(0.95)),'max':int(m.max())}
    # free/basic product id guess
    if product is not None:
        h2['note'] = 'Connection logs do not contain traffic bytes; analysis uses connection counts as proxy. Product 1 appears to be Basic/Free by naming.'
# also check adv_view_history for ad-for-limit extension
if os.path.exists(os.path.join(DATA,'adv_view_history.csv')):
    av = load('adv_view_history.csv', dtype=str, parse_dates=['created_at'])
    if av is not None:
        h2['adv_views_total'] = int(len(av))
        h2['adv_views_users'] = int(av['user_id'].nunique()) if 'user_id' in av.columns else None
        av['date'] = av['created_at'].dt.date
        per_user_day = av.groupby(['user_id','date']).size()
        h2['adv_per_user_day'] = {'mean':float(per_user_day.mean()),'median':float(per_user_day.median()),'p90':float(per_user_day.quantile(0.9)),'max':int(per_user_day.max())}
        per_user_month = av.groupby(['user_id', av['created_at'].dt.to_period('M').astype(str)]).size()
        h2['adv_per_user_month'] = {'mean':float(per_user_month.mean()),'median':float(per_user_month.median()),'p90':float(per_user_month.quantile(0.9)),'max':int(per_user_month.max())}
else:
    h2['adv_view_history'] = 'not downloaded yet'
results['hypothesis_2_traffic_limits'] = h2

# ---------- Hypothesis 3: time to purchase, trial path ----------
h3 = {'title':'Путь до покупки: триал, бесплатный тариф, конверсия'}
if users is not None and orders is not None:
    paid_orders = orders[orders['status']=='paid'].copy()
    h3['paid_orders'] = int(len(paid_orders))
    h3['paid_trial_orders'] = int(paid_orders['trial'].sum()) if 'trial' in paid_orders.columns else None
    h3['paid_nontrial_orders'] = int((~paid_orders['trial']).sum()) if 'trial' in paid_orders.columns else None
    # first paid order per user
    first_paid = paid_orders.sort_values('created_at').groupby('user_id').first().reset_index()
    h3['users_with_paid_order'] = int(first_paid['user_id'].nunique())
    # join with users
    u = users[['id','created_at','trial_used_at','role']].copy()
    u = u.rename(columns={'id':'user_id','created_at':'user_created_at'})
    fp = first_paid.merge(u, on='user_id', how='left')
    fp['days_to_first_paid'] = (fp['created_at'] - fp['user_created_at']).dt.total_seconds()/86400
    d = fp['days_to_first_paid'].dropna()
    d = d[d>=0]
    h3['days_to_first_paid'] = {'mean':float(d.mean()),'median':float(d.median()),'p25':float(d.quantile(0.25)),'p75':float(d.quantile(0.75)),'p90':float(d.quantile(0.9))}
    # trial vs no trial at first paid
    if 'trial' in fp.columns:
        t = fp[fp['trial']==True]
        nt = fp[fp['trial']==False]
        h3['first_paid_is_trial'] = int(len(t))
        h3['first_paid_not_trial'] = int(len(nt))
        for label, sub in [('trial',t),('nontrial',nt)]:
            dd = sub['days_to_first_paid'].dropna()
            dd = dd[dd>=0]
            if len(dd):
                h3[f'days_to_first_paid_{label}'] = {'mean':float(dd.mean()),'median':float(dd.median()),'p75':float(dd.quantile(0.75))}
    # users who bought without ever using trial
    if 'trial_used_at' in fp.columns:
        no_trial_ever = fp[fp['trial_used_at'].isna()]
        h3['paid_users_never_used_trial'] = int(len(no_trial_ever))
        h3['paid_users_never_used_trial_share'] = float(len(no_trial_ever)/len(fp)) if len(fp) else None
    # conversion among users created in period
    h3['total_users'] = int(len(users))
    h3['paid_user_share'] = float(len(fp)/len(users))
    # time from trial_used_at to first paid
    if 'trial_used_at' in fp.columns:
        fp2 = fp[fp['trial_used_at'].notna()].copy()
        fp2['days_trial_to_paid'] = (fp2['created_at'] - fp2['trial_used_at']).dt.total_seconds()/86400
        dd = fp2['days_trial_to_paid'].dropna()
        h3['days_trial_to_paid'] = {'mean':float(dd.mean()),'median':float(dd.median()),'p75':float(dd.quantile(0.75)),'p90':float(dd.quantile(0.9))}
        h3['bought_after_trial_same_day_or_before'] = int((dd<=0).sum())
results['hypothesis_3_conversion_path'] = h3

# ---------- Hypothesis 4: incident/error patterns ----------
h4 = {'title':'Паттерны в логах инцидентов'}
if task_history is not None:
    h4['task_history_rows'] = int(len(task_history))
    h4['task_history_cols'] = list(task_history.columns)
    for c in task_history.columns:
        if task_history[c].nunique() < 100:
            h4[f'task_history_{c}_top'] = task_history[c].value_counts(dropna=False).head(20).to_dict()
    # errors
    err_cols = [c for c in task_history.columns if 'error' in c.lower() or 'status' in c.lower() or 'stage' in c.lower()]
    h4['error_like_cols'] = err_cols
    for c in err_cols:
        h4[f'{c}_values'] = task_history[c].value_counts(dropna=False).head(30).to_dict()
# logs.zip not analyzed here; note
h4['logs_zip_note'] = 'logs.zip (4.7GB) is very large; analysis below covers task_history and available connection/transaction patterns. If logs.zip contains app incident logs, extract and run grep/count by error type, platform, app version.'
# transaction failures
if transactions is not None:
    h4['tx_status'] = transactions['status'].value_counts(dropna=False).to_dict()
    failed = transactions[transactions['status']=='failed']
    h4['tx_failed'] = int(len(failed))
    if 'created_at' in failed.columns:
        failed['hour'] = failed['created_at'].dt.hour
        h4['failed_tx_by_hour'] = failed['hour'].value_counts().sort_index().to_dict()
# orders failures
if orders is not None:
    h4['order_status'] = orders['status'].value_counts(dropna=False).to_dict()
    if 'provider_id' in orders.columns:
        h4['order_status_by_provider'] = orders.groupby(['provider_id','status']).size().unstack(fill_value=0).to_dict(orient='index')
results['hypothesis_4_incidents'] = h4

# ---------- Hypothesis 5: platform / device patterns ----------
h5 = {'title':'Платформы, устройства и поведение'}
if os.path.exists(os.path.join(DATA,'devices.csv')):
    # may still be partial; try loading
    try:
        dev = load('devices.csv', dtype=str, parse_dates=['last_seen','push_tokens_updated_at'])
        if dev is not None:
            h5['devices_rows'] = int(len(dev))
            h5['devices_cols'] = list(dev.columns)
            for c in ['client_type','os','brand','in_sub']:
                if c in dev.columns:
                    h5[f'devices_{c}'] = dev[c].value_counts(dropna=False).head(20).to_dict()
            if 'user_id' in dev.columns:
                dpu = dev.groupby('user_id').size()
                h5['devices_per_user'] = {'mean':float(dpu.mean()),'median':float(dpu.median()),'p90':float(dpu.quantile(0.9)),'max':int(dpu.max())}
                h5['users_with_multi_devices'] = int((dpu>1).sum())
    except Exception as e:
        h5['devices_error'] = str(e)
else:
    h5['devices'] = 'not downloaded yet'
if os.path.exists(os.path.join(DATA,'sessions.csv')):
    try:
        sess = load('sessions.csv', dtype=str, parse_dates=['created_at','last_accessed_at','revoked_at','expired_at'])
        if sess is not None:
            h5['sessions_rows'] = int(len(sess))
            h5['sessions_cols'] = list(sess.columns)
            if 'user_id' in sess.columns:
                spu = sess.groupby('user_id').size()
                h5['sessions_per_user'] = {'mean':float(spu.mean()),'median':float(spu.median()),'p90':float(spu.quantile(0.9)),'max':int(spu.max())}
    except Exception as e:
        h5['sessions_error'] = str(e)
else:
    h5['sessions'] = 'not downloaded yet'
results['hypothesis_5_platforms'] = h5

# ---------- Save ----------
with open(os.path.join(OUT,'analysis_results.json'),'w',encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print('SAVED analysis_results.json')
