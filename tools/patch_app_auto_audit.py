path_app = r'D:\AccessReaper-v2\frontend\app.js'
with open(path_app, 'r', encoding='utf-8') as f:
    c = f.read()

target = 'await ApiClient.runAudit();'
replacement = 'await ApiClient.triggerAutoAudit();'

c_norm = c.replace('\r\n', '\n')
assert target in c_norm, "Target not found"
c_new = c_norm.replace(target, replacement, 1)

with open(path_app, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c_new)

print("SUCCESS: patched app.js ApiClient.triggerAutoAudit")
