path = r'D:\AccessReaper-v2\backend\app\schemas\iam.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

target = '    durationHours: int | None = None'
replacement = '    durationHours: float | None = None'

c_norm = c.replace('\r\n', '\n')
assert target in c_norm, "Target not found"
c_new = c_norm.replace(target, replacement, 1)

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c_new)

print("SUCCESS: patched iam.py ApprovalSchema.durationHours")
