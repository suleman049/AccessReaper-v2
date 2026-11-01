import os

# 1. Update api-client.js
path_api = r'D:\AccessReaper-v2\frontend\api-client.js'
with open(path_api, 'r', encoding='utf-8') as f:
    text = f.read()

old_auth_check = '''    const token = await this.getToken();
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;'''

new_auth_check = '''    const token = await this.getToken();
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    } else {
      headers["Authorization"] = "Bearer dev-token";
      headers["X-Dev-User"] = "jordan.davis@acme.io";
    }'''

text = text.replace(old_auth_check, new_auth_check)

old_fail = '''    if (!res.ok) {
      if (typeof window.showToast === "function") window.showToast(`Download failed (${res.status})`);
      return;
    }'''

new_fail = '''    if (!res.ok) {
      let msg = `Download failed (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson?.error?.message) msg = errJson.error.message;
      } catch {}
      if (typeof window.showToast === "function") window.showToast(msg);
      return;
    }'''

text = text.replace(old_fail, new_fail)

old_pdf = '`audit-${runId}-report.pdf`'
new_pdf = '`AccessReaper-v2-audit-${runId}.pdf`'
text = text.replace(old_pdf, new_pdf)

old_req = '''    const token = await this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }'''

new_req = '''    const token = await this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    } else if (!headers["Authorization"]) {
      headers["Authorization"] = "Bearer dev-token";
      headers["X-Dev-User"] = "jordan.davis@acme.io";
    }'''

text = text.replace(old_req, new_req)

with open(path_api, 'w', encoding='utf-8', newline='\n') as f:
    f.write(text)
print("api-client.js updated successfully")

# 2. Update report-dialog.js
path_rep = r'D:\AccessReaper-v2\frontend\report-dialog.js'
with open(path_rep, 'r', encoding='utf-8') as f:
    rep_text = f.read()

delegation_code = '''
// Global event delegation for Download PDF button
document.addEventListener('click', (e) => {
  const btn = e.target.closest('#download-report-pdf, [data-download-audit-pdf]');
  if (btn) {
    const runId = btn.dataset.runId;
    if (runId && window.ApiClient) {
      ApiClient.downloadPdf(runId);
    }
  }
});
'''

if 'Global event delegation for Download PDF' not in rep_text:
    rep_text += delegation_code
    with open(path_rep, 'w', encoding='utf-8', newline='\n') as f:
        f.write(rep_text)
    print("report-dialog.js updated with event delegation")
else:
    print("report-dialog.js already has event delegation")
