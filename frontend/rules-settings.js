// AccessReaper v2 — Risk Rules Settings Component (Phase 2)
// Provides editable scoring weights, thresholds, impact dry-preview, and version rollback.

const RulesSettings = {
  activeVersion: 1,
  activePayload: null,
  history: [],
  previewResult: null,
  previewLoading: false,
  initialized: false,

  async init() {
    if (this.initialized) return;
    this.initialized = true;
    await this.fetchRules();
    if (location.hash.slice(1).split('?')[0] === 'settings') {
      const card = document.querySelector('#risk-rules-settings-card');
      if (card) {
        const div = document.createElement('div');
        div.innerHTML = this.renderCard();
        const newCard = div.firstElementChild;
        if (newCard) {
          card.replaceWith(newCard);
          this.attachEvents(document.querySelector('#page-content') || document);
        }
      }
    }
  },

  async fetchRules() {
    try {
      if (window.ApiClient && !window.ApiClient.isDemoMode) {
        const res = await ApiClient.getRules();
        this.activeVersion = res.active?.version || 1;
        this.activePayload = res.active?.payload || this.getDefaultConfig();
        this.history = res.history || [];
      } else {
        this.activeVersion = 1;
        this.activePayload = this.getDefaultConfig();
        this.history = [{
          version: 1,
          createdBy: "System baseline",
          createdAt: "2026-10-14T09:00:00+05:00",
          note: "Default baseline rule weights",
          isActive: true
        }];
      }
    } catch (err) {
      console.warn("Could not fetch rules:", err);
      this.activePayload = this.getDefaultConfig();
    }
  },

  getDefaultConfig() {
    return {
      dormantDays: 90,
      thresholds: { highMin: 70, mediumMin: 40 },
      points: {
        dormant: 40,
        projectMismatch: 30,
        elevatedAccess: 20,
        sensitiveResource: 10,
        formerEmployee: 80,
        contractorAdmin: 50,
        firestoreAdmin: 50,
        directAdminBypass: 40,
        privilegedInactive: 40,
        unmatchedAccount: 40,
        unmatchedAccountElevated: 70,
        sodConflict: 50,
        busFactor: 30,
        archivedRepo: 40,
        inactiveOutsideCollaborator: 50,
        dormantIdentity: 30,
      },
      rulesEnabled: {
        dormant: true,
        projectMismatch: true,
        elevatedAccess: true,
        sensitiveResource: true,
        formerEmployee: true,
        contractorAdmin: true,
        firestoreAdmin: true,
        directAdminBypass: true,
        privilegedInactive: true,
        unmatchedAccount: true,
        sodConflict: true,
        busFactor: true,
        archivedRepo: true,
        inactiveOutsideCollaborator: true,
        dormantIdentity: true,
      }
    };
  },

  renderCard() {
    const payload = this.activePayload || this.getDefaultConfig();
    const pts = payload.points || {};
    const th = payload.thresholds || { highMin: 70, mediumMin: 40 };
    const enabled = payload.rulesEnabled || {};

    let previewHtml = "";
    if (this.previewResult) {
      const s = this.previewResult.summary;
      const changes = this.previewResult.changes || [];
      const changeRows = changes.map(c => `
        <tr>
          <td><b>${safe(c.name)}</b><br><small class="text-muted">${safe(c.resource)}</small></td>
          <td><span class="status-badge ${c.oldRisk.toLowerCase()}">${safe(c.oldRisk)}</span> (${c.oldScore} pts)</td>
          <td>&rarr;</td>
          <td><span class="status-badge ${c.newRisk.toLowerCase()}">${safe(c.newRisk)}</span> (${c.newScore} pts)</td>
        </tr>
      `).join("");

      previewHtml = `
        <div class="rules-preview-box">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <strong>Preview Impact Analysis (Policy Simulation)</strong>
            <button type="button" class="btn btn-outline btn-sm" id="btn-close-preview">&times; Close preview</button>
          </div>
          <p class="text-muted" style="font-size: 12px; margin: 0 0 8px;">
            Simulated impact on current workspace assignments if these rules are activated:
          </p>
          <div class="rules-preview-counts">
            <div class="rules-preview-stat">
              <span>High Risk</span>
              <strong style="color: var(--red);">${s.currentHigh} &rarr; ${s.high}</strong>
            </div>
            <div class="rules-preview-stat">
              <span>Medium Risk</span>
              <strong style="color: var(--amber);">${s.currentMedium} &rarr; ${s.medium}</strong>
            </div>
            <div class="rules-preview-stat">
              <span>Healthy (Low)</span>
              <strong style="color: var(--green);">${s.currentLow} &rarr; ${s.low}</strong>
            </div>
          </div>
          ${changes.length ? `
            <div style="margin-top: 10px;">
              <small style="font-weight: 600;">Affected assignments (${changes.length}):</small>
              <table class="table table-sm" style="font-size: 11px; margin-top: 6px;">
                <tbody>${changeRows}</tbody>
              </table>
            </div>
          ` : '<p style="font-size: 12px; color: var(--green); margin: 6px 0 0;">No existing assignments change risk level under this configuration.</p>'}
        </div>
      `;
    }

    // Version history rows
    const historyRows = (this.history || []).map(h => {
      let dateStr = "—";
      if (h.createdAt) {
        try {
          dateStr = new Date(h.createdAt).toLocaleDateString("en-US", {
            timeZone: "Asia/Karachi",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          });
        } catch {
          dateStr = String(h.createdAt);
        }
      }

      const isCurrent = h.version === this.activeVersion || h.isActive;
      return `
        <tr>
          <td><b>v${h.version}</b></td>
          <td>${safe(h.createdBy || "Admin")}</td>
          <td><small class="text-muted">${safe(dateStr)}</small></td>
          <td><span title="${safe(h.note)}">${safe(h.note || "No note recorded")}</span></td>
          <td style="text-align: right;">
            ${isCurrent ? '<span class="status-badge approved">Active</span>' : `<button type="button" class="btn btn-outline btn-sm" data-restore-version="${h.version}">Restore</button>`}
          </td>
        </tr>
      `;
    }).join("");

    return `
      <section class="card settings-card" id="risk-rules-settings-card">
        <div class="settings-card-heading">
          <span class="settings-icon">${uiIcon('scale', 18)}</span>
          <div>
            <h2>Risk scoring rules</h2>
            <p>Configurable scoring weights, dormancy threshold, and risk cutoffs. Currently active: <b>Version ${this.activeVersion}</b></p>
          </div>
        </div>

        <form id="rules-config-form" class="rules-config-section">
          <!-- Thresholds Block -->
          <div style="margin-bottom: 6px;">
            <span class="section-eyebrow" style="font-size: 11px; letter-spacing: 0.8px;">SEVERITY THRESHOLDS & DORMANCY</span>
          </div>
          <div class="rules-config-grid">
            <div class="rule-input-group">
              <label for="rule-dormant-days">Inactivity threshold (days)</label>
              <input type="number" id="rule-dormant-days" class="form-control" min="1" max="3650" value="${payload.dormantDays || 90}">
              <small>Days without recorded activity to flag as dormant (default: 90)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-high-min">High risk minimum points</label>
              <input type="number" id="rule-high-min" class="form-control" min="1" max="200" value="${th.highMin || 70}">
              <small>Assignments scoring at or above this are High risk (default: 70)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-medium-min">Medium risk minimum points</label>
              <input type="number" id="rule-medium-min" class="form-control" min="1" max="200" value="${th.mediumMin || 40}">
              <small>Assignments scoring at or above this are Medium risk (default: 40)</small>
            </div>
          </div>

          <!-- Base Rule Weights -->
          <div style="margin: 12px 0 6px;">
            <span class="section-eyebrow" style="font-size: 11px; letter-spacing: 0.8px;">BASE SCORING RULE WEIGHTS</span>
          </div>
          <div class="rules-config-grid">
            <div class="rule-input-group">
              <label for="rule-pts-dormant">
                <span>Dormant account points</span>
                <input type="checkbox" id="rule-en-dormant" ${enabled.dormant !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-dormant" class="form-control" min="0" max="100" value="${pts.dormant ?? 40}">
              <small>Points when inactive &ge; threshold (default: 40)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-mismatch">
                <span>Project / Team mismatch</span>
                <input type="checkbox" id="rule-en-mismatch" ${enabled.projectMismatch !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-mismatch" class="form-control" min="0" max="100" value="${pts.projectMismatch ?? 30}">
              <small>Points when repo project differs from user team (default: 30)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-elevated">
                <span>Elevated access (Admin / Write)</span>
                <input type="checkbox" id="rule-en-elevated" ${enabled.elevatedAccess !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-elevated" class="form-control" min="0" max="100" value="${pts.elevatedAccess ?? 20}">
              <small>Points for Admin or Write permission level (default: 20)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-sensitive">
                <span>Sensitive resource</span>
                <input type="checkbox" id="rule-en-sensitive" ${enabled.sensitiveResource !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-sensitive" class="form-control" min="0" max="100" value="${pts.sensitiveResource ?? 10}">
              <small>Points for production or sensitive infrastructure (default: 10)</small>
            </div>
          </div>

          <!-- Named Frontend Rules -->
          <div style="margin: 12px 0 6px;">
            <span class="section-eyebrow" style="font-size: 11px; letter-spacing: 0.8px;">NAMED IAM PATTERN RULES</span>
          </div>
          <div class="rules-config-grid">
            <div class="rule-input-group">
              <label for="rule-pts-former">
                <span>Former employee active</span>
                <input type="checkbox" id="rule-en-former" ${enabled.formerEmployee !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-former" class="form-control" min="0" max="100" value="${pts.formerEmployee ?? 80}">
              <small>Ex-employee account still active (default: 80, High)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-contractor">
                <span>Contractor with Admin</span>
                <input type="checkbox" id="rule-en-contractor" ${enabled.contractorAdmin !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-contractor" class="form-control" min="0" max="100" value="${pts.contractorAdmin ?? 50}">
              <small>External contractor with administrator rights (default: 50)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-firestore">
                <span>Firestore admin beyond duties</span>
                <input type="checkbox" id="rule-en-firestore" ${enabled.firestoreAdmin !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-firestore" class="form-control" min="0" max="100" value="${pts.firestoreAdmin ?? 50}">
              <small>Application admin role exceeding support role (default: 50)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-bypass">
                <span>Direct admin grant bypass</span>
                <input type="checkbox" id="rule-en-bypass" ${enabled.directAdminBypass !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-bypass" class="form-control" min="0" max="100" value="${pts.directAdminBypass ?? 40}">
              <small>Direct grant bypassing policy (default: 40)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-privileged">
                <span>Privileged inactive account</span>
                <input type="checkbox" id="rule-en-privileged" ${enabled.privilegedInactive !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-privileged" class="form-control" min="0" max="100" value="${pts.privilegedInactive ?? 40}">
              <small>Elevated privileges with no recent activity (default: 40)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-unmatched">
                <span>Unmatched account (Standard Read)</span>
                <input type="checkbox" id="rule-en-unmatched" ${enabled.unmatchedAccount !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-unmatched" class="form-control" min="0" max="100" value="${pts.unmatchedAccount ?? 40}">
              <small>Unlinked GitHub account with standard access (default: 40)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-unmatched-elevated">
                <span>Unmatched account (Admin / Write)</span>
              </label>
              <input type="number" id="rule-pts-unmatched-elevated" class="form-control" min="0" max="100" value="${pts.unmatchedAccountElevated ?? 70}">
              <small>Unlinked GitHub account with Admin or Write (default: 70, High)</small>
            </div>
          </div>

          <!-- Separation of Duties & Orphan Rules -->
          <div style="margin: 12px 0 6px;">
            <span class="section-eyebrow" style="font-size: 11px; letter-spacing: 0.8px;">SEPARATION OF DUTIES &amp; ORPHAN RULES</span>
          </div>
          <div class="rules-config-grid">
            <div class="rule-input-group">
              <label for="rule-pts-sod">
                <span>Separation of Duties conflict</span>
                <input type="checkbox" id="rule-en-sod" ${enabled.sodConflict !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-sod" class="form-control" min="0" max="100" value="${pts.sodConflict ?? 50}">
              <small>Conflicting cross-domain privileges (default: 50)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-busfactor">
                <span>Repository bus-factor (&le; 1 admin)</span>
                <input type="checkbox" id="rule-en-busfactor" ${enabled.busFactor !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-busfactor" class="form-control" min="0" max="100" value="${pts.busFactor ?? 30}">
              <small>Single point of failure admin coverage (default: 30)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-archived">
                <span>Archived repo Write/Admin</span>
                <input type="checkbox" id="rule-en-archived" ${enabled.archivedRepo !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-archived" class="form-control" min="0" max="100" value="${pts.archivedRepo ?? 40}">
              <small>Write/Admin on archived repository (default: 40)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-inactive-collab">
                <span>Inactive outside collaborator</span>
                <input type="checkbox" id="rule-en-inactive-collab" ${enabled.inactiveOutsideCollaborator !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-inactive-collab" class="form-control" min="0" max="100" value="${pts.inactiveOutsideCollaborator ?? 50}">
              <small>Contractor with Admin/Write inactive &gt; 30d (default: 50)</small>
            </div>
            <div class="rule-input-group">
              <label for="rule-pts-dormant-identity">
                <span>Active identity with 0 assignments</span>
                <input type="checkbox" id="rule-en-dormant-identity" ${enabled.dormantIdentity !== false ? "checked" : ""}>
              </label>
              <input type="number" id="rule-pts-dormant-identity" class="form-control" min="0" max="100" value="${pts.dormantIdentity ?? 30}">
              <small>Active employee with no assigned resources (default: 30)</small>
            </div>
          </div>

          ${previewHtml}

          <div class="rules-actions-bar">
            <div>
              <button type="button" class="btn btn-outline" id="btn-preview-rules">Preview impact</button>
            </div>
            <div>
              <button type="button" class="btn btn-primary" id="btn-save-rules">Save as new version</button>
            </div>
          </div>
        </form>

        <!-- Version History Section -->
        <div style="padding: 16px 20px; border-top: 1px solid var(--border);">
          <div style="margin-bottom: 8px;">
            <span class="section-eyebrow" style="font-size: 11px;">RULE CONFIGURATION VERSION HISTORY</span>
          </div>
          <div class="table-responsive">
            <table class="rules-history-table">
              <thead>
                <tr>
                  <th>VERSION</th>
                  <th>CREATED BY</th>
                  <th>DATE</th>
                  <th>NOTE</th>
                  <th style="text-align: right;">STATUS</th>
                </tr>
              </thead>
              <tbody>
                ${historyRows || '<tr><td colspan="5" class="text-muted">No historical versions recorded.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    `;
  },

  getFormPayload() {
    const val = id => parseInt(document.querySelector(`#${id}`)?.value || "0", 10);
    const chk = id => Boolean(document.querySelector(`#${id}`)?.checked);

    const dormantDays = val("rule-dormant-days");
    const highMin = val("rule-high-min");
    const mediumMin = val("rule-medium-min");

    if (mediumMin >= highMin) {
      if (typeof showToast === "function") showToast("Validation error: Medium cutoff must be strictly less than High cutoff.");
      return null;
    }

    return {
      dormantDays,
      thresholds: { highMin, mediumMin },
      points: {
        dormant: val("rule-pts-dormant"),
        projectMismatch: val("rule-pts-mismatch"),
        elevatedAccess: val("rule-pts-elevated"),
        sensitiveResource: val("rule-pts-sensitive"),
        formerEmployee: val("rule-pts-former"),
        contractorAdmin: val("rule-pts-contractor"),
        firestoreAdmin: val("rule-pts-firestore"),
        directAdminBypass: val("rule-pts-bypass"),
        privilegedInactive: val("rule-pts-privileged"),
        unmatchedAccount: val("rule-pts-unmatched") || 40,
        unmatchedAccountElevated: val("rule-pts-unmatched-elevated") || 70,
        sodConflict: val("rule-pts-sod") || 50,
        busFactor: val("rule-pts-busfactor") || 30,
        archivedRepo: val("rule-pts-archived") || 40,
        inactiveOutsideCollaborator: val("rule-pts-inactive-collab") || 50,
        dormantIdentity: val("rule-pts-dormant-identity") || 30,
      },
      rulesEnabled: {
        dormant: chk("rule-en-dormant"),
        projectMismatch: chk("rule-en-mismatch"),
        elevatedAccess: chk("rule-en-elevated"),
        sensitiveResource: chk("rule-en-sensitive"),
        formerEmployee: chk("rule-en-former"),
        contractorAdmin: chk("rule-en-contractor"),
        firestoreAdmin: chk("rule-en-firestore"),
        directAdminBypass: chk("rule-en-bypass"),
        privilegedInactive: chk("rule-en-privileged"),
        unmatchedAccount: chk("rule-en-unmatched"),
        sodConflict: chk("rule-en-sod"),
        busFactor: chk("rule-en-busfactor"),
        archivedRepo: chk("rule-en-archived"),
        inactiveOutsideCollaborator: chk("rule-en-inactive-collab"),
        dormantIdentity: chk("rule-en-dormant-identity"),
      }
    };
  },

  attachEvents(container) {
    // Preview Impact button
    container.querySelector("#btn-preview-rules")?.addEventListener("click", async () => {
      const payload = this.getFormPayload();
      if (!payload) return;
      try {
        if (window.ApiClient && !window.ApiClient.isDemoMode) {
          const res = await ApiClient.previewRules(payload);
          this.previewResult = res;
        } else {
          this.previewResult = {
            summary: { high: 6, medium: 1, low: 5, currentHigh: 6, currentMedium: 1, currentLow: 5 },
            changes: []
          };
        }
        if (typeof render === "function") render();
      } catch (err) {
        console.error("Preview failed:", err);
      }
    });

    // Close preview button
    container.querySelector("#btn-close-preview")?.addEventListener("click", () => {
      this.previewResult = null;
      if (typeof render === "function") render();
    });

    // Save as new version
    container.querySelector("#btn-save-rules")?.addEventListener("click", () => {
      const payload = this.getFormPayload();
      if (!payload) return;

      openDecision(
        "Save new rule configuration?",
        "Activate these scoring weights as the new active rule version. Subsequent audits will evaluate risk using this version.",
        `New rule version · Thresholds: ${payload.thresholds.mediumMin}/${payload.thresholds.highMin}`,
        "Save and activate",
        async (note) => {
          try {
            await ApiClient.createRuleConfig(payload, note);
            decisionFeedback("New risk rule version activated.");
            this.previewResult = null;
            await this.fetchRules();
            if (typeof render === "function") render();
          } catch (err) {
            console.error("Failed to save rules:", err);
          }
        },
        true
      );
    });

    // Restore old version
    container.querySelectorAll("[data-restore-version]").forEach(btn => {
      btn.addEventListener("click", () => {
        const version = parseInt(btn.dataset.restoreVersion, 10);
        openDecision(
          `Restore rule configuration version ${version}?`,
          `Roll back the active scoring weights to version ${version}. Subsequent audits will use these weights.`,
          `Rollback to v${version}`,
          "Restore version",
          async (note) => {
            try {
              await ApiClient.rollbackRuleConfig(version);
              decisionFeedback(`Rule configuration v${version} restored.`);
              this.previewResult = null;
              await this.fetchRules();
              if (typeof render === "function") render();
            } catch (err) {
              console.error("Failed to rollback rules:", err);
            }
          },
          false
        );
      });
    });
  }
};

window.RulesSettings = RulesSettings;
