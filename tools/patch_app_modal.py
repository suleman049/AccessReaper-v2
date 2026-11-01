import os

app_path = r'D:\AccessReaper-v2\frontend\app.js'
with open(app_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
inserted_tab = False
inserted_detected = False

for i, line in enumerate(lines):
    if "if(b.id==='btn-open-request-modal'){" in line:
        tab_code = """  if(b.id==='tab-existing-user'||b.id==='tab-new-user'){
    const isNew = b.id==='tab-new-user';
    const tabExist = document.querySelector('#tab-existing-user');
    const tabNew = document.querySelector('#tab-new-user');
    const secExist = document.querySelector('#section-existing-user');
    const secNew = document.querySelector('#section-new-user');
    if(tabExist && tabNew && secExist && secNew){
      tabExist.style.background = isNew ? 'transparent' : '#ff4d1f';
      tabExist.style.color = isNew ? 'var(--text, #334155)' : '#fff';
      tabNew.style.background = isNew ? '#ff4d1f' : 'transparent';
      tabNew.style.color = isNew ? '#fff' : 'var(--text, #334155)';
      secExist.style.display = isNew ? 'none' : 'block';
      secNew.style.display = isNew ? 'block' : 'none';
    }
  }

"""
        new_lines.append(tab_code)
        inserted_tab = True

    new_lines.append(line)

    if "bootstrap.Modal.getOrCreateInstance(document.querySelector('#request-modal')).show();" in line and not inserted_detected:
        # We want to insert the detected population right BEFORE showing the modal!
        pass

content = "".join(new_lines)

old_modal_show = "bootstrap.Modal.getOrCreateInstance(document.querySelector('#request-modal')).show();"
new_modal_show = """    const detectedWrapper = document.querySelector('#req-detected-wrapper');
    const detectedSelect = document.querySelector('#req-detected-select');
    const unmapped = window.unmatchedGitHubAccounts || (window.GitHubSettings && window.GitHubSettings.unmatched) || [];
    if(detectedWrapper && detectedSelect){
      if(unmapped.length > 0){
        detectedWrapper.style.display = 'block';
        detectedSelect.innerHTML = '<option value="">-- Choose detected GitHub collaborator --</option>' +
          unmapped.map(u => `<option value="${safe(u.login)}">@${safe(u.login)} (${safe(Array.isArray(u.repos) && u.repos.length ? u.repos.join(', ') : 'Collaborator')})</option>`).join('');
      } else {
        detectedWrapper.style.display = 'none';
      }
    }

    bootstrap.Modal.getOrCreateInstance(document.querySelector('#request-modal')).show();"""

if old_modal_show in content:
    content = content.replace(old_modal_show, new_modal_show, 1)

# Add change listener if not already there
change_listener = """
document.addEventListener('change', e => {
  if (e.target && e.target.id === 'req-detected-select') {
    const val = e.target.value;
    if (val) {
      const ghInput = document.querySelector('#req-github-input');
      const nameInput = document.querySelector('#req-new-name-input');
      const emailInput = document.querySelector('#req-new-email-input');
      if (ghInput) ghInput.value = val;
      if (nameInput && !nameInput.value) nameInput.value = val;
      if (emailInput && !emailInput.value) emailInput.value = `${val}@payhive.internal`;
    }
  }
});
"""

if "req-detected-select" not in content or "addEventListener('change'" not in content:
    content += change_listener

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: patch_app_modal completed.")
