import os

for root, _, files in os.walk('D:/AccessReaper-v2/backend/app'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    l = line.strip()
                    if 'gemini' in l.lower() and not l.startswith('#') and not l.startswith('"""') and not l.startswith("'''"):
                        print(f"{f}:{i} {l[:90]}")
