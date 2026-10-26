# -*- coding: utf-8 -*-
import os, json, hashlib
LOCK = r'D:\ai manager\LOCKED'
BASE = r'D:\ai manager'
def sha256(p):
    import hashlib
    h = hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(65536), b''): h.update(c)
    return h.hexdigest()
man = json.load(open(os.path.join(LOCK,'MANIFEST.json'), encoding='utf-8'))
bad = []
for rel, info in man['files'].items():
    cur = os.path.join(BASE, rel)
    if not os.path.isfile(cur):
        bad.append((rel, 'MISSING'))
    else:
        if sha256(cur) != info['sha256']:
            bad.append((rel, 'CHANGED'))
if not bad:
    print('OK - all locked engine files are intact')
else:
    print('WARNING - some locked files differ:')
    for r, why in bad:
        print('  ', why, r)
