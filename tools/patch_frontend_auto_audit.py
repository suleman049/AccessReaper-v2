# Patch frontend/api-client.js
path_api = r'D:\AccessReaper-v2\frontend\api-client.js'
with open(path_api, 'r', encoding='utf-8') as f:
    c = f.read()

target_api = """  async updateAutomationConfig(config) {
    return await this.request("/api/automation/config", {
      method: "PUT",
      body: config,
    });
  },"""

replacement_api = """  async updateAutomationConfig(config) {
    return await this.request("/api/automation/config", {
      method: "PUT",
      body: config,
    });
  },

  async triggerAutoAudit() {
    return await this.request("/api/automation/trigger", {
      method: "POST",
    });
  },"""

c_norm = c.replace('\r\n', '\n')
target_api_norm = target_api.replace('\r\n', '\n')
replacement_api_norm = replacement_api.replace('\r\n', '\n')

if target_api_norm in c_norm:
    c_new = c_norm.replace(target_api_norm, replacement_api_norm, 1)
    with open(path_api, 'w', encoding='utf-8', newline='\n') as f:
        f.write(c_new)
    print("SUCCESS: patched api-client.js")
else:
    print("WARNING: target_api not found")

# Patch frontend/app.js
path_app = r'D:\AccessReaper-v2\frontend\app.js'
with open(path_app, 'r', encoding='utf-8') as f:
    c = f.read()

target_app = """  if(b.id==='btn-trigger-auto-audit'){
    b.disabled = true;
    const origHtml = b.innerHTML;
    b.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" style="width:11px;height:11px;border-width:2px;margin-right:4px;"></span> Running…';
    (async () => {
      try {
        await ApiClient.runAudit();
        const data = await ApiClient.bootstrap();
        ApiClient.syncState(data);
        if (window.AutomationTimer) await AutomationTimer.fetchStatus();
        render();
        showToast("Automated IAM audit cycle completed successfully.");
      } catch (err) {
        showToast(err.message || "Could not execute automated audit.");
      } finally {
        b.disabled = false;
        b.innerHTML = origHtml;
      }
    })();
    return;
  }"""

replacement_app = """  if(b.id==='btn-trigger-auto-audit'){
    b.disabled = true;
    const origHtml = b.innerHTML;
    b.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" style="width:11px;height:11px;border-width:2px;margin-right:4px;"></span> Running…';
    (async () => {
      try {
        await ApiClient.triggerAutoAudit();
        const data = await ApiClient.bootstrap();
        ApiClient.syncState(data);
        if (window.AutomationTimer) await AutomationTimer.fetchStatus();
        render();
        showToast("Automated IAM audit cycle completed successfully.");
      } catch (err) {
        showToast(err.message || "Could not execute automated audit.");
      } finally {
        b.disabled = false;
        b.innerHTML = origHtml;
      }
    })();
    return;
  }"""

c_norm = c.replace('\r\n', '\n')
target_app_norm = target_app.replace('\r\n', '\n')
replacement_app_norm = replacement_app.replace('\r\n', '\n')

if target_app_norm in c_norm:
    c_new = c_norm.replace(target_app_norm, replacement_app_norm, 1)
    with open(path_app, 'w', encoding='utf-8', newline='\n') as f:
        f.write(c_new)
    print("SUCCESS: patched app.js")
else:
    print("WARNING: target_app not found")
