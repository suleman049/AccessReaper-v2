// AccessReaper v2 — Automatic Audits Settings Component (Stage 1)
// Configures 24-hour automated IAM audits with Asia/Karachi timezone,
// pause/resume with required explanation note, time of day picker, and recent runs history.

const ScheduleSettings = {
  enabled: true,
  intervalHours: 24,
  timeOfDay: "02:00",
  nextRun: null,
  formattedNextRun: "Calculating...",
  pauseNote: null,
  pauseModalOpen: false,
  initialized: false,

  async init() {
    await this.fetchSchedule();
    if (location.hash.slice(1).split("?")[0] === "settings") {
      const card = document.querySelector("#schedule-settings-card");
      if (card) {
        const div = document.createElement("div");
        div.innerHTML = this.renderCard();
        const newCard = div.firstElementChild;
        if (newCard) {
          card.replaceWith(newCard);
          this.attachEvents(document.querySelector("#page-content") || document);
        }
      }
    }
  },

  async fetchSchedule() {
    try {
      if (window.ApiClient && !window.ApiClient.isDemoMode) {
        const res = await ApiClient.getAutomationStatus();
        this.enabled = res.enabled;
        this.timeOfDay = res.timeOfDay || "02:00";
        this.pauseNote = res.pauseNote || null;
        if (res.nextRunAt) {
          try {
            const dt = new Date(res.nextRunAt);
            this.formattedNextRun = dt.toLocaleString("en-US", {
              weekday: "short",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              timeZone: "Asia/Karachi",
            }) + " PKT";
          } catch (e) {
            this.formattedNextRun = res.nextRunAt;
          }
        } else {
          this.formattedNextRun = "Paused";
        }
      } else {
        this.enabled = true;
        this.timeOfDay = "02:00";
        this.formattedNextRun = "Daily at 02:00 PKT (active schedule)";
      }
    } catch (err) {
      console.warn("Could not fetch automation schedule:", err);
    }
  },

  renderRecentRuns() {
    const runs = (window.auditRuns || []).slice(-4).reverse();
    if (!runs.length) {
      return `<p class="text-muted" style="font-size: 12px; margin-top: 8px;">No audit runs recorded yet.</p>`;
    }

    return `
      <table class="auto-recent-runs-table">
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Completed (PKT)</th>
            <th>Status</th>
            <th>Trigger</th>
            <th>Findings</th>
          </tr>
        </thead>
        <tbody>
          ${runs.map(r => {
            const isDegraded = r.status === "Degraded";
            const dateStr = r.completedAt ? new Date(r.completedAt).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
            return `
              <tr>
                <td><strong>${safe(r.id)}</strong></td>
                <td>${safe(dateStr)}</td>
                <td>
                  <span class="badge ${isDegraded ? 'badge-warning' : 'badge-success'}" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; ${isDegraded ? 'background:#fff4ed;color:#b54708;' : 'background:#ecfdf3;color:#027a48;'}">
                    ${safe(r.status)}
                  </span>
                </td>
                <td style="text-transform: capitalize;">${safe(r.trigger || 'scheduled')}</td>
                <td>${r.high || 0} High · ${r.medium || 0} Med</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
  },

  renderCard() {
    const isPaused = !this.enabled;

    return `
      <section class="card settings-card" id="schedule-settings-card">
        <div class="settings-card-heading">
          <span class="settings-icon">${uiIcon('clock', 18)}</span>
          <div style="flex:1;">
            <div class="d-flex align-items-center justify-content-between">
              <h2>Automatic audits</h2>
              ${isPaused
                ? `<span class="badge badge-warning" style="background:#fff4ed;color:#b54708;border:1px solid #fedf89;padding:4px 8px;border-radius:6px;font-weight:600;font-size:12px;">Paused</span>`
                : `<span class="badge badge-success" style="background:#ecfdf3;color:#027a48;border:1px solid #a6f4c5;padding:4px 8px;border-radius:6px;font-weight:600;font-size:12px;">Active (Every 24 hours)</span>`
              }
            </div>
            <p>The system syncs and audits by itself every 24 hours. All schedules run in <b>Asia/Karachi (PKT)</b> timezone.</p>
          </div>
        </div>

        <form id="schedule-config-form" class="schedule-config-form">
          <div class="schedule-row">
            <label>Interval</label>
            <div style="font-size:13px;font-weight:600;color:var(--text);padding:6px 0;">
              Fixed 24 hours (Daily recurring)
            </div>
          </div>

          <div class="schedule-row" id="sched-time-row">
            <label for="sched-time">Daily execution time (PKT)</label>
            <input type="time" id="sched-time" class="form-control" value="${this.timeOfDay || "02:00"}" style="max-width: 160px;" ${isPaused ? 'disabled' : ''}>
          </div>

          <div class="schedule-next-indicator">
            <span>Next automatic run:</span>
            <strong>${safe(this.formattedNextRun)}</strong>
          </div>

          ${isPaused && this.pauseNote ? `
            <div class="auto-audit-pause-box">
              <strong style="color:#b54708;font-size:12px;display:block;margin-bottom:4px;">Pause explanation:</strong>
              <span style="font-size:12px;color:var(--text);">${safe(this.pauseNote)}</span>
            </div>
          ` : ''}

          <div id="pause-modal-box" class="auto-audit-pause-box" style="display: ${this.pauseModalOpen ? 'block' : 'none'};">
            <strong style="display:block;margin-bottom:6px;font-size:13px;">Reason for pausing automatic audits</strong>
            <p style="font-size:12px;color:var(--muted);margin-bottom:8px;">An explanation is required. This will be recorded in the immutable audit log.</p>
            <textarea id="pause-note-input" class="form-control" rows="2" placeholder="e.g., Scheduled maintenance window or organization reconfiguration"></textarea>
            <div id="pause-note-error" style="display:none;color:#b42318;font-size:12px;margin-top:4px;">A note explaining the reason for pausing automatic audits is required.</div>
            <div class="d-flex justify-content-end gap-2" style="margin-top:10px;">
              <button type="button" class="btn btn-outline btn-sm" id="btn-cancel-pause">Cancel</button>
              <button type="button" class="btn btn-primary btn-sm" id="btn-confirm-pause" style="background:#b42318;border-color:#b42318;">Confirm pause</button>
            </div>
          </div>

          <div class="d-flex justify-content-between align-items-center" style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border);">
            <div>
              ${isPaused ? `
                <button type="button" class="btn btn-outline" id="btn-resume-schedule" style="color:#027a48;border-color:#a6f4c5;">
                  Resume automatic audits
                </button>
              ` : `
                <button type="button" class="btn btn-outline" id="btn-open-pause" style="color:#b54708;border-color:#fedf89;">
                  Pause automatic audits…
                </button>
              `}
            </div>
            <div>
              <button type="button" class="btn btn-primary" id="btn-save-schedule" ${isPaused ? 'disabled' : ''}>
                Save execution time
              </button>
            </div>
          </div>
        </form>

        <div style="margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--border);">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:13px;">Recent automated audit runs</strong>
            <span style="font-size:11px;color:var(--muted);">Past 4 cycles</span>
          </div>
          ${this.renderRecentRuns()}
        </div>
      </section>
    `;
  },

  attachEvents(container) {
    const saveBtn = container.querySelector("#btn-save-schedule");
    const openPauseBtn = container.querySelector("#btn-open-pause");
    const resumeBtn = container.querySelector("#btn-resume-schedule");
    const cancelPauseBtn = container.querySelector("#btn-cancel-pause");
    const confirmPauseBtn = container.querySelector("#btn-confirm-pause");
    const pauseBox = container.querySelector("#pause-modal-box");
    const pauseInput = container.querySelector("#pause-note-input");
    const pauseError = container.querySelector("#pause-note-error");

    openPauseBtn?.addEventListener("click", () => {
      this.pauseModalOpen = true;
      if (pauseBox) pauseBox.style.display = "block";
      pauseInput?.focus();
    });

    cancelPauseBtn?.addEventListener("click", () => {
      this.pauseModalOpen = false;
      if (pauseBox) pauseBox.style.display = "none";
      if (pauseError) pauseError.style.display = "none";
    });

    confirmPauseBtn?.addEventListener("click", async () => {
      const note = (pauseInput?.value || "").trim();
      if (!note) {
        if (pauseError) {
          pauseError.textContent = "A note explaining the reason for pausing automatic audits is required.";
          pauseError.style.display = "block";
        }
        pauseInput?.focus();
        return;
      }

      try {
        if (window.ApiClient && !window.ApiClient.isDemoMode) {
          const res = await ApiClient.updateAutomationConfig({
            enabled: false,
            timeOfDay: this.timeOfDay,
            note: note,
          });
          this.enabled = res.enabled;
          this.pauseNote = res.pauseNote;
          this.pauseModalOpen = false;
          if (window.AutomationTimer) window.AutomationTimer.updateFromStatus(res);
          if (typeof decisionFeedback === "function") decisionFeedback("Automatic audits paused.");
        } else {
          this.enabled = false;
          this.pauseNote = note;
          this.pauseModalOpen = false;
          if (typeof decisionFeedback === "function") decisionFeedback("Automatic audits paused.");
        }
        await this.init();
        if (typeof render === "function") render();
      } catch (err) {
        console.error("Failed to pause automatic audits:", err);
        if (pauseError) {
          pauseError.textContent = err.message || "Failed to pause automatic audits.";
          pauseError.style.display = "block";
        }
      }
    });

    resumeBtn?.addEventListener("click", async () => {
      try {
        if (window.ApiClient && !window.ApiClient.isDemoMode) {
          const res = await ApiClient.updateAutomationConfig({
            enabled: true,
            timeOfDay: this.timeOfDay,
            note: "Resumed by administrator",
          });
          this.enabled = res.enabled;
          this.pauseNote = null;
          if (window.AutomationTimer) window.AutomationTimer.updateFromStatus(res);
          if (typeof decisionFeedback === "function") decisionFeedback("Automatic audits resumed.");
        } else {
          this.enabled = true;
          this.pauseNote = null;
          if (typeof decisionFeedback === "function") decisionFeedback("Automatic audits resumed.");
        }
        await this.init();
        if (typeof render === "function") render();
      } catch (err) {
        console.error("Failed to resume automatic audits:", err);
      }
    });

    saveBtn?.addEventListener("click", async () => {
      const timeVal = container.querySelector("#sched-time")?.value || "02:00";
      try {
        if (window.ApiClient && !window.ApiClient.isDemoMode) {
          const res = await ApiClient.updateAutomationConfig({
            enabled: true,
            timeOfDay: timeVal,
            note: `Changed daily execution time to ${timeVal} PKT`,
          });
          this.timeOfDay = res.timeOfDay;
          this.enabled = res.enabled;
          if (window.AutomationTimer) window.AutomationTimer.updateFromStatus(res);
          if (typeof decisionFeedback === "function") decisionFeedback(`Daily audit time set to ${res.timeOfDay} PKT.`);
        } else {
          this.timeOfDay = timeVal;
          if (typeof decisionFeedback === "function") decisionFeedback(`Daily audit time set to ${timeVal} PKT.`);
        }
        await this.init();
        if (typeof render === "function") render();
      } catch (err) {
        console.error("Failed to update execution time:", err);
      }
    });
  }
};

window.ScheduleSettings = ScheduleSettings;
