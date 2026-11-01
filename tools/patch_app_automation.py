with open(r"D:\AccessReaper-v2\frontend\app.js", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Float duration parsing in access-request-form
target_duration = "const duration_val = parseInt(document.querySelector('#req-duration-select')?.value || '0', 10);"
replacement_duration = "const duration_val = parseFloat(document.querySelector('#req-duration-select')?.value || '0');"
assert target_duration in text, "target_duration not found in app.js"
text = text.replace(target_duration, replacement_duration)

# 2. Live JIT table badge calculation (support seconds, minutes, days)
target_jit = """  if(p.isTemporary){
    let timeRemaining = 'JIT Lease';
    if(p.expiresAt){
      const msLeft = new Date(p.expiresAt).getTime() - Date.now();
      if(msLeft > 0){
        const hoursLeft = Math.round(msLeft / 3600000);
        timeRemaining = hoursLeft <= 48 ? `${hoursLeft}h left` : `${Math.round(hoursLeft/24)}d left`;
      } else {
        timeRemaining = 'Expired';
      }
    }"""
replacement_jit = """  if(p.isTemporary){
    let timeRemaining = 'JIT Lease';
    if(p.expiresAt){
      const msLeft = new Date(p.expiresAt).getTime() - Date.now();
      if(msLeft > 0){
        if(msLeft < 60000){
          timeRemaining = `${Math.ceil(msLeft / 1000)}s left`;
        } else if(msLeft < 3600000){
          timeRemaining = `${Math.ceil(msLeft / 60000)}m left`;
        } else {
          const hoursLeft = Math.round(msLeft / 3600000);
          timeRemaining = hoursLeft <= 48 ? `${hoursLeft}h left` : `${Math.round(hoursLeft/24)}d left`;
        }
      } else {
        timeRemaining = 'Expired (Reaping…)';
      }
    }"""
assert target_jit in text, "target_jit not found in app.js"
text = text.replace(target_jit, replacement_jit)

# 3. Add #btn-trigger-auto-audit click handler
target_click = "if(b.matches('[data-export]'))exportCsv(b.dataset.export);"
replacement_click = """if(b.id==='btn-trigger-auto-audit'){
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
  }

  """ + target_click
assert target_click in text, "target_click not found in app.js"
text = text.replace(target_click, replacement_click)

# 4. Add AutoPilotSettings card to settingsPage
target_settings = """    if (!settingsMain.querySelector('#schedule-settings-card') && typeof ScheduleSettings !== 'undefined') {

      const div = document.createElement('div');

      div.innerHTML = ScheduleSettings.renderCard();

      while (div.firstChild) settingsMain.appendChild(div.firstChild);

    }"""

replacement_settings = """    if (!settingsMain.querySelector('#schedule-settings-card') && typeof ScheduleSettings !== 'undefined') {

      const div = document.createElement('div');

      div.innerHTML = ScheduleSettings.renderCard();

      while (div.firstChild) settingsMain.appendChild(div.firstChild);

    }

    if (!settingsMain.querySelector('#autopilot-settings-card') && typeof AutoPilotSettings !== 'undefined') {

      const div = document.createElement('div');

      div.innerHTML = AutoPilotSettings.renderCard();

      while (div.firstChild) settingsMain.appendChild(div.firstChild);

    }"""
assert target_settings in text, "target_settings not found in app.js"
text = text.replace(target_settings, replacement_settings)

# 5. Initialize AutoPilotSettings in settingsPage
target_init = "if(typeof ScheduleSettings !== 'undefined'){ ScheduleSettings.init(); ScheduleSettings.attachEvents(pageContent); }"
replacement_init = "if(typeof ScheduleSettings !== 'undefined'){ ScheduleSettings.init(); ScheduleSettings.attachEvents(pageContent); }\n  if(typeof AutoPilotSettings !== 'undefined'){ AutoPilotSettings.init(); AutoPilotSettings.attachEvents(pageContent); }"
assert target_init in text, "target_init not found in app.js"
text = text.replace(target_init, replacement_init)

with open(r"D:\AccessReaper-v2\frontend\app.js", "w", encoding="utf-8") as f:
    f.write(text)
print("SUCCESS: patched app.js with automation features")
