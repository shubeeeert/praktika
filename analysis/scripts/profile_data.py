import pandas as pd, os, glob, json

files = sorted(glob.glob('data/*.csv'))
info = []
for f in files:
    try:
        df = pd.read_csv(f, sep=';', nrows=3, dtype=str)
        size = os.path.getsize(f)
        info.append({
            'file': os.path.basename(f),
            'size': size,
            'cols': list(df.columns),
            'sample': df.head(1).to_dict(orient='records')[0]
        })
    except Exception as e:
        info.append({'file': os.path.basename(f), 'size': os.path.getsize(f), 'error': str(e)})

with open('analysis/output/profile.json', 'w', encoding='utf-8') as out:
    json.dump(info, out, ensure_ascii=False, indent=2)

for i in info:
    if 'error' in i:
        print(f"{i['file']}\tERR\t{i['error']}")
    else:
        print(f"{i['file']}\t{i['size']}\t{len(i['cols'])}\t{'|'.join(i['cols'][:12])}")
