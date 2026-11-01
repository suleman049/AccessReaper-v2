/**
 * Stage 4: Notifications Settings Component for AccessReaper v2
 * Manages daily email digest preference, SMTP status inspection, and test email delivery.
 */

const NotificationsSettings = {
  preferences: {
    emailDigestEnabled: true,
    inAppEnabled: true,
    smtpConfigured: false,
  },
  loading: false,

  renderCard() {
    return `
      <section class="card settings-card" id="notifications-settings-card">
        <div class="settings-card-heading">
          <span class="settings-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
          </span>
          <div>
            <h2>Notifications &amp; Alerts</h2>
            <p>Configure in-app alert badges and daily email digests.</p>
          </div>
        </div>

        <div class="notifications-config-section">
          <!-- In-App Alerts Row -->
          <div class="notif-config-block">
            <div class="notif-block-header">
              <div>
                <strong>In-App Notification Center</strong>
                <p class="text-muted" style="margin:2px 0 0;font-size:12px;">
                  Alerts on audit completion, high-risk findings, overdue approvals (&gt;24h), and sync degradation.
                </p>
              </div>
              <span class="badge" style="background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;font-size:11px;font-weight:700;padding:4px 8px;border-radius:6px;">
                Active
              </span>
            </div>
          </div>

          <hr style="border:0;border-top:1px solid var(--border);margin:14px 0;">

          <!-- Daily Email Digest Block -->
          <div class="notif-config-block">
            <div class="notif-block-header">
              <div>
                <strong>Daily Email Digest (SMTP)</strong>
                <p class="text-muted" style="margin:2px 0 0;font-size:12px;">
                  Receive one summary email after each automatic 24-hour IAM audit.
                </p>
              </div>
              <span id="smtp-status-badge" class="badge" style="background:#f1f5f9;color:#64748b;border:1px solid #cbd5e1;font-size:11px;font-weight:700;padding:4px 8px;border-radius:6px;">
                Checking...
              </span>
            </div>

            <div class="notif-toggle-row" style="margin-top:12px;display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--surface-subtle, #f8fafc);border:1px solid var(--border);border-radius:8px;">
              <div>
                <label for="toggle-email-digest" style="font-weight:600;font-size:13px;cursor:pointer;">
                  Enable daily email digest
                </label>
                <small style="display:block;color:var(--muted);font-size:11px;">
                  Dispatches a consolidated summary to active administrators.
                </small>
              </div>
              <input type="checkbox" id="toggle-email-digest" style="width:18px;height:18px;accent-color:var(--orange);cursor:pointer;" checked>
            </div>

            <div style="display:flex;align-items:center;justify-content:space-between;margin-top:14px;flex-wrap:wrap;gap:10px;">
              <small class="text-muted" id="smtp-info-text" style="font-size:11px;">
                Configure SMTP in <code>backend/.env</code> (host, port, user, password, from).
              </small>
              <button type="button" class="btn btn-outline btn-sm" id="btn-send-test-email">
                Send test email
              </button>
            </div>
          </div>

          <hr style="border:0;border-top:1px solid var(--border);margin:14px 0;">

          <!-- Discord & Slack Webhook Sentinel Block -->
          <div class="notif-config-block" id="webhook-sentinel-block">
            <div class="notif-block-header">
              <div>
                <strong>Discord &amp; Slack Interactive Webhook Sentinel</strong>
                <p class="text-muted" style="margin:2px 0 0;font-size:12px;">
                  Dispatches real-time alerts for access requests, JIT expirations, rogue collaborator quarantines, and offboardings.
                </p>
              </div>
              <span id="webhook-status-badge" class="badge" style="background:#f1f5f9;color:#64748b;border:1px solid #cbd5e1;font-size:11px;font-weight:700;padding:4px 8px;border-radius:6px;">
                Checking...
              </span>
            </div>

            <div style="margin-top:12px;">
              <label for="input-webhook-url" style="font-weight:600;font-size:12px;display:block;margin-bottom:6px;">
                SecOps Webhook URL (Discord / Slack)
              </label>
              <div style="display:flex;gap:8px;align-items:center;">
                <input type="url" id="input-webhook-url" class="form-control" placeholder="https://discord.com/api/webhooks/... or https://hooks.slack.com/..." style="font-size:13px;flex:1;">
                <button type="button" class="btn btn-primary btn-sm" id="btn-save-webhook" style="white-space:nowrap;">
                  Save URL
                </button>
                <button type="button" class="btn btn-outline btn-sm" id="btn-test-webhook" style="white-space:nowrap;">
                  Test Webhook
                </button>
              </div>
              <small class="text-muted" id="webhook-info-text" style="font-size:11px;display:block;margin-top:6px;">
                Real-time incident response sentinel &bull; Formatted rich embeds and buttons.
              </small>
            </div>
          </div>
        </div>
      </section>
    `;
  },

  webhookConfig: {
    configured: false,
    maskedUrl: "",
    channelType: "generic"
  },

  async init() {
    if (!window.ApiClient || window.ApiClient.isDemoMode) {
      this.updateUI();
      return;
    }

    try {
      const res = await ApiClient.getNotificationPreferences();
      this.preferences = {
        emailDigestEnabled: res.emailDigestEnabled ?? true,
        inAppEnabled: res.inAppEnabled ?? true,
        smtpConfigured: res.smtpConfigured ?? false,
      };
    } catch (err) {
      console.warn("Failed to load notification preferences:", err);
    }

    try {
      const wh = await ApiClient.getWebhookConfig();
      this.webhookConfig = wh;
    } catch (err) {
      console.warn("Failed to load webhook configuration:", err);
    }

    this.updateUI();
  },

  updateUI() {
    const checkbox = document.getElementById("toggle-email-digest");
    if (checkbox) {
      checkbox.checked = this.preferences.emailDigestEnabled;
    }

    const whBadge = document.getElementById("webhook-status-badge");
    const whInput = document.getElementById("input-webhook-url");
    const whInfo = document.getElementById("webhook-info-text");
    if (whBadge) {
      if (this.webhookConfig && this.webhookConfig.configured) {
        whBadge.textContent = (this.webhookConfig.channelType === 'discord' ? 'Discord Sentinel' : (this.webhookConfig.channelType === 'slack' ? 'Slack Sentinel' : 'Webhook Active'));
        whBadge.style.background = "#f0fdf4";
        whBadge.style.color = "#16a34a";
        whBadge.style.borderColor = "#bbf7d0";
        if (whInput && this.webhookConfig.maskedUrl && !whInput.value) {
          whInput.placeholder = this.webhookConfig.maskedUrl;
        }
        if (whInfo) whInfo.textContent = "Security Sentinel is connected. Alerts for JIT expirations, rogue access, and approvals will post here.";
      } else {
        whBadge.textContent = "Not Configured";
        whBadge.style.background = "#f8fafc";
        whBadge.style.color = "#64748b";
        whBadge.style.borderColor = "#e2e8f0";
      }
    }

    const badge = document.getElementById("smtp-status-badge");
    const infoText = document.getElementById("smtp-info-text");
    if (badge) {
      if (this.preferences.smtpConfigured) {
        badge.textContent = "SMTP Configured";
        badge.style.background = "#eff6ff";
        badge.style.color = "#1d4ed8";
        badge.style.borderColor = "#bfdbfe";
        if (infoText) infoText.textContent = "SMTP service is active and ready for automatic digests.";
      } else {
        badge.textContent = "SMTP Not Configured";
        badge.style.background = "#f8fafc";
        badge.style.color = "#64748b";
        badge.style.borderColor = "#e2e8f0";
        if (infoText) infoText.innerHTML = "Daily digest is queued locally. Set <code>SMTP_HOST</code> in <code>.env</code> to deliver emails.";
      }
    }
  },

  attachEvents(container) {
    const checkbox = container.querySelector("#toggle-email-digest");
    if (checkbox) {
      checkbox.addEventListener("change", async (e) => {
        const enabled = e.target.checked;
        this.preferences.emailDigestEnabled = enabled;
        if (window.ApiClient && !window.ApiClient.isDemoMode) {
          try {
            await ApiClient.updateNotificationPreferences({ emailDigestEnabled: enabled });
            if (typeof showToast === "function") {
              showToast(enabled ? "Daily email digest enabled" : "Daily email digest disabled");
            }
          } catch (err) {
            console.warn("Failed to update notification preferences:", err);
            if (typeof showToast === "function") showToast("Failed to save preference");
          }
        }
      });
    }

    const saveWhBtn = container.querySelector("#btn-save-webhook");
    const testWhBtn = container.querySelector("#btn-test-webhook");
    const whInput = container.querySelector("#input-webhook-url");

    if (saveWhBtn && whInput) {
      saveWhBtn.addEventListener("click", async () => {
        const url = whInput.value.trim();
        if (!url) {
          if (typeof showToast === "function") showToast("Please enter a valid webhook URL.");
          return;
        }
        saveWhBtn.disabled = true;
        saveWhBtn.textContent = "Saving...";
        try {
          await ApiClient.saveWebhookConfig(url);
          if (typeof showToast === "function") showToast("Webhook URL saved successfully!");
          this.webhookConfig = await ApiClient.getWebhookConfig();
          this.updateUI();
          whInput.value = "";
        } catch (err) {
          if (typeof showToast === "function") showToast(err.message || "Failed to save webhook URL.");
        } finally {
          saveWhBtn.disabled = false;
          saveWhBtn.textContent = "Save URL";
        }
      });
    }

    if (testWhBtn) {
      testWhBtn.addEventListener("click", async () => {
        const customUrl = whInput ? whInput.value.trim() : null;
        testWhBtn.disabled = true;
        testWhBtn.textContent = "Sending Test...";
        try {
          const res = await ApiClient.testWebhook(customUrl || null);
          if (typeof showToast === "function") showToast(res.message);
        } catch (err) {
          if (typeof showToast === "function") showToast("Failed to test webhook: " + (err.message || "Error"));
        } finally {
          testWhBtn.disabled = false;
          testWhBtn.textContent = "Test Webhook";
        }
      });
    }

    const testBtn = container.querySelector("#btn-send-test-email");
    if (testBtn) {
      testBtn.addEventListener("click", async () => {
        if (this.loading) return;
        this.loading = true;
        const originalText = testBtn.textContent;
        testBtn.disabled = true;
        testBtn.textContent = "Sending test email...";

        try {
          if (window.ApiClient && !window.ApiClient.isDemoMode) {
            const res = await ApiClient.sendTestEmail();
            if (typeof showToast === "function") {
              showToast(res.message);
            }
          } else {
            if (typeof showToast === "function") {
              showToast("Demo mode: SMTP test simulated.");
            }
          }
        } catch (err) {
          if (typeof showToast === "function") {
            showToast("Failed to send test email: " + (err.message || "Unknown error"));
          }
        } finally {
          this.loading = false;
          testBtn.disabled = false;
          testBtn.textContent = originalText;
        }
      });
    }
  },
};

window.NotificationsSettings = NotificationsSettings;
