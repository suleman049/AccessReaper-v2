// AccessReaper v2 — Workspace User & People Management View (Phase 2 & Stage 2)
// Handles listing Firestore profiles, pending signups, and organization People identities.

const UsersPage = {
  activeTab: "users", // "users" or "people"
  peopleFilter: "all", // "all", "active", "contractor", "former"
  statusFilter: "all",
  searchQuery: "",
  users: [],
  people: [],
  peopleSearch: "",
  configured: true,
  unconfiguredMessage: "",
  loading: false,

  async fetchUsers() {
    this.loading = true;
    try {
      if (window.ApiClient && !window.ApiClient.isDemoMode) {
        const res = await ApiClient.getUsers(this.statusFilter, this.searchQuery);
        this.configured = res.configured;
        this.unconfiguredMessage = res.message || "";
        this.users = res.users || [];
        this.updateNavBadge();
      } else {
        this.configured = false;
        this.unconfiguredMessage = "Service account not configured in demo mode.";
        this.users = [];
      }
    } catch (err) {
      console.warn("Could not fetch users:", err);
      this.configured = false;
    } finally {
      this.loading = false;
    }
  },

  async fetchPeople() {
    try {
      if (window.ApiClient && !window.ApiClient.isDemoMode) {
        this.people = await ApiClient.getIdentities();
      } else {
        this.people = [];
      }
    } catch (err) {
      console.warn("Could not fetch people:", err);
    }
  },

  updateNavBadge() {
    const badge = document.querySelector("#nav-user-count");
    if (!badge) return;
    const pendingCount = (this.users || []).filter(u => u.status === "pending").length;
    badge.textContent = pendingCount;
    badge.style.display = pendingCount > 0 ? "" : "none";
  },

  renderPeopleTab() {
    const q = this.peopleSearch.toLowerCase().trim();
    const filter = this.peopleFilter || 'all';
    const filtered = (this.people || []).filter(p => {
      if (filter === 'active' && p.employment_status !== 'active') return false;
      if (filter === 'contractor' && p.employment_status !== 'contractor' && !(p.job_role || '').toLowerCase().includes('contractor') && p.team !== 'External') return false;
      if (filter === 'former' && p.employment_status !== 'former') return false;
      const matchText = `${p.name} ${p.email} ${p.team} ${p.job_role} ${p.github_login || ""}`.toLowerCase();
      return !q || matchText.includes(q);
    });

    return `
      <div class="card users-tools-card mb-3">
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <button type="button" class="btn btn-primary btn-sm" id="btn-add-person">
            + Add Person
          </button>
          <button type="button" class="btn btn-outline btn-sm" id="btn-people-import-csv">
            ${uiIcon('upload', 13)} Import CSV
          </button>
          <div class="ms-md-3 d-flex align-items-center gap-1 flex-wrap">
            <button type="button" class="btn btn-sm ${filter === 'all' ? 'btn-primary' : 'btn-outline'}" data-people-filter="all" style="border-radius:16px;font-size:12px;font-weight:600;">
              All (${(this.people||[]).length})
            </button>
            <button type="button" class="btn btn-sm ${filter === 'active' ? 'btn-primary' : 'btn-outline'}" data-people-filter="active" style="border-radius:16px;font-size:12px;font-weight:600;">
              Active Employees (${(this.people||[]).filter(p => p.employment_status === 'active').length})
            </button>
            <button type="button" class="btn btn-sm ${filter === 'contractor' ? 'btn-primary' : 'btn-outline'}" data-people-filter="contractor" style="border-radius:16px;font-size:12px;font-weight:600;">
              Contractors (${(this.people||[]).filter(p => p.employment_status === 'contractor' || p.team === 'External' || (p.job_role || '').toLowerCase().includes('contractor')).length})
            </button>
            <button type="button" class="btn btn-sm ${filter === 'former' ? 'btn-primary' : 'btn-outline'}" data-people-filter="former" style="border-radius:16px;font-size:12px;font-weight:600;${filter === 'former' ? 'background:#ef4444;border-color:#ef4444;' : ''}">
              Offboarded (${(this.people||[]).filter(p => p.employment_status === 'former').length})
            </button>
          </div>
        </div>
        <div class="search-control" style="max-width: 300px;">
          <span class="search-control-icon">${uiIcon("search")}</span>
          <input type="search" id="people-search" class="form-control" placeholder="Search people or team…" value="${safe(this.peopleSearch)}">
        </div>
      </div>

      <div class="card table-panel">
        <div class="table-responsive">
          <table class="table mb-0 align-middle">
            <thead>
              <tr>
                <th style="padding-left: 20px;">PERSON</th>
                <th>ROLE / TITLE</th>
                <th>TEAM</th>
                <th>STATUS</th>
                <th>LINKED GITHUB</th>
                <th style="text-align: right; padding-right: 20px;">ACTION</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.length ? filtered.map(p => {
                const statusTone = p.employment_status === "active" ? "approved" : p.employment_status === "contractor" ? "pending" : "declined";
                return `
                  <tr>
                    <td style="padding-left: 20px;">
                      <div class="d-flex align-items-center gap-2">
                        <span class="identity-avatar">${safe(p.initials || "U")}</span>
                        <div>
                          <strong>${safe(p.name)}</strong>
                          <small class="d-block text-muted">${safe(p.email)}</small>
                        </div>
                      </div>
                    </td>
                    <td>${safe(p.job_role || "Team member")}</td>
                    <td>${safe(p.team || "Engineering")}</td>
                    <td>
                      <span class="status-badge ${statusTone}" style="text-transform: capitalize;">
                        ${safe(p.employment_status)}
                      </span>
                    </td>
                    <td>
                      ${p.github_login ? `<code>@${safe(p.github_login)}</code>` : `<span class="text-muted">Unlinked</span>`}
                    </td>
                    <td style="text-align: right; padding-right: 20px;">
                      <div class="d-flex align-items-center justify-content-end gap-2">
                        <button type="button" class="btn btn-outline btn-sm btn-edit-person" data-email="${safe(p.email)}">
                          Edit
                        </button>
                        ${p.employment_status !== "former" ? `
                          <button type="button" class="btn btn-sm btn-outline-danger btn-offboard-person" data-email="${safe(p.email)}" data-name="${safe(p.name)}" style="border-color:#ef4444;color:#ef4444;font-size:12px;" title="One-Click Employee Offboarding Wipe">
                            ${uiIcon('userX', 13)} Offboard
                          </button>
                        ` : `<span class="badge" style="background:rgba(239,68,68,0.1);color:#ef4444;font-size:11px;font-weight:600;">Offboarded</span>`}
                      </div>
                    </td>
                  </tr>
                `;
              }).join("") : `
                <tr>
                  <td colspan="6" class="text-center p-4 text-muted">
                    No people found. Click "+ Add Person" or "Import CSV" to add organization identities.
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },

  renderUsersTab() {
    let bannerHtml = "";
    if (!this.configured) {
      bannerHtml = `
        <div class="unconfigured-notice">
          <div style="font-size: 24px; color: var(--muted, #94a3b8);">${uiIcon('settings', 32)}</div>
          <div>
            <strong>Service account not configured</strong>
            <p>${safe(this.unconfiguredMessage || "To manage workspace accounts, configure the Firebase service account private key.")}</p>
            <ol>
              <li>Go to <b>Firebase Console</b> &rarr; <b>Project settings</b> &rarr; <b>Service accounts</b>.</li>
              <li>Click <b>Generate new private key</b>.</li>
              <li>Save the key file as: <code>backend/secrets/firebase-service-account.json</code></li>
              <li>Reload this screen.</li>
            </ol>
          </div>
        </div>
      `;
    }

    const filterPills = [
      ["all", "All users"],
      ["pending", "Pending signups"],
      ["active", "Active admins"],
      ["disabled", "Disabled / Rejected"],
    ];

    const toolsHtml = this.configured ? `
      <div class="card users-tools-card">
        <div class="users-status-pills">
          ${filterPills.map(([f, label]) => `
            <button type="button" class="user-status-btn ${this.statusFilter === f ? "active" : ""}" data-user-filter="${f}">
              ${label}
            </button>
          `).join("")}
        </div>
        <div class="search-control" style="max-width: 300px;">
          <span class="search-control-icon">${uiIcon("search")}</span>
          <input type="search" id="users-search" class="form-control" placeholder="Search by name or email…" value="${safe(this.searchQuery)}">
        </div>
      </div>
    ` : "";

    let rowsHtml = "";
    if (this.users.length === 0) {
      rowsHtml = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 36px 20px; color: var(--muted);">
            No workspace users match your filter criteria.
          </td>
        </tr>
      `;
    } else {
      rowsHtml = this.users.map(u => {
        const isPending = u.status === "pending";
        const isActive = u.status === "active";
        const isDisabled = u.status === "disabled" || u.status === "rejected";

        let statusClass = "pending";
        if (isActive) statusClass = "approved";
        if (isDisabled) statusClass = "declined";

        return `
          <tr data-user-uid="${safe(u.uid)}">
            <td style="padding-left: 20px;">
              <div class="d-flex align-items-center gap-2">
                <span class="identity-avatar">${safe(u.initials || "U")}</span>
                <div>
                  <strong>${safe(u.name || "Unknown Name")}</strong>
                  <small class="d-block text-muted">${safe(u.email)}</small>
                </div>
              </div>
            </td>
            <td>${safe(u.role || "pending")}</td>
            <td><span class="status-badge ${statusClass}">${safe(u.status || "pending")}</span></td>
            <td><small class="text-muted">${safe(u.createdAt ? new Date(u.createdAt).toLocaleDateString() : "—")}</small></td>
            <td style="padding-right: 20px;">
              <div class="users-actions-cell">
                ${isPending ? `
                  <button type="button" class="btn btn-outline btn-sm text-danger" data-user-reject="${safe(u.uid)}">Reject</button>
                  <button type="button" class="btn btn-primary btn-sm" data-user-activate="${safe(u.uid)}">Activate</button>
                ` : ""}
                ${isActive ? `
                  <button type="button" class="btn btn-outline btn-sm text-danger" data-user-deactivate="${safe(u.uid)}">Deactivate</button>
                ` : ""}
                ${isDisabled ? `
                  <button type="button" class="btn btn-outline btn-sm" data-user-activate="${safe(u.uid)}">Reactivate</button>
                ` : ""}
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }

    const tableHtml = this.configured ? `
      <div class="card table-panel">
        <div class="table-responsive">
          <table class="table mb-0 align-middle">
            <thead>
              <tr>
                <th style="padding-left: 20px;">USER</th>
                <th>ROLE</th>
                <th>STATUS</th>
                <th>CREATED</th>
                <th style="text-align: right; padding-right: 20px;">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      </div>
    ` : "";

    return `${bannerHtml}${toolsHtml}${tableHtml}`;
  },

  render() {
    const container = document.createElement("div");
    container.className = "users-workbench";

    const isPeople = this.activeTab === "people";

    const headingHtml = `
      <div class="page-heading">
        <div>
          <h1>${isPeople ? "Organization People" : "Workspace Users"}</h1>
          <p>${isPeople ? "Manage employee identities, organizational teams, and linked GitHub accounts." : "Activate new administrator signups and manage workspace access."}</p>
        </div>
      </div>
      <div class="segmented mb-3" id="users-tab-bar" style="max-width: 380px;">
        <button type="button" class="${this.activeTab === 'users' ? 'active' : ''}" data-tab="users">Workspace Admins</button>
        <button type="button" class="${this.activeTab === 'people' ? 'active' : ''}" data-tab="people">People (Identities)</button>
      </div>
    `;

    container.innerHTML = headingHtml + (isPeople ? this.renderPeopleTab() : this.renderUsersTab());
    this.attachEvents(container);
    return container.outerHTML;
  },

  openAddPersonModal() {
    const modal = document.querySelector("#review-modal");
    if (!modal) return;
    modal.classList.remove("is-audit-report");

    document.querySelector("#review-modal-body").innerHTML = `
      <div class="d-flex justify-content-between mb-3">
        <span class="eyebrow mb-0">PEOPLE MANAGEMENT</span>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <h2>Add New Person</h2>
      <p>Register an employee identity in payhive-eng organization directory.</p>

      <div class="mb-2">
        <label class="field-label" for="add-person-name">Full Name</label>
        <input type="text" id="add-person-name" class="form-control" placeholder="e.g. Alex Rivera" required />
      </div>
      <div class="mb-2">
        <label class="field-label" for="add-person-email">Work Email</label>
        <input type="email" id="add-person-email" class="form-control" placeholder="employee@payhive.internal" required />
      </div>
      <div class="row mb-2">
        <div class="col-6">
          <label class="field-label" for="add-person-team">Team</label>
          <input type="text" id="add-person-team" class="form-control" placeholder="Engineering" value="Engineering" />
        </div>
        <div class="col-6">
          <label class="field-label" for="add-person-role">Job Role</label>
          <input type="text" id="add-person-role" class="form-control" placeholder="Software Engineer" value="Software Engineer" />
        </div>
      </div>
      <div class="row mb-3">
        <div class="col-6">
          <label class="field-label" for="add-person-status">Employment Status</label>
          <select id="add-person-status" class="form-control select-control">
            <option value="active" selected>Active</option>
            <option value="contractor">Contractor</option>
            <option value="former">Former Employee</option>
          </select>
        </div>
        <div class="col-6">
          <label class="field-label" for="add-person-project">Current Project</label>
          <input type="text" id="add-person-project" class="form-control" placeholder="Optional project name" />
        </div>
      </div>
      <div class="mb-3">
        <label class="field-label" for="add-person-note">Decision Note (Required)</label>
        <textarea id="add-person-note" class="form-control" rows="2" placeholder="Reason for adding identity to organization directory..."></textarea>
      </div>

      <div class="review-modal-actions mt-3">
        <button class="btn btn-outline" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-primary" id="btn-submit-add-person">Add Person</button>
      </div>
    `;

    bootstrap.Modal.getOrCreateInstance(modal).show();

    document.getElementById("btn-submit-add-person").onclick = async () => {
      const name = document.getElementById("add-person-name").value.trim();
      const email = document.getElementById("add-person-email").value.trim();
      const team = document.getElementById("add-person-team").value.trim() || "Engineering";
      const role = document.getElementById("add-person-role").value.trim() || "Team member";
      const status = document.getElementById("add-person-status").value;
      const project = document.getElementById("add-person-project").value.trim() || null;
      const note = document.getElementById("add-person-note").value.trim();

      if (!name || !email || !note) {
        if (typeof window.showToast === "function") window.showToast("Name, email, and decision note are required.");
        return;
      }

      try {
        await window.ApiClient.createIdentity({
          name,
          email,
          team,
          job_role: role,
          employment_status: status,
          current_project: project,
          note,
        });
        bootstrap.Modal.getInstance(modal)?.hide();
        if (typeof window.showToast === "function") window.showToast(`Person ${name} created.`);
        await this.fetchPeople();
        if (typeof render === "function") render();
      } catch (err) {
        if (typeof window.showToast === "function") window.showToast("Could not create person: " + err.message);
      }
    };
  },

  openEditPersonModal(email) {
    const p = (this.people || []).find(x => x.email.toLowerCase() === email.toLowerCase());
    if (!p) return;

    const modal = document.querySelector("#review-modal");
    if (!modal) return;
    modal.classList.remove("is-audit-report");

    document.querySelector("#review-modal-body").innerHTML = `
      <div class="d-flex justify-content-between mb-3">
        <span class="eyebrow mb-0">EDIT IDENTITY</span>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <h2>Edit Person Details</h2>
      <p>Updating identity properties automatically recalculates assignment risk findings.</p>

      <div class="mb-2">
        <label class="field-label" for="edit-person-name">Full Name</label>
        <input type="text" id="edit-person-name" class="form-control" value="${safe(p.name)}" required />
      </div>
      <div class="row mb-2">
        <div class="col-6">
          <label class="field-label" for="edit-person-team">Team</label>
          <input type="text" id="edit-person-team" class="form-control" value="${safe(p.team || '')}" />
        </div>
        <div class="col-6">
          <label class="field-label" for="edit-person-role">Job Role</label>
          <input type="text" id="edit-person-role" class="form-control" value="${safe(p.job_role || '')}" />
        </div>
      </div>
      <div class="row mb-3">
        <div class="col-6">
          <label class="field-label" for="edit-person-status">Employment Status</label>
          <select id="edit-person-status" class="form-control select-control">
            <option value="active" ${p.employment_status === 'active' ? 'selected' : ''}>Active</option>
            <option value="contractor" ${p.employment_status === 'contractor' ? 'selected' : ''}>Contractor</option>
            <option value="former" ${p.employment_status === 'former' ? 'selected' : ''}>Former Employee</option>
          </select>
        </div>
        <div class="col-6">
          <label class="field-label" for="edit-person-project">Current Project</label>
          <input type="text" id="edit-person-project" class="form-control" value="${safe(p.current_project || '')}" />
        </div>
      </div>
      <div class="mb-3">
        <label class="field-label" for="edit-person-note">Decision Note (Required)</label>
        <textarea id="edit-person-note" class="form-control" rows="2" placeholder="Reason for updating employee identity details..."></textarea>
      </div>

      <div class="review-modal-actions mt-3">
        <button class="btn btn-outline" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-primary" id="btn-submit-edit-person">Save Changes</button>
      </div>
    `;

    bootstrap.Modal.getOrCreateInstance(modal).show();

    document.getElementById("btn-submit-edit-person").onclick = async () => {
      const name = document.getElementById("edit-person-name").value.trim();
      const team = document.getElementById("edit-person-team").value.trim();
      const role = document.getElementById("edit-person-role").value.trim();
      const status = document.getElementById("edit-person-status").value;
      const project = document.getElementById("edit-person-project").value.trim();
      const note = document.getElementById("edit-person-note").value.trim();

      if (!name || !note) {
        if (typeof window.showToast === "function") window.showToast("Name and decision note are required.");
        return;
      }

      try {
        await window.ApiClient.updateIdentity(email, {
          name,
          team,
          job_role: role,
          employment_status: status,
          current_project: project || null,
          note,
        });
        bootstrap.Modal.getInstance(modal)?.hide();
        if (typeof window.showToast === "function") window.showToast(`Updated identity ${name}.`);
        await this.fetchPeople();
        await window.ApiClient.loadAndRender();
      } catch (err) {
        if (typeof window.showToast === "function") window.showToast("Could not update person: " + err.message);
      }
    };
  },

  attachEvents(container) {
    // Tab switching
    container.querySelectorAll("#users-tab-bar button").forEach(btn => {
      btn.addEventListener("click", async () => {
        this.activeTab = btn.dataset.tab;
        if (this.activeTab === "people") {
          await this.fetchPeople();
        } else {
          await this.fetchUsers();
        }
        if (typeof render === "function") render();
      });
    });

    // People tab events
    const peopleSearchInput = container.querySelector("#people-search");
    if (peopleSearchInput) {
      let timeout;
      peopleSearchInput.addEventListener("input", (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
          this.peopleSearch = e.target.value;
          if (typeof render === "function") render();
        }, 200);
      });
    }

    container.querySelectorAll("[data-people-filter]").forEach(btn => {
      btn.addEventListener("click", () => {
        this.peopleFilter = btn.dataset.peopleFilter;
        if (typeof render === "function") render();
      });
    });

    container.querySelector("#btn-add-person")?.addEventListener("click", () => {
      this.openAddPersonModal();
    });

    container.querySelector("#btn-people-import-csv")?.addEventListener("click", () => {
      if (window.GitHubSettings?.openCsvImportModal) {
        window.GitHubSettings.openCsvImportModal();
      }
    });

    container.querySelectorAll(".btn-edit-person").forEach(btn => {
      btn.addEventListener("click", () => {
        this.openEditPersonModal(btn.dataset.email);
      });
    });

    container.querySelectorAll(".btn-offboard-person").forEach(btn => {
      btn.addEventListener("click", async () => {
        const email = btn.dataset.email;
        const name = btn.dataset.name || email;
        const confirmed = window.confirm(
          `Are you sure you want to offboard ${name}?\n\n` +
          `This action will:\n` +
          `• Mark employment status as Former\n` +
          `• Instantly remove all collaborator permissions across all payhive-eng repositories on live GitHub\n` +
          `• Auto-decline any pending access requests\n` +
          `• Generate an official Offboarding Certificate & compliance audit trail\n` +
          `• Dispatch notification emails & security webhooks`
        );
        if (!confirmed) return;

        btn.disabled = true;
        btn.textContent = "Offboarding…";
        try {
          const res = await ApiClient.offboardEmployee(email, `Admin executed one-click employee offboarding for ${name}`);
          if (typeof showToast === "function") {
            showToast(`Employee ${name} offboarded. ${res.revokedCount} repository permissions revoked.`);
          }
          await this.fetchPeople();
          const bData = await ApiClient.bootstrap();
          ApiClient.syncState(bData);
          if (typeof render === "function") render();
        } catch (err) {
          if (typeof showToast === "function") {
            showToast(err.message || "Could not offboard employee.");
          }
          btn.disabled = false;
          btn.textContent = "${uiIcon('userX', 13)} Offboard";
        }
      });
    });

    // Users tab events
    container.querySelectorAll("[data-user-filter]").forEach(btn => {
      btn.addEventListener("click", async () => {
        this.statusFilter = btn.dataset.userFilter;
        await this.fetchUsers();
        if (typeof render === "function") render();
      });
    });

    const searchInput = container.querySelector("#users-search");
    if (searchInput) {
      let timeout;
      searchInput.addEventListener("input", (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(async () => {
          this.searchQuery = e.target.value;
          await this.fetchUsers();
          if (typeof render === "function") render();
        }, 300);
      });
    }

    // Activate button
    container.querySelectorAll("[data-user-activate]").forEach(btn => {
      btn.addEventListener("click", () => {
        const uid = btn.dataset.userActivate;
        const target = this.users.find(u => u.uid === uid);
        const name = target ? (target.name || target.email) : uid;
        openDecision(
          "Activate administrator access?",
          `Grant full workspace administrator privileges to ${name} in organization payhive-eng`,
          `${name} · admin access`,
          "Activate account",
          async (note) => {
            try {
              await ApiClient.activateUser(uid, note);
              decisionFeedback(`Account ${name} activated.`);
              await this.fetchUsers();
              if (typeof render === "function") render();
            } catch (err) {
              console.error("Activation failed:", err);
            }
          },
          true
        );
      });
    });

    // Deactivate button
    container.querySelectorAll("[data-user-deactivate]").forEach(btn => {
      btn.addEventListener("click", () => {
        const uid = btn.dataset.userDeactivate;
        const target = this.users.find(u => u.uid === uid);
        const name = target ? (target.name || target.email) : uid;
        openDecision(
          "Deactivate administrator account?",
          `Revoke workspace access for ${name} and invalidate active authentication sessions.`,
          `${name} · status: disabled`,
          "Deactivate account",
          async (note) => {
            try {
              await ApiClient.deactivateUser(uid, note);
              decisionFeedback(`Account ${name} deactivated.`);
              await this.fetchUsers();
              if (typeof render === "function") render();
            } catch (err) {
              console.error("Deactivation failed:", err);
            }
          },
          true
        );
      });
    });

    // Reject button
    container.querySelectorAll("[data-user-reject]").forEach(btn => {
      btn.addEventListener("click", () => {
        const uid = btn.dataset.userReject;
        const target = this.users.find(u => u.uid === uid);
        const name = target ? (target.name || target.email) : uid;
        openDecision(
          "Reject pending signup?",
          `Reject the pending account request for ${name}. No workspace access will be granted.`,
          `${name} · status: rejected`,
          "Reject request",
          async (note) => {
            try {
              await ApiClient.rejectUser(uid, note);
              decisionFeedback(`Account request for ${name} rejected.`);
              await this.fetchUsers();
              if (typeof render === "function") render();
            } catch (err) {
              console.error("Rejection failed:", err);
            }
          },
          true
        );
      });
    });
  }
};

window.UsersPage = UsersPage;
