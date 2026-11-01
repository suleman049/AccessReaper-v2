// AccessReaper v2 — Automation Timer Component (Stage 1)
// Live ticking countdown to the next automated 24-hour IAM audit.
// Uses server time offset to eliminate client PC clock skew.

const AutomationTimer = {
  status: null,
  timeOffset: 0,
  intervalId: null,
  pollId: null,
  initialized: false,
  lastKnownRunId: null,
  wasRunning: false,

  init() {
    if (this.initialized) return;
    this.initialized = true;
    this.startTicking();
    this.startPolling();
    this.fetchStatus();
  },

  updateFromStatus(status) {
    if (!status) return;
    const oldRunId = this.lastKnownRunId;
    const wasRunning = this.wasRunning;
    const newRunId = status.lastRun ? status.lastRun.id : null;
    const isRunning = Boolean(status.isRunning);

    this.status = status;
    this.wasRunning = isRunning;
    if (newRunId) this.lastKnownRunId = newRunId;

    if (status.serverTime) {
      this.timeOffset = new Date(status.serverTime).getTime() - Date.now();
    }

    // Auto-reload data when a run completes
    if ((wasRunning && !isRunning) || (oldRunId && newRunId && oldRunId !== newRunId)) {
      if (typeof ApiClient !== "undefined" && ApiClient.bootstrap) {
        ApiClient.bootstrap().then((data) => {
          if (ApiClient.syncState) ApiClient.syncState(data);
          if (typeof render === "function") render();
          if (typeof showToast === "function") showToast("Automatic audit completed");
        }).catch((err) => console.error("Could not refresh data after automatic audit:", err));
      }
    }

    this.updateDom();
  },

  async fetchStatus() {
    try {
      if (window.ApiClient && !window.ApiClient.isDemoMode) {
        const res = await ApiClient.getAutomationStatus();
        this.updateFromStatus(res);
      }
    } catch (e) {
      console.warn("Automation status poll failed:", e);
    }
  },

  startPolling() {
    if (this.pollId) clearInterval(this.pollId);
    this.pollId = setInterval(() => this.fetchStatus(), 20000);
  },

  startTicking() {
    if (this.intervalId) clearInterval(this.intervalId);
    this.intervalId = setInterval(() => this.tick(), 1000);
  },

  tick() {
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
  },

  getFormattedCountdown() {
    const st = this.status || window.automationStatus;
    if (!st || !st.enabled || !st.nextRunAt) return null;

    const target = new Date(st.nextRunAt).getTime();
    const now = Date.now() + this.timeOffset;
    const diff = Math.max(0, Math.floor((target - now) / 1000));

    const h = String(Math.floor(diff / 3600)).padStart(2, "0");
    const m = String(Math.floor((diff % 3600) / 60)).padStart(2, "0");
    const s = String(diff % 60).padStart(2, "0");
    return `${h}:${m}:${s}`;
  },

  renderChip() {
    const st = this.status || window.automationStatus;
    if (!st) {
      return `<div class="automation-chip-wrap" id="automation-chip-wrap">
        <span class="badge badge-outline automation-chip">
          <span class="chip-dot active"></span> Next audit in <span class="countdown-clock" id="countdown-clock-val">--:--:--</span>
        </span>
        <span class="automation-subtext">Automatic 24-hour cycle</span>
      </div>`;
    }

    if (!st.enabled) {
      return `<div class="automation-chip-wrap" id="automation-chip-wrap" title="${st.pauseNote ? 'Paused: ' + safe(st.pauseNote) : 'Automatic audits paused'}">
        <span class="badge badge-warning automation-chip paused">
          <span class="chip-dot paused"></span> Automatic audits paused
        </span>
        <span class="automation-subtext">${safe(st.pauseNote ? 'Paused: ' + st.pauseNote : 'Paused by admin · 24h schedule off')}</span>
      </div>`;
    }

    if (st.isRunning) {
      return `<div class="automation-chip-wrap" id="automation-chip-wrap">
        <span class="badge badge-outline automation-chip running">
          <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="width:11px;height:11px;border-width:2px;margin-right:4px;"></span>
          Audit in progress…
        </span>
        <span class="automation-subtext">Automated IAM audit running</span>
      </div>`;
    }

    const countdown = this.getFormattedCountdown() || "00:00:00";
    let lastAuditText = "First automatic audit pending";
    if (st.lastRun && st.lastRun.at) {
      try {
        const d = new Date(st.lastRun.at);
        lastAuditText = d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
      } catch (e) {
        lastAuditText = st.lastRun.at;
      }
    } else if (window.lastAudit) {
      lastAuditText = window.lastAudit;
    }

    return `<div class="automation-chip-wrap" id="automation-chip-wrap">
      <div style="display:inline-flex;align-items:center;gap:8px;">
        <span class="badge badge-outline automation-chip" title="Next automatic audit in ${countdown}">
          <span class="chip-dot active"></span> Next audit in <span class="countdown-clock" id="countdown-clock-val">${countdown}</span>
        </span>
        <button type="button" class="btn btn-sm btn-outline automation-run-btn" id="btn-trigger-auto-audit" style="font-size:11.5px;padding:3px 9px;border-radius:6px;display:inline-flex;align-items:center;gap:4px;" title="Execute automated audit cycle immediately">
          ${uiIcon('zap', 12)} <span>Run Auto-Audit</span>
        </button>
      </div>
      <span class="automation-subtext">Last audit: ${safe(lastAuditText)} · Automatic</span>
    </div>`;
  },

  updateDom() {
    const chips = document.querySelectorAll("#automation-chip-wrap");
    if (!chips.length) return;
    const st = this.status || window.automationStatus;

    chips.forEach((el) => {
      const clockEl = el.querySelector("#countdown-clock-val");
      if (clockEl && st && st.enabled && !st.isRunning) {
        clockEl.textContent = this.getFormattedCountdown() || "00:00:00";
      } else {
        const temp = document.createElement("div");
        temp.innerHTML = this.renderChip();
        const newChip = temp.firstElementChild;
        if (newChip) el.replaceWith(newChip);
      }
    });
  }
};

window.AutomationTimer = AutomationTimer;
// Auto-initialize when loaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => AutomationTimer.init());
} else {
  AutomationTimer.init();
}
