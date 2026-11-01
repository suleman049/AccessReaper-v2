with open(r'D:\AccessReaper-v2\frontend\github-settings.js', 'r', encoding='utf-8') as f:
    c = f.read()

old_block = '''          <div class="gh-actions-bar">
            <button class="btn btn-sm btn-outline text-danger" id="btn-gh-disconnect">Disconnect</button>
            <button class="btn btn-sm btn-primary" id="btn-gh-datamode">Data mode: <strong>${currentMode.toUpperCase()}</strong></button>'''

new_block = '''          <div class="gh-actions-bar">
            <button class="btn btn-sm btn-outline text-danger" id="btn-gh-disconnect">Disconnect</button>
            <span class="badge bg-success text-white" style="font-size: 11px; padding: 6px 10px; border-radius: 6px; font-weight: 700; display: inline-flex; align-items: center; gap: 5px;">
              <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#fff;"></span>
              Mode: LIVE PRODUCTION
            </span>'''

# Normalize newlines
c_norm = c.replace('\r\n', '\n')
old_norm = old_block.replace('\r\n', '\n')
new_norm = new_block.replace('\r\n', '\n')

if old_norm in c_norm:
    c_norm = c_norm.replace(old_norm, new_norm, 1)
    with open(r'D:\AccessReaper-v2\frontend\github-settings.js', 'w', encoding='utf-8') as f:
        f.write(c_norm)
    print("SUCCESS: Updated github-settings.js data mode badge!")
else:
    print("ERROR: old_block not found in github-settings.js")
