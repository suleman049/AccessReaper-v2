import sys

path = r"D:\AccessReaper-v2\frontend\app.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    if (!settingsMain.querySelector('#schedule-settings-card') && typeof ScheduleSettings !== 'undefined') {
      const div = document.createElement('div');
      div.innerHTML = ScheduleSettings.renderCard();
      while (div.firstChild) settingsMain.appendChild(div.firstChild);
    }
  }
  if(typeof RulesSettings !== 'undefined'){ RulesSettings.init(); RulesSettings.attachEvents(pageContent); }
  if(typeof ScheduleSettings !== 'undefined'){ ScheduleSettings.init(); ScheduleSettings.attachEvents(pageContent); }
  if(typeof GitHubSettings !== 'undefined'){ GitHubSettings.init(); }"""

replacement = """    if (!settingsMain.querySelector('#schedule-settings-card') && typeof ScheduleSettings !== 'undefined') {
      const div = document.createElement('div');
      div.innerHTML = ScheduleSettings.renderCard();
      while (div.firstChild) settingsMain.appendChild(div.firstChild);
    }
    if (!settingsMain.querySelector('#notifications-settings-card') && typeof NotificationsSettings !== 'undefined') {
      const div = document.createElement('div');
      div.innerHTML = NotificationsSettings.renderCard();
      while (div.firstChild) settingsMain.appendChild(div.firstChild);
    }
  }
  if(typeof RulesSettings !== 'undefined'){ RulesSettings.init(); RulesSettings.attachEvents(pageContent); }
  if(typeof ScheduleSettings !== 'undefined'){ ScheduleSettings.init(); ScheduleSettings.attachEvents(pageContent); }
  if(typeof NotificationsSettings !== 'undefined'){ NotificationsSettings.init(); NotificationsSettings.attachEvents(pageContent); }
  if(typeof GitHubSettings !== 'undefined'){ GitHubSettings.init(); }"""

content_norm = content.replace("\r\n", "\n")
target_norm = target.replace("\r\n", "\n")
replacement_norm = replacement.replace("\r\n", "\n")

if target_norm in content_norm:
    new_content_norm = content_norm.replace(target_norm, replacement_norm, 1)
    if "\r\n" in content:
        new_content = new_content_norm.replace("\n", "\r\n")
    else:
        new_content = new_content_norm
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new_content)
    print("Successfully patched app.js")
else:
    print("Target not found in app.js!")
