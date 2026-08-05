

import re, sys

_fn_pattern = re.compile(
    r'\s*(def\s|async\s+def\s|function\s+\w|async\s+function\s+\w'
    r'|export\s+(?:default\s+)?(?:async\s+)?function\s+\w|class\s+\w)'
)

files_to_check = [
    'api/services/chat_service.py',
    'api/models/chat.py',
    'frontend/app/repo/[id]/page.tsx',
    'frontend/app/repo/[id]/chat/page.tsx',
]

all_ok = True
for fname in files_to_check:
    try:
        with open(fname, encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f'MISSING: {fname}')
        continue
    
    start = None
    detections = []
    for idx, line in enumerate(lines):
        if _fn_pattern.match(line):
            start = idx
        if start is not None and idx - start > 120 and line.strip() == '':
            detections.append(f'  span={idx-start} blank@{idx+1} def@{start+1}: {lines[start].strip()[:50]}')
            start = None
    
    if detections:
        all_ok = False
        print(f'LONG FUNCTIONS in {fname}:')
        for d in detections:
            print(d)
    else:
        print(f'OK: {fname}')

sys.exit(0 if all_ok else 1)

