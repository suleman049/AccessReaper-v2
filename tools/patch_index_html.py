path = r"D:\AccessReaper-v2\frontend\index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add notification bell to topbar-actions
target_topbar = '<button class="icon-button top-search header-search"'
replacement_topbar = """<div class="notification-wrap" id="notification-wrap"><button class="icon-button notification-button" id="notification-bell" aria-label="Notifications" aria-expanded="false" title="Notifications"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg><span class="notification-badge" id="notification-unread-count" style="display:none;">0</span></button><div class="notification-panel d-none" id="notification-panel" role="dialog" aria-label="Notifications"><div class="notification-header"><strong>Notifications</strong><button type="button" class="text-link" id="mark-all-notifications-read" style="font-size:12px;cursor:pointer;">Mark all read</button></div><div class="notification-list" id="notification-list"></div></div></div><button class="icon-button top-search header-search\""""

if target_topbar in content and "notification-bell" not in content:
    content = content.replace(target_topbar, replacement_topbar, 1)
    print("Added notification bell to index.html")

# 2. Add scripts
target_scripts = '<script src="github-settings.js"></script><script src="app.js"></script>'
replacement_scripts = '<script src="github-settings.js"></script><script src="notifications-center.js"></script><script src="notifications-settings.js"></script><script src="app.js"></script>'

if target_scripts in content and "notifications-center.js" not in content:
    content = content.replace(target_scripts, replacement_scripts, 1)
    print("Added notifications scripts to index.html")

with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(content)
print("index.html update finished.")
