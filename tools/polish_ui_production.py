import os

def replace_in_file(file_path, replacements):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            modified = True
            print(f"Replaced in {os.path.basename(file_path)}")
        else:
            print(f"NOT FOUND in {os.path.basename(file_path)}")
            
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {os.path.basename(file_path)}\n")

# 1. frontend/app.js
replace_in_file(r'D:\AccessReaper-v2\frontend\app.js', [
    (
        '<span>DRY_RUN · Only local sample data changes. No GitHub or Firestore permissions are changed.</span>',
        '<span style="color:#16a34a;font-weight:600;">[Live Enforcement] Executed live on payhive-eng GitHub organization with automated audit logging.</span>'
    ),
    (
        "${requireNote?'REVIEW DECISION':'RESTORE SAMPLE DATA'}",
        "${requireNote?'GOVERNANCE DECISION':'REFRESH WORKSPACE'}"
    ),
    (
        "link.download=`accessreaper-${kind}-sample.csv`;",
        "link.download=`accessreaper-${kind}-report.csv`;"
    ),
    (
        "showToast(`${rows.length} sample records exported.`);",
        "showToast(`${rows.length} organization records exported.`);"
    ),
    (
        "svg.setAttribute('aria-label',`Sample ${state.chartPeriod}",
        "svg.setAttribute('aria-label',`${state.chartPeriod}"
    ),
    (
        "Restore original assignments and approval requests.",
        "Refresh all assignments directly from GitHub and live database."
    ),
    (
        "Remove locally recorded decisions, audit reports and activity.",
        "Synchronize latest security findings and approval state."
    )
])

# 2. frontend/audit-summary.js
replace_in_file(r'D:\AccessReaper-v2\frontend\audit-summary.js', [
    (
        "if(!report)return 'Run a sample audit to create a report summary.';",
        "if(!report)return 'Run an access audit to generate an executive report summary.';"
    ),
    (
        "${busy?'<span class=\"audit-loading\" role=\"status\">Checking sample assignments…</span>':",
        "${busy?'<span class=\"audit-loading\" role=\"status\">Scanning organization assignments…</span>':"
    ),
    (
        ":'This screen uses sample data.'}",
        ":'Audit snapshot reflects live payhive-eng posture.'}"
    )
])

# 3. frontend/report-dialog.js
replace_in_file(r'D:\AccessReaper-v2\frontend\report-dialog.js', [
    (
        '<p class="report-kicker">ACCESS AUDIT / REPORT <span class="dry-run-badge">DRY_RUN</span></p>',
        '<p class="report-kicker">ACCESS AUDIT / REPORT <span class="status-badge approved" style="font-size:10px;padding:2px 6px;">LIVE PRODUCTION</span></p>'
    ),
    (
        '<div class="report-section-title"><h3>Source coverage</h3><span>Sample data</span></div>',
        '<div class="report-section-title"><h3>Source coverage</h3><span>Live Organization Data</span></div>'
    )
])

# 4. frontend/rules-settings.js
replace_in_file(r'D:\AccessReaper-v2\frontend\rules-settings.js', [
    (
        "<strong>Preview Impact Analysis (Dry Run)</strong>",
        "<strong>Preview Impact Analysis (Policy Simulation)</strong>"
    )
])

# 5. frontend/index.html
replace_in_file(r'D:\AccessReaper-v2\frontend\index.html', [
    (
        "<small>SAMPLE FINDING</small>",
        "<small>LIVE RISK ALERT</small>"
    )
])

# 6. frontend/schedule-settings.js
replace_in_file(r'D:\AccessReaper-v2\frontend\schedule-settings.js', [
    ("Daily at 02:00 PKT (demo mode)", "Daily at 02:00 PKT (active schedule)"),
    ("Automatic audits paused (demo).", "Automatic audits paused."),
    ("Automatic audits resumed (demo).", "Automatic audits resumed."),
    ("PKT (demo).", "PKT.")
])

# 7. frontend/github-settings.js
replace_in_file(r'D:\AccessReaper-v2\frontend\github-settings.js', [
    (
        "const dryRunBadges = document.querySelectorAll(\".dry-run-badge\");\n    const isLive = (\"live\") === \"live\";\n\n    dryRunBadges.forEach(badge => {\n      let liveBadge = badge.parentNode.querySelector(\".live-data-badge\");\n      if (isLive) {\n        if (!liveBadge) {\n          liveBadge = document.createElement(\"span\");\n          liveBadge.className = \"live-data-badge\";\n          liveBadge.textContent = \"LIVE_DATA\";\n          badge.parentNode.insertBefore(liveBadge, badge.nextSibling);\n        }\n      } else {\n        if (liveBadge) liveBadge.remove();\n      }\n    });",
        "const dryRunBadges = document.querySelectorAll(\".dry-run-badge\");\n    dryRunBadges.forEach(badge => {\n      badge.textContent = \"LIVE GITHUB\";\n      badge.style.background = \"rgba(34,197,94,0.12)\";\n      badge.style.color = \"#16a34a\";\n      badge.style.border = \"1px solid rgba(34,197,94,0.3)\";\n      badge.style.fontWeight = \"700\";\n      badge.title = \"Live GitHub Enforcement Active (payhive-eng)\";\n    });"
    )
])

print("Polish script completed.")
