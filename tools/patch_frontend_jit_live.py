# 1. Patch frontend/api-client.js
path_api = r'D:\AccessReaper-v2\frontend\api-client.js'
with open(path_api, 'r', encoding='utf-8') as f:
    c_api = f.read()

target_api = """  async triggerAutoAudit() {
    return await this.request("/api/automation/trigger", {
      method: "POST",
    });
  },"""

replacement_api = """  async triggerAutoAudit() {
    return await this.request("/api/automation/trigger", {
      method: "POST",
    });
  },

  async reapJit() {
    return await this.request("/api/automation/reap", {
      method: "POST",
    });
  },"""

c_api_norm = c_api.replace('\r\n', '\n')
target_api_norm = target_api.replace('\r\n', '\n')
replacement_api_norm = replacement_api.replace('\r\n', '\n')
assert target_api_norm in c_api_norm, "Target not found in api-client.js"
c_api_new = c_api_norm.replace(target_api_norm, replacement_api_norm, 1)

with open(path_api, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c_api_new)
print("SUCCESS: patched api-client.js")

# 2. Patch frontend/app.js jitBadge
path_app = r'D:\AccessReaper-v2\frontend\app.js'
with open(path_app, 'r', encoding='utf-8') as f:
    c_app = f.read()

target_badge = 'jitBadge = `<span class="badge" style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:700;margin-left:4px;display:inline-flex;align-items:center;gap:3px;" title="Just-In-Time Temporary Lease">${uiIcon(\'clock\', 11)} ${timeRemaining}</span>`;'
replacement_badge = 'jitBadge = `<span class="badge" data-jit-badge="${safe(p.id)}" data-expires-at="${safe(p.expiresAt || \'\')}" style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:700;margin-left:4px;display:inline-flex;align-items:center;gap:3px;" title="Just-In-Time Temporary Lease">${uiIcon(\'clock\', 11)} <span class="jit-countdown-text">${timeRemaining}</span></span>`;'

c_app_norm = c_app.replace('\r\n', '\n')
assert target_badge in c_app_norm, "target_badge not found in app.js"
c_app_new = c_app_norm.replace(target_badge, replacement_badge, 1)

with open(path_app, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c_app_new)
print("SUCCESS: patched app.js jitBadge")

# 3. Patch frontend/automation-timer.js
path_timer = r'D:\AccessReaper-v2\frontend\automation-timer.js'
with open(path_timer, 'r', encoding='utf-8') as f:
    c_timer = f.read()

target_timer = """  tick() {
    this.updateDom();
  },"""

replacement_timer = """  tick() {
    this.updateDom();
    this.updateJitBadges();
  },

  updateJitBadges() {
    const badges = document.querySelectorAll("[data-jit-badge]");
    if (!badges.length) return;

    let hasExpired = false;
    badges.forEach((el) => {
      const expiresAt = el.dataset.expiresAt;
      if (!expiresAt) return;
      const msLeft = new Date(expiresAt).getTime() - Date.now();
      const textSpan = el.querySelector(".jit-countdown-text");
      if (!textSpan) return;

      if (msLeft > 0) {
        if (msLeft < 60000) {
          textSpan.textContent = `${Math.ceil(msLeft / 1000)}s left`;
        } else if (msLeft < 3600000) {
          textSpan.textContent = `${Math.ceil(msLeft / 60000)}m left`;
        } else {
          const hoursLeft = Math.round(msLeft / 3600000);
          textSpan.textContent = hoursLeft <= 48 ? `${hoursLeft}h left` : `${Math.round(hoursLeft / 24)}d left`;
        }
      } else {
        textSpan.textContent = "Expired (Revoking…)";
        el.style.background = "#fee2e2";
        el.style.color = "#dc2626";
        el.style.borderColor = "#fca5a5";

        if (!el.dataset.reapTriggered) {
          el.dataset.reapTriggered = "true";
          hasExpired = true;
        }
      }
    });

    if (hasExpired && window.ApiClient && !window.ApiClient.isDemoMode) {
      (async () => {
        try {
          if (typeof ApiClient.reapJit === "function") {
            await ApiClient.reapJit();
          }
          const data = await ApiClient.bootstrap();
          ApiClient.syncState(data);
          if (typeof render === "function") render();
          if (window.NotificationsCenter) await NotificationsCenter.fetchNotifications();
          if (typeof showToast === "function") {
            showToast("⏱️ JIT temporary lease expired: access was automatically revoked.");
          }
        } catch (e) {
          console.warn("Auto-reap trigger error:", e);
        }
      })();
    }
  },"""

c_timer_norm = c_timer.replace('\r\n', '\n')
target_timer_norm = target_timer.replace('\r\n', '\n')
replacement_timer_norm = replacement_timer.replace('\r\n', '\n')
assert target_timer_norm in c_timer_norm, "Target not found in automation-timer.js"
c_timer_new = c_timer_norm.replace(target_timer_norm, replacement_timer_norm, 1)

with open(path_timer, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c_timer_new)
print("SUCCESS: patched automation-timer.js")

# 4. Patch frontend/notifications-center.js
path_notif = r'D:\AccessReaper-v2\frontend\notifications-center.js'
with open(path_notif, 'r', encoding='utf-8') as f:
    c_notif = f.read()

# Change poll interval from 30000 to 10000
c_notif_new = c_notif.replace("setInterval(() => this.fetchNotifications(), 30000)", "setInterval(() => this.fetchNotifications(), 10000)")

# Add jit_expired to icon handler
target_icon = 'case "approval_overdue":'
replacement_icon = 'case "jit_expired":\n      case "approval_overdue":'
c_notif_new = c_notif_new.replace(target_icon, replacement_icon, 1)

# Add toast on new notification arrival
target_fetch = """      this.unreadCount = res.unreadCount || 0;
      this.notifications = res.notifications || [];
      this.updateBadge();"""

replacement_fetch = """      const prevCount = this.unreadCount;
      this.unreadCount = res.unreadCount || 0;
      this.notifications = res.notifications || [];
      this.updateBadge();
      if (this.unreadCount > prevCount && prevCount >= 0 && this.notifications.length > 0) {
        const latest = this.notifications[0];
        if (latest && !latest.isRead && typeof showToast === "function") {
          showToast(`🔔 ${latest.title}: ${latest.message}`);
        }
      }"""

c_notif_new_norm = c_notif_new.replace('\r\n', '\n')
target_fetch_norm = target_fetch.replace('\r\n', '\n')
replacement_fetch_norm = replacement_fetch.replace('\r\n', '\n')
assert target_fetch_norm in c_notif_new_norm, "target_fetch not found in notifications-center.js"
c_notif_final = c_notif_new_norm.replace(target_fetch_norm, replacement_fetch_norm, 1)

with open(path_notif, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c_notif_final)
print("SUCCESS: patched notifications-center.js")
