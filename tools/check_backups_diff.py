import filecmp
import os

files = [
    "app.js",
    "workspace-design.js",
    "styles.css",
    "dark-theme.css",
    "index.html",
    "review-workbenches.css",
    "phase2.css",
]

for f in files:
    orig = os.path.join(r"D:\AccessReaper-v2\frontend", f)
    backup = os.path.join(r"D:\AccessReaper-v2\frontend", f + ".backup")
    if os.path.exists(backup):
        match = filecmp.cmp(orig, backup, shallow=False)
        print(f"{f}: {'MATCHES BACKUP EXACTLY' if match else 'DIFFERENT'}")
    else:
        print(f"{f}: NO BACKUP FOUND")
