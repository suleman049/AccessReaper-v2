import os

def replace_in_file(file_path, replacements):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            modified = True
            print(f"Replaced: '{old}' -> '{new}' in {os.path.basename(file_path)}")
        else:
            print(f"Not found: '{old}' in {os.path.basename(file_path)}")
            
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Saved {file_path}")

gov_path = r'D:\AccessReaper-v2\frontend\governance.js'
gov_replacements = [
    ("<span>Local DRY_RUN state</span>", "<span>Live Enforced (payhive-eng)</span>"),
    ("DRY_RUN: finding dismissed; comment saved.", "Finding dismissed; decision recorded."),
    ("DRY_RUN: access revoked; comment saved.", "Access revoked on GitHub; decision recorded."),
    ("DRY_RUN: sample permission updated; comment saved.", "Permission updated on GitHub; decision recorded."),
    ("The sample policy check found no mismatch", "The policy check found no mismatch"),
    ("Not recorded in legacy sample", "Direct GitHub Organization Grant"),
    ("The sample audit could not finish. Try running it again.", "The audit could not finish. Try running it again."),
    ("Sample assignments, audits and decisions restored.", "Workspace data refreshed from live GitHub."),
]
replace_in_file(gov_path, gov_replacements)

app_path = r'D:\AccessReaper-v2\frontend\app.js'
app_replacements = [
    ("Your saved sample records have not been changed. Try loading the view again.", "Your records have not been changed. Try reloading the view."),
]
replace_in_file(app_path, app_replacements)
print("Finished UI cleanup.")
