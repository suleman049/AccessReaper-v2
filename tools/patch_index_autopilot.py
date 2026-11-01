with open(r"D:\AccessReaper-v2\frontend\index.html", "r", encoding="utf-8") as f:
    text = f.read()

target = '<script src="notifications-settings.js"></script><script src="app.js"></script>'
replacement = '<script src="notifications-settings.js"></script><script src="autopilot-settings.js"></script><script src="app.js"></script>'

assert target in text, "target not found in index.html"
text = text.replace(target, replacement)
with open(r"D:\AccessReaper-v2\frontend\index.html", "w", encoding="utf-8") as f:
    f.write(text)
print("SUCCESS: added autopilot-settings.js to index.html")
