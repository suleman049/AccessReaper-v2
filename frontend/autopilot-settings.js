// AccessReaper v2 — Auto-Pilot Autonomous Policy Enforcer Component (Stage 2)
const AutoPilotSettings = {
  enabled: false,
  lastEnforcedAt: null,
  eligibleCount: 0,
  activePolicies: [],
  initialized: false,

  renderInPlace() {
    if (location.hash.slice(1).split("?")[0] === "settings") {
      const card = document.querySelector("#autopilot-settings-card");
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

  async init() {
    await this.fetchStatus();
    this.renderInPlace();
  },

  async fetchStatus() {
    try {
      if (window.ApiClient && !window.ApiClient.isDemoMode) {
        const res = await ApiClient.getAutoPilot();
        this.enabled = Boolean(res.enabled);
        this.lastEnforcedAt = res.last_enforced_at;
        this.eligibleCount = res.eligible_findings_count || 0;
        this.activePolicies = res.active_policies || [];
      }
    } catch (e) {
      console.warn("Auto-Pilot fetch failed:", e);
    }
  },

  renderCard() {
    const isEnforced = this.enabled;
    let formattedLast = "Never (Manual mode active)";
    if (this.lastEnforcedAt) {
      try {
        formattedLast = new Date(this.lastEnforcedAt).toLocaleString("en-US", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
      } catch (e) {
        formattedLast = this.lastEnforcedAt;
      }
    }

    return `
      <section class="card mb-4" id="autopilot-settings-card" style="border-radius:10px; overflow:hidden;">
        <div class="card-header d-flex justify-content-between align-items-center" style="padding: 16px 20px; background:var(--surface-soft, rgba(0,0,0,0.06)); border-bottom: 1px solid var(--border);">
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="color:#f59e0b;display:flex;">${uiIcon('zap', 20)}</span>
            <div>
              <h2 style="font-size:16px;margin:0;font-weight:600;display:flex;align-items:center;gap:8px;">
                Autonomous Policy Enforcer (Auto-Pilot)
                <span class="badge" style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;background:${isEnforced ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)'};color:${isEnforced ? '#10b981' : '#94a3b8'};">
                  ${isEnforced ? 'AUTONOMOUS ACTIVE' : 'MANUAL REVIEW (OFF)'}
                </span>
              </h2>
              <p style="font-size:12px;color:var(--muted);margin:2px 0 0;">Continuous least-privilege autonomous enforcement for payhive-eng</p>
            </div>
          </div>
          <div class="form-check form-switch" style="font-size:15px;margin:0;">
            <input class="form-check-input" type="checkbox" id="autopilot-toggle-switch" style="cursor:pointer;" ${isEnforced ? 'checked' : ''}>
          </div>
        </div>

        <div style="padding: 20px;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px; margin-bottom:18px;">
            <div style="max-width:680px;">
              <p style="font-size:13px;line-height:1.6;margin:0 0 10px;color:var(--text);">
                When <strong>Auto-Pilot</strong> is switched <strong>ON</strong>, AccessReaper acts as an autonomous security daemon. It monitors contractor privileges and dormant access, automatically enforcing least-privilege compliance without waiting for manual administrator intervention.
              </p>
              <div style="font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:5px;">
                <div>&bull; <strong>External Contractor Policy:</strong> External staff with Admin rights are automatically de-escalated to Write.</div>
                <div>&bull; <strong>JIT Reaper:</strong> Expired temporary repository leases are revoked live on GitHub at 00:00.</div>
                <div>&bull; <strong>Tamper-Proof Audit Trail:</strong> Every autonomous action writes an immutable record under <em>Actor: Auto-Pilot</em>.</div>
              </div>
            </div>

            <div style="display:flex;flex-direction:column;gap:8px;min-width:200px;">
              <div style="font-size:11.5px;color:var(--muted);">
                Eligible for Auto-Reap: <strong>${this.eligibleCount} findings</strong>
              </div>
              <div style="font-size:11.5px;color:var(--muted);">
                Last Enforced: <strong>${safe(formattedLast)}</strong>
              </div>
              <button type="button" class="btn btn-sm btn-primary" id="btn-enforce-autopilot" style="font-size:12px;margin-top:4px;">
                ${uiIcon('zap', 13)} Enforce Policies Now
              </button>
            </div>
          </div>
        </div>
      </section>
    `;
  },

  attachEvents(container) {
    const sw = container.querySelector("#autopilot-toggle-switch");
    if (sw) {
      sw.onchange = async (e) => {
        const val = e.target.checked;
        try {
          const res = await ApiClient.updateAutoPilot(val);
          this.enabled = Boolean(res.enabled);
          this.lastEnforcedAt = res.last_enforced_at;
          this.eligibleCount = res.eligible_findings_count || 0;
          this.activePolicies = res.active_policies || [];
          const statusText = this.enabled
            ? "Auto-Pilot Mode enabled: Continuous autonomous enforcement is ACTIVE."
            : "Auto-Pilot Mode paused: System is in Manual Review mode.";
          if (typeof showToast === "function") showToast(statusText);
          this.renderInPlace();
        } catch (err) {
          if (typeof showToast === "function") showToast(err.message || "Failed to update Auto-Pilot");
          e.target.checked = !val;
        }
      };
    }

    const enforceBtn = container.querySelector("#btn-enforce-autopilot");
    if (enforceBtn) {
      enforceBtn.onclick = async () => {
        enforceBtn.disabled = true;
        enforceBtn.innerHTML =
          '<span class="spinner-border spinner-border-sm" style="width:11px;height:11px;border-width:2px;margin-right:4px;"></span> Enforcing…';
        try {
          const res = await ApiClient.enforceAutoPilot();
          const msg = res.message || `Auto-Pilot enforced: ${res.remediated_count} privileges remediated.`;
          if (typeof showToast === "function") showToast(msg);
          await this.fetchStatus();
          this.renderInPlace();
        } catch (err) {
          if (typeof showToast === "function") showToast(err.message || "Could not enforce Auto-Pilot");
        } finally {
          enforceBtn.disabled = false;
          enforceBtn.innerHTML = `${uiIcon('zap', 13)} Enforce Policies Now`;
        }
      };
    }
  },
};

window.AutoPilotSettings = AutoPilotSettings;
