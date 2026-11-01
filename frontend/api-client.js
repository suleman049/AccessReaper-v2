// AccessReaper v2 API Client
// Connects frontend to backend /api endpoints with Firebase ID token authentication.

const ApiClient = {
  isDemoMode: false,
  loaded: false,

  async getToken() {
    if (window.FirebaseIdentity?.user) {
      try {
        return await window.FirebaseIdentity.user.getIdToken();
      } catch (err) {
        console.warn("Could not retrieve Firebase token:", err);
      }
    }
    return null;
  },

  async request(path, options = {}) {
    const headers = {
      ...(options.headers || {}),
    };

    const token = await this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    } else if (!headers["Authorization"]) {
      headers["Authorization"] = "Bearer dev-token";
      headers["X-Dev-User"] = "admin@payhive-eng.internal";
    }

    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }

    let res;
    try {
      res = await fetch(path, { ...options, headers });
    } catch (netErr) {
      if (typeof window.showToast === "function") {
        window.showToast("Could not connect to AccessReaper server.");
      }
      throw netErr;
    }

    if (!res.ok) {
      let errorData;
      try {
        errorData = await res.json();
      } catch {
        errorData = { error: { code: "HTTP_ERROR", message: `Request failed: ${res.statusText}` } };
      }
      const message = errorData?.error?.message || `Error ${res.status}`;
      if (typeof window.showToast === "function") {
        window.showToast(message);
      }
      const err = new Error(message);
      err.status = res.status;
      err.data = errorData;
      throw err;
    }

    return await res.json();
  },

  async bootstrap() {
    return await this.request("/api/bootstrap");
  },

  async remediate(id, note, targetAccess = null) {
    const body = { note };
    if (targetAccess !== null) {
      body.target_access = targetAccess;
    }
    return await this.request(`/api/assignments/${encodeURIComponent(id)}/remediate`, {
      method: "POST",
      body,
    });
  },

  async dismiss(id, note) {
    return await this.request(`/api/assignments/${encodeURIComponent(id)}/dismiss`, {
      method: "POST",
      body: { note },
    });
  },

  async decideApproval(id, action, note) {
    return await this.request(`/api/approvals/${encodeURIComponent(id)}/decision`, {
      method: "POST",
      body: { action, note },
    });
  },

  async createAccessRequest(data) {
    return await this.request("/api/approvals", {
      method: "POST",
      body: data,
    });
  },

  async createPublicRequest(data) {
    return await this.request("/api/requests/public", {
      method: "POST",
      body: data,
    });
  },

  async getPublicRepos() {
    return await this.request("/api/requests/public/repositories");
  },

  async runAudit() {
    return await this.request("/api/audits/run", {
      method: "POST",
    });
  },

  async resetSample() {
    return await this.request("/api/admin/reset-sample", {
      method: "POST",
    });
  },

  // --- Phase 2: User Management ---
  async getUsers(status = "all", q = "") {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (q) params.set("q", q);
    return await this.request(`/api/users?${params.toString()}`);
  },

  async activateUser(uid, note) {
    return await this.request(`/api/users/${encodeURIComponent(uid)}/activate`, {
      method: "POST",
      body: { note },
    });
  },

  async deactivateUser(uid, note) {
    return await this.request(`/api/users/${encodeURIComponent(uid)}/deactivate`, {
      method: "POST",
      body: { note },
    });
  },

  async rejectUser(uid, note) {
    return await this.request(`/api/users/${encodeURIComponent(uid)}/reject`, {
      method: "POST",
      body: { note },
    });
  },

  // --- Phase 2: Risk Rules ---
  async getRules() {
    return await this.request("/api/rules");
  },

  async createRuleConfig(config, note) {
    return await this.request("/api/rules", {
      method: "POST",
      body: { config, note },
    });
  },

  async rollbackRuleConfig(version) {
    return await this.request(`/api/rules/${encodeURIComponent(version)}/activate`, {
      method: "POST",
    });
  },

  async previewRules(config) {
    return await this.request("/api/rules/preview", {
      method: "POST",
      body: { config },
    });
  },

  // --- Stage 1: Automation ---
  async getAutomationStatus() {
    return await this.request("/api/automation/status");
  },

  async updateAutomationConfig(config) {
    return await this.request("/api/automation/config", {
      method: "PUT",
      body: config,
    });
  },

  async triggerAutoAudit() {
    return await this.request("/api/automation/trigger", {
      method: "POST",
    });
  },

  async reapJit() {
    return await this.request("/api/automation/reap", {
      method: "POST",
    });
  },

  // --- Auto-Pilot Mode ---
  async getAutoPilot() {
    return await this.request("/api/automation/autopilot");
  },

  async updateAutoPilot(enabled) {
    return await this.request("/api/automation/autopilot", {
      method: "PUT",
      body: { enabled },
    });
  },

  async enforceAutoPilot() {
    return await this.request("/api/automation/autopilot/enforce", {
      method: "POST",
    });
  },

  // --- Phase 2: Scheduled Audits ---
  async getSchedule() {
    return await this.request("/api/schedule");
  },

  async updateSchedule(scheduleData) {
    return await this.request("/api/schedule", {
      method: "PUT",
      body: scheduleData,
    });
  },

  async getNextScheduleRun() {
    return await this.request("/api/schedule/next-run");
  },

  // --- Phase 2: Server-side Reports ---
  async downloadBlob(url, filename) {
    const token = await this.getToken();
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    } else {
      headers["Authorization"] = "Bearer dev-token";
      headers["X-Dev-User"] = "admin@payhive-eng.internal";
    }
    let res;
    try {
      res = await fetch(url, { headers });
    } catch {
      if (typeof window.showToast === "function") window.showToast("Could not download file.");
      return;
    }
    if (!res.ok) {
      let msg = `Download failed (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson?.error?.message) msg = errJson.error.message;
      } catch {}
      if (typeof window.showToast === "function") window.showToast(msg);
      return;
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(blobUrl);
  },

  async downloadPdf(runId) {
    await this.downloadBlob(`/api/audits/${encodeURIComponent(runId)}/report.pdf`, `AccessReaper-v2-audit-${runId}.pdf`);
  },

  async downloadFindingsCsv(runId) {
    await this.downloadBlob(`/api/audits/${encodeURIComponent(runId)}/findings.csv`, `audit-${runId}-findings.csv`);
  },

  async downloadHistoryCsv(params = {}) {
    const qs = new URLSearchParams(params).toString();
    await this.downloadBlob(`/api/history.csv?${qs}`, "accessreaper-audit-history.csv");
  },

  // --- Generic HTTP helpers ---
  async get(path) {
    return await this.request(path, { method: "GET" });
  },

  async post(path, body) {
    return await this.request(path, { method: "POST", body });
  },

  async put(path, body) {
    return await this.request(path, { method: "PUT", body });
  },

  async delete(path) {
    return await this.request(path, { method: "DELETE" });
  },

  // --- Phase 3: GitHub IAM Integration ---
  async getGitHubStatus() {
    return await this.get("/api/integrations/github/status");
  },

  async configureGitHub(org, token, syncBeforeAudit = null) {
    return await this.put("/api/integrations/github/config", {
      org,
      token,
      sync_before_audit: syncBeforeAudit,
    });
  },

  async disconnectGitHub() {
    return await this.delete("/api/integrations/github/config");
  },

  async testGitHub(org = null, token = null) {
    return await this.post("/api/integrations/github/test", { org, token });
  },

  async syncGitHub() {
    return await this.post("/api/integrations/github/sync");
  },

  async getUnmatchedGitHub() {
    return await this.get("/api/integrations/github/unmatched");
  },

  async mapGitHubAccount(login, email) {
    return await this.put(`/api/integrations/github/map/${encodeURIComponent(login)}`, { email });
  },

  async getDataMode() {
    return await this.get("/api/integrations/github/mode");
  },

  async setDataMode(mode) {
    return await this.put("/api/integrations/github/mode", { data_mode: mode });
  },

  async updateIdentityStatus(email, employment_status, note) {
    return await this.put(`/api/identities/${encodeURIComponent(email)}`, {
      employment_status,
      note,
    });
  },

  // --- Stage 2: Triage & Identities ---
  async getIdentities() {
    return await this.get("/api/identities");
  },

  async createIdentity(data) {
    return await this.post("/api/identities", data);
  },

  async updateIdentity(email, data) {
    return await this.put(`/api/identities/${encodeURIComponent(email)}`, data);
  },

  async previewCsvImport(csvText) {
    return await this.post("/api/identities/import-csv/preview", { csvText });
  },

  async confirmCsvImport(rows, note = "CSV bulk identity import") {
    return await this.post("/api/identities/import-csv/confirm", { rows, note });
  },

  async bulkMapGitHub(mappings) {
    return await this.post("/api/integrations/github/bulk-map", { mappings });
  },

  async getGitHubAutoSuggestions() {
    return await this.get("/api/integrations/github/auto-suggest");
  },

  async classifyGitHubAccount(login, accountType, note = "") {
    return await this.put(`/api/integrations/github/accounts/${encodeURIComponent(login)}/classification`, {
      accountType,
      note,
    });
  },

  // --- Stage 3: Separation of Duties ---
  async getSoDConflicts() {
    return await this.get("/api/rules/sod");
  },

  async createSoDConflict(conflict) {
    return await this.post("/api/rules/sod", conflict);
  },

  async updateSoDConflict(id, conflict) {
    return await this.put(`/api/rules/sod/${encodeURIComponent(id)}`, conflict);
  },

  async deleteSoDConflict(id, note = "") {
    return await this.delete(`/api/rules/sod/${encodeURIComponent(id)}?note=${encodeURIComponent(note)}`);
  },

  // --- Stage 4: Notifications & AI Explanations ---
  async getNotifications() {
    return await this.get("/api/notifications");
  },

  async markNotificationRead(id) {
    return await this.post(`/api/notifications/${encodeURIComponent(id)}/read`);
  },

  async markAllNotificationsRead() {
    return await this.post("/api/notifications/read-all");
  },

  async getNotificationPreferences() {
    return await this.get("/api/notifications/preferences");
  },

  async updateNotificationPreferences(data) {
    return await this.put("/api/notifications/preferences", data);
  },

  async sendTestEmail() {
    return await this.post("/api/notifications/test-email");
  },

  async offboardEmployee(idOrEmail, note = "Employee offboarding - complete access revocation") {
    return await this.post(`/api/identities/${encodeURIComponent(idOrEmail)}/offboard`, { note });
  },

  async getWebhookConfig() {
    return await this.get("/api/webhooks/config");
  },

  async saveWebhookConfig(webhookUrl) {
    return await this.post("/api/webhooks/config", { webhook_url: webhookUrl });
  },

  async testWebhook(webhookUrl = null) {
    return await this.post("/api/webhooks/test", { webhook_url: webhookUrl });
  },

  async getLLMStatus() {
    return await this.get("/api/llm/status");
  },

  syncState(data) {
    if (data.people && Array.isArray(data.people)) people = data.people;
    if (data.approvals && Array.isArray(data.approvals)) approvals = data.approvals;
    if (data.history && Array.isArray(data.history)) history = data.history;
    if (data.auditRuns && Array.isArray(data.auditRuns)) auditRuns = data.auditRuns;
    if (data.auditSnapshots && Array.isArray(data.auditSnapshots)) auditSnapshots = data.auditSnapshots;
    if (data.lastAudit) lastAudit = data.lastAudit;
    if (data.dataMode) window.currentDataMode = data.dataMode;
    if (data.llmStatus) window.llmStatus = data.llmStatus;
    if (data.automation) {
      window.automationStatus = data.automation;
      if (window.AutomationTimer) window.AutomationTimer.updateFromStatus(data.automation);
    }
    if (data.unmatchedGitHub) {
      window.unmatchedGitHubAccounts = data.unmatchedGitHub;
      if (window.GitHubSettings) {
        window.GitHubSettings.unmatched = data.unmatchedGitHub;
      }
    }
  },

  async loadAndRender() {
    if (new URLSearchParams(location.search).get("demo") === "1") {
      this.isDemoMode = true;
      if (typeof showToast === "function") showToast("API unavailable — demo mode");
      if (typeof render === "function") render();
      return;
    }
    try {
      const data = await this.bootstrap();
      this.syncState(data);
      this.isDemoMode = false;
      this.loaded = true;
      if (typeof render === "function") render();
    } catch (err) {
      console.warn("Bootstrap failed, falling back to demo mode:", err);
      this.isDemoMode = true;
      if (typeof showToast === "function") showToast("API unavailable — demo mode");
      if (typeof render === "function") render();
    }
  }
};

window.ApiClient = ApiClient;
