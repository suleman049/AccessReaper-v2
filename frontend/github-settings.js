// AccessReaper v2 — GitHub Integration & Data Mode Settings
// Handles connected service status, sync, disconnect, data mode toggling, and unmatched account mapping.

const GitHubSettings = {
  status: null,
  unmatched: [],
  isSyncing: false,

  async init() {
    await this.fetchStatus();
    await this.fetchUnmatched();
    this.renderConnectedService();
    this.renderUnmatchedCard();
    this.updateHeaderBadge();
  },

  async fetchStatus() {
    try {
      if (window.ApiClient) {
        this.status = await window.ApiClient.getGitHubStatus();
        if (this.status && this.status.data_mode) {
          window.currentDataMode = this.status.data_mode;
        }
      }
    } catch (e) {
      console.warn("Could not fetch GitHub status:", e);
    }
  },

  async fetchUnmatched() {
    try {
      if (window.ApiClient) {
        this.unmatched = await window.ApiClient.getUnmatchedGitHub();
      }
    } catch (e) {
      console.warn("Could not fetch unmatched accounts:", e);
    }
  },

  formatTime(isoStr) {
    if (!isoStr) return "Never";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  },

  renderConnectedService() {
    // Find Connected services card in Settings
    const servicesCard = document.querySelector(".settings-card:has(.settings-service)");
    if (!servicesCard) return;

    // Find GitHub Organization row
    const services = servicesCard.querySelectorAll(".settings-service");
    let ghRow = null;
    services.forEach(s => {
      if (s.textContent.includes("GitHub Organization")) {
        ghRow = s;
      }
    });

    if (!ghRow) return;

    const isConnected = this.status && this.status.connected;
    const org = this.status?.org_name || "payhive-eng";
    const lastSyncTime = this.status?.last_sync?.finished_at ? this.formatTime(this.status.last_sync.finished_at) : "Never";
    const currentMode = "live";

    let stateHtml = "";
    if (isConnected) {
      stateHtml = `
        <div class="gh-connected-status">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
            <span class="connection-state is-connected">Connected · ${org} · last sync ${lastSyncTime}</span>
            <span class="badge bg-success text-white" style="font-size: 11px; padding: 3px 8px; border-radius: 4px; display: inline-flex; align-items: center; gap: 4px;">
              <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#4ade80;"></span>
              Auto-sync active (every 15m)
            </span>
          </div>
          <div class="gh-actions-bar">
            <button class="btn btn-sm btn-outline text-danger" id="btn-gh-disconnect">Disconnect</button>
            <span class="badge bg-success text-white" style="font-size: 11px; padding: 6px 10px; border-radius: 6px; font-weight: 700; display: inline-flex; align-items: center; gap: 5px;">
              <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#fff;"></span>
              Mode: LIVE PRODUCTION
            </span>
            <button class="btn btn-sm btn-outline" id="btn-gh-sync" style="opacity: 0.8; font-size: 11px;" ${this.isSyncing ? "disabled" : ""} title="Background scheduler syncs automatically every 15 minutes. Click to force instant sync.">
              ${this.isSyncing ? '<span class="spinner-inline"></span> Syncing...' : "↻ Manual sync"}
            </button>
          </div>
        </div>
      `;
    } else {
      stateHtml = `
        <div class="gh-disconnected-status">
          <span class="connection-state">Not connected</span>
          <div class="gh-actions-bar">
            <button class="btn btn-sm btn-primary" id="btn-gh-connect">Connect</button>
            <button class="btn btn-sm btn-outline" id="btn-gh-datamode">Data mode: <strong>${currentMode.toUpperCase()}</strong></button>
          </div>
        </div>
      `;
    }

    let statusContainer = ghRow.querySelector(".gh-service-details");
    if (!statusContainer) {
      statusContainer = document.createElement("div");
      statusContainer.className = "gh-service-details";
      const oldState = ghRow.querySelector(".connection-state");
      if (oldState) oldState.remove();
      ghRow.appendChild(statusContainer);
    }
    statusContainer.innerHTML = stateHtml;

    // Bind event handlers
    const btnConnect = document.getElementById("btn-gh-connect");
    if (btnConnect) btnConnect.onclick = () => this.openConnectModal();

    const btnSync = document.getElementById("btn-gh-sync");
    if (btnSync) btnSync.onclick = () => this.syncNow();

    const btnDisconnect = document.getElementById("btn-gh-disconnect");
    if (btnDisconnect) btnDisconnect.onclick = () => this.disconnect();

    const btnDataMode = document.getElementById("btn-gh-datamode");
    if (btnDataMode) btnDataMode.onclick = () => this.openDataModeModal();

    this.renderAIStatus(servicesCard);
  },

  async renderAIStatus(servicesCard) {
    if (!window.llmStatus && window.ApiClient && window.ApiClient.getLLMStatus) {
      try {
        window.llmStatus = await window.ApiClient.getLLMStatus();
      } catch (e) {
        console.warn("Could not fetch LLM status:", e);
      }
    }
    const s = window.llmStatus;
    if (!s) return;

    const orderEl = document.getElementById("ai-provider-order");
    const usageEl = document.getElementById("ai-token-usage");
    const cfgEl = document.getElementById("ai-configured-status");

    if (orderEl && s.provider_order) {
      orderEl.textContent = s.provider_order.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" → ");
    }
    if (usageEl) {
      const u = (s.daily_token_usage || 0).toLocaleString();
      const b = (s.daily_token_budget || 200000).toLocaleString();
      usageEl.textContent = `${u} / ${b}`;
    }
    if (cfgEl) {
      const groqCfg = s.groq && s.groq.configured ? "Yes" : "No";
      const geminiCfg = s.gemini && s.gemini.configured ? "Yes" : "No";
      cfgEl.textContent = `Groq: ${groqCfg} · Gemini: ${geminiCfg}`;
    }
  },

  renderUnmatchedCard() {
    let card = document.getElementById("unmatched-github-card");
    const container = document.querySelector(".settings-content .settings-main") || document.querySelector(".settings-main");
    if (!container) return;

    const count = this.unmatched ? this.unmatched.length : 0;

    let rowsHtml = "";
    if (count === 0) {
      rowsHtml = `
        <div class="unmatched-empty-state">
          <p>All GitHub accounts are currently mapped to recognized organization employees.</p>
        </div>
      `;
    } else {
      rowsHtml = `
        <div class="alert alert-warning mb-3" style="background: rgba(245, 158, 11, 0.08); border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 6px; font-size: 13px; color: var(--text-primary); margin-bottom: 16px;">
          <strong>${uiIcon('alert', 14)} Action Required:</strong> These GitHub accounts have hidden or private emails on GitHub. AccessReaper could not automatically discover their email addresses from metadata. Please enter their company email below and click <strong>Link</strong> so that automated access revocation notices can be delivered to them.
        </div>
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2" style="padding: 10px 0; border-bottom: 1px solid var(--border);">
          <div class="d-flex gap-2">
            <button type="button" class="btn btn-outline btn-sm" id="btn-auto-suggest">
              ${uiIcon('sparkles', 13)} Auto-suggest matches
            </button>
            <button type="button" class="btn btn-outline btn-sm" id="btn-open-csv-import">
              ${uiIcon('upload', 13)} Import CSV
            </button>
          </div>
          <div>
            <button type="button" class="btn btn-primary btn-sm" id="btn-save-all-links">
              Save all links
            </button>
          </div>
        </div>
        <div class="unmatched-list">
          ${this.unmatched.map(u => {
            const isNonStandard = u.account_type && u.account_type !== "user";
            return `
            <div class="unmatched-item" data-login="${u.login}">
              <div class="unmatched-info" style="flex: 1; min-width: 220px;">
                <strong>@${u.login}</strong>
                <span class="risk-badge risk-${u.highest_risk.toLowerCase()}">${u.highest_risk}</span>
                ${isNonStandard ? `<span class="badge bg-secondary" title="${safe(u.note || '')}" style="font-size:10px;text-transform:uppercase;">${safe(u.account_type)}</span>` : ''}
                <small>${u.assignments_count} permission assignment${u.assignments_count === 1 ? "" : "s"}</small>
              </div>
              <div class="unmatched-action" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                <select class="form-control form-control-sm select-control classify-select" data-login="${u.login}" style="max-width:120px;font-size:11px;">
                  <option value="user" ${u.account_type === "user" ? "selected" : ""}>User</option>
                  <option value="bot" ${u.account_type === "bot" ? "selected" : ""}>Bot</option>
                  <option value="service" ${u.account_type === "service" ? "selected" : ""}>Service</option>
                  <option value="ignored" ${u.account_type === "ignored" ? "selected" : ""}>Ignored</option>
                </select>
                <input type="email" class="form-control form-control-sm unmatched-email-input" data-login="${u.login}" placeholder="employee@payhive.internal" style="max-width:200px;" />
                <button class="btn btn-sm btn-outline btn-map-account" data-login="${u.login}">Link</button>
              </div>
            </div>
            `;
          }).join("")}
        </div>
      `;
    }

    const cardHtml = `
      <div class="settings-card-heading">
        <span class="settings-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
        </span>
        <div>
          <h2>GitHub accounts with hidden emails <span class="badge ${count > 0 ? "bg-warning text-dark" : "bg-secondary"}">${count}</span></h2>
          <p>GitHub logins whose emails are private or hidden on GitHub. Enter their company email to link their identity and enable automated email notices.</p>
        </div>
      </div>
      ${rowsHtml}
    `;

    if (!card) {
      card = document.createElement("section");
      card.id = "unmatched-github-card";
      card.className = "card settings-card";
      // Insert after connected services card
      const servicesCard = document.querySelector(".settings-card:has(.settings-service)");
      if (servicesCard && servicesCard.parentNode) {
        servicesCard.parentNode.insertBefore(card, servicesCard.nextSibling);
      } else {
        container.appendChild(card);
      }
    }
    card.innerHTML = cardHtml;

    // Auto-suggest handler
    card.querySelector("#btn-auto-suggest")?.addEventListener("click", async () => {
      try {
        const suggestions = await window.ApiClient.getGitHubAutoSuggestions();
        let matchedCount = 0;
        suggestions.forEach(s => {
          const input = card.querySelector(`.unmatched-email-input[data-login="${s.login}"]`);
          if (input && !input.value) {
            input.value = s.suggestedEmail;
            input.style.borderColor = "#12b76a";
            input.title = `Suggested: ${s.suggestedName} (${Math.round(s.confidence * 100)}% match)`;
            matchedCount++;
          }
        });
        if (typeof window.showToast === "function") {
          window.showToast(`Found ${matchedCount} suggested matches. Review and click 'Save all links' to confirm.`);
        }
      } catch (err) {
        if (typeof window.showToast === "function") window.showToast("Could not fetch suggestions: " + err.message);
      }
    });

    // Save All handler (Bulk link)
    card.querySelector("#btn-save-all-links")?.addEventListener("click", async () => {
      const inputs = card.querySelectorAll(".unmatched-email-input");
      const mappings = [];
      inputs.forEach(inp => {
        const val = inp.value.trim();
        if (val) {
          mappings.push({ login: inp.dataset.login, email: val });
        }
      });

      if (!mappings.length) {
        if (typeof window.showToast === "function") window.showToast("No employee emails entered.");
        return;
      }

      try {
        const res = await window.ApiClient.bulkMapGitHub(mappings);
        if (typeof window.showToast === "function") window.showToast(`Successfully linked ${res.mappedCount} GitHub accounts.`);
        await this.init();
        if (window.currentDataMode === "live") {
          await window.ApiClient.loadAndRender();
        }
      } catch (err) {
        if (typeof window.showToast === "function") window.showToast("Bulk mapping failed: " + err.message);
      }
    });

    // Open CSV Import handler
    card.querySelector("#btn-open-csv-import")?.addEventListener("click", () => {
      this.openCsvImportModal();
    });

    // Classification change handler
    card.querySelectorAll(".classify-select").forEach(sel => {
      sel.addEventListener("change", (e) => {
        const login = sel.dataset.login;
        const newType = e.target.value;
        if (newType === "user") {
          window.ApiClient.classifyGitHubAccount(login, "user", "Reset to standard user").then(async () => {
            if (typeof window.showToast === "function") window.showToast(`@${login} set as standard user.`);
            await this.init();
            if (window.currentDataMode === "live") await window.ApiClient.loadAndRender();
          });
          return;
        }

        openDecision(
          `Classify @${login} as ${newType}?`,
          `Non-user accounts (${newType}) are excluded from unmatched employee alerts while remaining visible and audited for security.`,
          `@${login} · classification: ${newType}`,
          `Confirm ${newType}`,
          async (note) => {
            try {
              await window.ApiClient.classifyGitHubAccount(login, newType, note);
              decisionFeedback(`@${login} marked as ${newType}.`);
              await this.init();
              if (window.currentDataMode === "live") await window.ApiClient.loadAndRender();
            } catch (err) {
              console.error("Classification failed:", err);
            }
          },
          true
        );
      });
    });

    // Bind link account handlers
    card.querySelectorAll(".btn-map-account").forEach(btn => {
      btn.onclick = async () => {
        const login = btn.dataset.login;
        const item = btn.closest(".unmatched-item");
        const emailInput = item.querySelector(".unmatched-email-input");
        const email = emailInput?.value.trim();
        if (!email) {
          if (typeof window.showToast === "function") window.showToast("Please enter an employee email address.");
          return;
        }
        await this.mapAccount(login, email);
      };
    });
  },

  updateHeaderBadge() {
    const dryRunBadges = document.querySelectorAll(".dry-run-badge");
    dryRunBadges.forEach(badge => {
      badge.textContent = "LIVE GITHUB";
      badge.style.background = "rgba(34,197,94,0.12)";
      badge.style.color = "#16a34a";
      badge.style.border = "1px solid rgba(34,197,94,0.3)";
      badge.style.fontWeight = "700";
      badge.title = "Live GitHub Enforcement Active (payhive-eng)";
    });
  },

  openConnectModal() {
    const modal = document.querySelector("#review-modal");
    if (!modal) return;
    modal.classList.remove("is-audit-report");

    document.querySelector("#review-modal-body").innerHTML = `
      <div class="d-flex justify-content-between mb-3">
        <span class="eyebrow mb-0">INTEGRATION SETUP</span>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <h2 id="modal-title">Connect GitHub Organization</h2>
      <p>Configure read-only synchronization for organization repositories, teams, and members.</p>
      
      <div class="mb-3">
        <label class="field-label" for="gh-org-input">GitHub Organization</label>
        <input type="text" id="gh-org-input" class="form-control" placeholder="e.g. payhive-eng" value="${this.status?.org_name || "payhive-eng"}" required />
      </div>

      <div class="mb-3">
        <label class="field-label" for="gh-token-input">Personal Access Token (Fine-grained or Classic)</label>
        <input type="password" id="gh-token-input" class="form-control" placeholder="ghp_..." required />
        <small class="text-muted d-block mt-1">Requires read-only scopes: <code>read:org</code>, <code>repo</code>.</small>
      </div>

      <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="gh-sync-before-audit" ${this.status?.sync_before_audit ? "checked" : ""}>
        <label class="form-check-label" for="gh-sync-before-audit">
          Automatically synchronize GitHub permissions before scheduled audits
        </label>
      </div>

      <div class="review-detail-box">
        <strong>Security & Privacy Guarantee</strong>
        <span>Token is stored encrypted at rest on the server (AES-128-CBC) and is used exclusively for read-only audit requests. It is never logged or returned to the browser.</span>
      </div>

      <div class="review-modal-actions mt-3">
        <button class="btn btn-outline" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-primary" id="btn-submit-connect">Connect & Verify</button>
      </div>
    `;

    bootstrap.Modal.getOrCreateInstance(modal).show();

    document.getElementById("btn-submit-connect").onclick = async () => {
      const org = document.getElementById("gh-org-input").value.trim();
      const token = document.getElementById("gh-token-input").value.trim();
      const syncBefore = document.getElementById("gh-sync-before-audit").checked;

      if (!org || !token) {
        if (typeof window.showToast === "function") window.showToast("Organization and token are required.");
        return;
      }

      const submitBtn = document.getElementById("btn-submit-connect");
      submitBtn.disabled = true;
      submitBtn.textContent = "Verifying...";

      try {
        await window.ApiClient.configureGitHub(org, token, syncBefore);
        bootstrap.Modal.getInstance(modal)?.hide();
        if (typeof window.showToast === "function") window.showToast(`Connected to GitHub org '${org}'.`);
        await this.init();
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Connect & Verify";
        const msg = err?.message || "Failed to connect to GitHub.";
        if (typeof window.showToast === "function") window.showToast(msg);
      }
    };
  },

  async syncNow() {
    this.isSyncing = true;
    this.renderConnectedService();
    if (typeof window.showToast === "function") window.showToast("GitHub synchronization started...");

    try {
      const summary = await window.ApiClient.syncGitHub();
      this.isSyncing = false;
      const msg = `Sync completed (${summary.status}): ${summary.assignments_created} created, ${summary.assignments_updated} updated.`;
      if (typeof window.showToast === "function") window.showToast(msg);
      await this.init();

      // If in live mode, reload bootstrap state to show fresh findings
      if (window.currentDataMode === "live") {
        await window.ApiClient.loadAndRender();
      }
    } catch (err) {
      this.isSyncing = false;
      this.renderConnectedService();
      if (typeof window.showToast === "function") window.showToast("Sync failed: " + (err.message || "Unknown error"));
    }
  },

  async disconnect() {
    if (!confirm("Are you sure you want to disconnect GitHub? Imported data will remain available.")) return;

    try {
      await window.ApiClient.disconnectGitHub();
      if (typeof window.showToast === "function") window.showToast("GitHub integration disconnected.");
      await this.init();
    } catch (err) {
      if (typeof window.showToast === "function") window.showToast("Could not disconnect: " + err.message);
    }
  },

  openDataModeModal() {
    const modal = document.querySelector("#review-modal");
    if (!modal) return;
    modal.classList.remove("is-audit-report");

    const currentMode = "live";
    const targetMode = currentMode === "sample" ? "live" : "sample";
    const targetLabel = targetMode === "live" ? "Live Data (GitHub Org)" : "Sample Data (Demo)";

    document.querySelector("#review-modal-body").innerHTML = `
      <div class="d-flex justify-content-between mb-3">
        <span class="eyebrow mb-0">WORKSPACE CONFIGURATION</span>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <h2>Switch Data Mode to ${targetLabel}</h2>
      <p>
        ${targetMode === "live" 
          ? "Switching to Live mode displays real permissions, collaborators, and audit findings imported from your connected GitHub organization. Sample demonstration records are safely preserved in the database." 
          : "Switching to Sample mode restores the built-in demonstration records and scenario evaluations. Your live GitHub imports remain preserved."}
      </p>

      <div class="review-detail-box">
        <strong>Current Mode: ${currentMode.toUpperCase()} &rarr; Target: ${targetMode.toUpperCase()}</strong>
        <span>Switching modes alters the active view across the Overview dashboard, Access audit table, and Run audit findings. Decisions and history remain intact.</span>
      </div>

      <div class="review-modal-actions mt-3">
        <button class="btn btn-outline" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-primary" id="btn-confirm-datamode">Switch to ${targetMode.toUpperCase()}</button>
      </div>
    `;

    bootstrap.Modal.getOrCreateInstance(modal).show();

    document.getElementById("btn-confirm-datamode").onclick = async () => {
      try {
        await window.ApiClient.setDataMode(targetMode);
        window.currentDataMode = targetMode;
        bootstrap.Modal.getInstance(modal)?.hide();
        if (typeof window.showToast === "function") window.showToast(`Switched workspace data mode to ${targetMode.toUpperCase()}.`);
        await window.ApiClient.loadAndRender();
        this.updateHeaderBadge();
        if (location.hash === "#settings") {
          await this.init();
        }
      } catch (err) {
        if (typeof window.showToast === "function") window.showToast("Could not switch data mode: " + err.message);
      }
    };
  },

  openCsvImportModal() {
    const modal = document.querySelector("#review-modal");
    if (!modal) return;
    modal.classList.remove("is-audit-report");

    document.querySelector("#review-modal-body").innerHTML = `
      <div class="d-flex justify-content-between mb-3">
        <span class="eyebrow mb-0">BULK TRIAGE & IMPORT</span>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <h2>Import Identities & GitHub Logins from CSV</h2>
      <p>Upload or paste CSV data with columns: <code>github_login,email,name,team,employment_status</code>.</p>

      <div class="mb-3">
        <label class="field-label" for="csv-text-input">CSV Content</label>
        <textarea id="csv-text-input" class="form-control" rows="5" placeholder="github_login,email,name,team,employment_status&#10;suleman049,suleman@payhive.internal,Suleman,Engineering,Active"></textarea>
      </div>

      <div id="csv-preview-area" class="mb-3" style="display:none;"></div>

      <div class="review-modal-actions mt-3">
        <button class="btn btn-outline" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-outline" id="btn-run-csv-preview">Preview Validation</button>
        <button class="btn btn-primary" id="btn-run-csv-confirm" disabled>Confirm Import</button>
      </div>
    `;

    bootstrap.Modal.getOrCreateInstance(modal).show();

    let validRowsToImport = [];

    document.getElementById("btn-run-csv-preview").onclick = async () => {
      const text = document.getElementById("csv-text-input").value.trim();
      const previewArea = document.getElementById("csv-preview-area");
      const confirmBtn = document.getElementById("btn-run-csv-confirm");

      if (!text) {
        if (typeof window.showToast === "function") window.showToast("Please enter CSV content.");
        return;
      }

      try {
        const res = await window.ApiClient.previewCsvImport(text);
        validRowsToImport = res.validRows;
        previewArea.style.display = "block";

        if (res.canImport) {
          previewArea.innerHTML = `
            <div class="alert alert-success p-2" style="font-size:12px;">
              ${uiIcon('check', 13)} Validated ${res.validRows.length} identity row(s). Ready to import.
            </div>
          `;
          confirmBtn.disabled = false;
        } else {
          previewArea.innerHTML = `
            <div class="alert alert-danger p-2" style="font-size:12px;">
              Found ${res.errorRows.length} error(s) in CSV. Please fix errors before confirming.
              <ul class="mb-0 mt-1">
                ${res.errorRows.map(e => `<li>Line ${e.line}: ${e.errors.join(", ")}</li>`).join("")}
              </ul>
            </div>
          `;
          confirmBtn.disabled = true;
        }
      } catch (err) {
        if (typeof window.showToast === "function") window.showToast("Preview failed: " + err.message);
      }
    };

    document.getElementById("btn-run-csv-confirm").onclick = async () => {
      try {
        const res = await window.ApiClient.confirmCsvImport(validRowsToImport, "Bulk CSV import via settings");
        bootstrap.Modal.getInstance(modal)?.hide();
        if (typeof window.showToast === "function") window.showToast(`Imported ${res.imported} new and updated ${res.updated} identities.`);
        await this.init();
        if (window.currentDataMode === "live") {
          await window.ApiClient.loadAndRender();
        }
      } catch (err) {
        if (typeof window.showToast === "function") window.showToast("Import failed: " + err.message);
      }
    };
  },

  async mapAccount(login, email) {
    try {
      await window.ApiClient.mapGitHubAccount(login, email);
      if (typeof window.showToast === "function") window.showToast(`Mapped @${login} to ${email}.`);
      await this.init();
      if (window.currentDataMode === "live") {
        await window.ApiClient.loadAndRender();
      }
    } catch (err) {
      if (typeof window.showToast === "function") window.showToast("Mapping failed: " + (err.message || "Invalid employee email."));
    }
  }
};

window.GitHubSettings = GitHubSettings;

// Hook into settings rendering
if (typeof window !== "undefined") {
  window.addEventListener("hashchange", () => {
    if (location.hash === "#settings") {
      setTimeout(() => GitHubSettings.init(), 60);
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    GitHubSettings.updateHeaderBadge();
    if (location.hash === "#settings") {
      setTimeout(() => GitHubSettings.init(), 60);
    }
  });
}
