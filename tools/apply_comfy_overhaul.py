"""
AccessReaper v2 — Linear / Stripe Comfy UI Overhaul Script
Applies clean, comfortable, low-cognitive-load UI to:
- frontend/workspace-design.js (Compact Posture Bar)
- frontend/app.js (Unified Toolbar + Linear Segments + Filter Drawer)
- frontend/phase2.css (Comfy Theme & Spacing)
"""

import sys
import re

def update_workspace_design():
    path = r"D:\AccessReaper-v2\frontend\workspace-design.js"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Locate auditOverview method
    idx_start = content.find("auditOverview(){")
    idx_end = content.find("dashboard(){")
    if idx_start == -1 or idx_end == -1:
        print("ERROR: Could not find auditOverview boundaries in workspace-design.js")
        return False

    new_audit_overview = """auditOverview(){
    const s=Governance.stats(),report=auditRuns.at(-1);
    const unmapped = window.unmatchedGitHubAccounts || (window.GitHubSettings && window.GitHubSettings.unmatched) || [];

    const unmappedAuditBanner = unmapped.length > 0 ? `
      <div class="comfy-notice mb-3" style="border-left: 3px solid #f59e0b; background: rgba(245, 158, 11, 0.08); padding: 8px 14px; border-radius: 8px; display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px;">
        <span style="font-size: 13px; display:inline-flex; align-items:center; gap:8px;">
          ${uiIcon('shieldAlert', 15)} <span><strong>${unmapped.length} account(s) have hidden emails</strong> (${unmapped.map(u => '@' + u.login).join(', ')}). Revocation notices need linked emails.</span>
        </span>
        <a href="#settings" class="btn btn-sm btn-outline" style="font-size: 12px; padding: 2px 10px; text-decoration: none;">Link in Settings</a>
      </div>
    ` : '';

    return `${unmappedAuditBanner}
      <section class="card comfy-posture-bar">
        <div class="comfy-posture-left">
          <div class="posture-org-pill">
            ${uiIcon('repo', 14)} <strong>payhive-eng</strong>
            <span class="posture-sub">&bull; ${s.assignments} assignments</span>
          </div>
          <div class="posture-chips">
            <button type="button" class="posture-chip chip-high ${state.auditSegment==='high_risk'?'active':''}" data-audit-segment="high_risk" title="Filter High-Risk findings">
              <span class="chip-dot"></span>
              <strong>${s.high}</strong> High Risk
            </button>
            <button type="button" class="posture-chip chip-medium ${state.auditRisk==='Medium'?'active':''}" id="chip-filter-medium" title="Filter Medium Risk">
              <span class="chip-dot"></span>
              <strong>${s.medium ?? people.filter(p=>p.risk==='Medium'&&!p.resolved).length}</strong> Medium
            </button>
            <button type="button" class="posture-chip chip-healthy" title="Healthy assignments">
              <span class="chip-dot"></span>
              <strong>${people.filter(p=>p.risk==='Low'&&!p.resolved).length}</strong> Healthy
            </button>
            <button type="button" class="posture-chip chip-remediated ${state.auditSegment==='remediated'?'active':''}" data-audit-segment="remediated" title="Filter Remediated assignments">
              <span class="chip-dot"></span>
              <strong>${people.filter(p=>p.resolved).length}</strong> Reviewed
            </button>
          </div>
        </div>
        <div class="comfy-posture-right">
          <span class="comfy-audit-timestamp" title="${safe(report?.id||(window.automationStatus?.nextRunAt ? ('The first automatic audit runs ' + new Date(window.automationStatus.nextRunAt).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})) : 'Scheduled at 02:00 PKT'))}">
            ${uiIcon('checkCircle', 13)} ${report ? `Audit: ${Governance.date(report.completedAt)}` : 'Audit: Ready'}
          </span>
          ${report ? `<button type="button" class="btn btn-sm btn-outline comfy-report-btn" data-audit-report="${report.id}" aria-label="View Full Report">${uiIcon('fileText', 13)} Full Report &rarr;</button>` : ''}
        </div>
      </section>
      ${report ? `<details class="comfy-summary-disclosure"><summary><span>${AuditSummary.disclosureHeader(report)}</span><span class="disclosure-hint">Expand analysis</span></summary><div class="comfy-summary-content">${AuditSummary.preview(report)}</div></details>` : ''}`;
  },

  """

    new_content = content[:idx_start] + new_audit_overview + content[idx_end:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("SUCCESS: Updated workspace-design.js")
    return True


def update_app_js():
    path = r"D:\AccessReaper-v2\frontend\app.js"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Ensure state has showFilters
    if "showFilters:" not in content:
        content = content.replace("const state={", "const state={showFilters:false,")

    # 2. Locate auditPage boundaries
    idx1 = content.find("function auditPage(){")
    idx2 = content.find("function dashboard(){")
    if idx1 == -1 or idx2 == -1:
        print("ERROR: Could not find auditPage boundaries in app.js")
        return False

    new_audit_page = """function auditPage(){
  const countAll = people.length;
  const countHigh = people.filter(p => p.risk === 'High' && !p.resolved).length;
  const countJit = people.filter(p => p.isTemporary && p.access !== 'None').length;
  const countExpiring = people.filter(p => {
    const empStatus = p.employmentStatus || p.employment_status || '';
    const isExpiringLease = p.isTemporary && p.expiresAt && (new Date(p.expiresAt).getTime() - Date.now() < 86400000 * 3);
    const isContractor = p.team === 'External' || (p.role && p.role.toLowerCase().includes('contractor')) || (p.job_role && p.job_role.toLowerCase().includes('contractor')) || empStatus === 'contractor' || (p.reason && p.reason.toLowerCase().includes('contractor'));
    return isExpiringLease || isContractor;
  }).length;
  const countInactive = people.filter(p => (p.reason && (p.reason.toLowerCase().includes('inactive') || p.reason.toLowerCase().includes('dormant'))) || (p.last && p.last.toLowerCase().includes('not recorded')) || (p.lastActiveAt && (Date.now() - new Date(p.lastActiveAt).getTime() > 86400000 * 30))).length;
  const countRemediated = people.filter(p => p.resolved).length;

  const filtered = filteredPeople();
  state.auditPage = Math.min(state.auditPage, Math.max(1, Math.ceil(filtered.length / 6)));
  const rows = filtered.slice((state.auditPage - 1) * 6, state.auditPage * 6);
  const filtersActive = state.auditSegment !== 'all' || state.auditQuery || state.auditRisk !== 'All risks' || state.auditAccess !== 'All access levels' || state.auditSource !== 'All sources' || state.auditUser !== 'All users' || state.auditRepo !== 'All resources' || state.auditAction !== 'All actions';
  const activeFilterCount = [
    state.auditRisk !== 'All risks',
    state.auditAccess !== 'All access levels',
    state.auditSource !== 'All sources',
    state.auditUser !== 'All users',
    state.auditRepo !== 'All resources',
    state.auditAction !== 'All actions'
  ].filter(Boolean).length;

  let segmentBanner = '';
  if (state.auditSegment === 'high_risk') {
    segmentBanner = `
      <div class="comfy-segment-strip strip-high-risk">
        <div class="segment-strip-content">
          <span class="segment-strip-icon">${uiIcon('shieldAlert', 14)}</span>
          <span class="segment-strip-text">
            <strong>High-Risk Exposure (${countHigh})</strong>: Users with unreviewed administrative rights, direct bypasses, or missing company mapping.
          </span>
        </div>
        <button type="button" class="comfy-strip-close" data-audit-segment="all">Show All (${countAll}) &times;</button>
      </div>`;
  } else if (state.auditSegment === 'jit') {
    segmentBanner = `
      <div class="comfy-segment-strip strip-jit">
        <div class="segment-strip-content">
          <span class="segment-strip-icon">${uiIcon('clock', 14)}</span>
          <span class="segment-strip-text">
            <strong>Just-In-Time (JIT) Leases (${countJit})</strong>: Users granted time-bound temporary repository privileges with automated expiry timers.
          </span>
        </div>
        <button type="button" class="comfy-strip-close" data-audit-segment="all">Show All (${countAll}) &times;</button>
      </div>`;
  } else if (state.auditSegment === 'expiring') {
    segmentBanner = `
      <div class="comfy-segment-strip strip-expiring">
        <div class="segment-strip-content">
          <span class="segment-strip-icon">${uiIcon('hourglass', 14)}</span>
          <span class="segment-strip-text">
            <strong>Expiring Access & Contractors (${countExpiring})</strong>: Contractors, external staff, and temporary assignments concluding shortly.
          </span>
        </div>
        <button type="button" class="comfy-strip-close" data-audit-segment="all">Show All (${countAll}) &times;</button>
      </div>`;
  } else if (state.auditSegment === 'inactive') {
    segmentBanner = `
      <div class="comfy-segment-strip strip-inactive">
        <div class="segment-strip-content">
          <span class="segment-strip-icon">${uiIcon('userMinus', 14)}</span>
          <span class="segment-strip-text">
            <strong>Dormant Accounts (${countInactive})</strong>: Assignments with no recorded activity in 30+ days. Recommended for least-privilege revocation.
          </span>
        </div>
        <button type="button" class="comfy-strip-close" data-audit-segment="all">Show All (${countAll}) &times;</button>
      </div>`;
  } else if (state.auditSegment === 'remediated') {
    segmentBanner = `
      <div class="comfy-segment-strip strip-remediated">
        <div class="segment-strip-content">
          <span class="segment-strip-icon">${uiIcon('checkCircle', 14)}</span>
          <span class="segment-strip-text">
            <strong>Remediated & Reviewed Access (${countRemediated})</strong>: Permissions reviewed, reduced, or approved with documented compliance justification.
          </span>
        </div>
        <button type="button" class="comfy-strip-close" data-audit-segment="all">Show All (${countAll}) &times;</button>
      </div>`;
  }

  return `<div class="audit-workbench">${pageHeading('Access audit','Inspect permissions. Review risk. Keep access appropriate.',`<button class="btn btn-outline" data-export="audit">Export CSV</button>${window.AutomationTimer ? window.AutomationTimer.renderChip() : ''}`)}${WorkspaceDesign.auditOverview()}

    <section class="card audit-register comfy-register">
      <div class="comfy-toolbar">
        <div class="comfy-segmented-nav" role="tablist" aria-label="Triage Segments">
          <button type="button" class="comfy-nav-tab ${state.auditSegment==='all'?'active':''}" data-audit-segment="all">
            ${uiIcon('layers', 13)} <span>All</span> <span class="tab-pill">${countAll}</span>
          </button>
          <button type="button" class="comfy-nav-tab tab-danger ${state.auditSegment==='high_risk'?'active':''}" data-audit-segment="high_risk">
            ${uiIcon('shieldAlert', 13)} <span>High Risk</span> <span class="tab-pill pill-danger">${countHigh}</span>
          </button>
          <button type="button" class="comfy-nav-tab tab-blue ${state.auditSegment==='jit'?'active':''}" data-audit-segment="jit">
            ${uiIcon('clock', 13)} <span>JIT Leases</span> <span class="tab-pill pill-blue">${countJit}</span>
          </button>
          <button type="button" class="comfy-nav-tab tab-amber ${state.auditSegment==='expiring'?'active':''}" data-audit-segment="expiring">
            ${uiIcon('hourglass', 13)} <span>Expiring</span> <span class="tab-pill pill-amber">${countExpiring}</span>
          </button>
          <button type="button" class="comfy-nav-tab tab-slate ${state.auditSegment==='inactive'?'active':''}" data-audit-segment="inactive">
            ${uiIcon('userMinus', 13)} <span>Dormant</span> <span class="tab-pill pill-slate">${countInactive}</span>
          </button>
          <button type="button" class="comfy-nav-tab tab-emerald ${state.auditSegment==='remediated'?'active':''}" data-audit-segment="remediated">
            ${uiIcon('checkCircle', 13)} <span>Reviewed</span> <span class="tab-pill pill-emerald">${countRemediated}</span>
          </button>
        </div>

        <div class="comfy-toolbar-tools">
          <div class="comfy-search-box">
            ${auditSearch('audit-search',state.auditQuery,'Search people or resources…')}
          </div>
          <button type="button" class="btn btn-sm btn-outline comfy-filter-btn ${activeFilterCount > 0 ? 'has-active' : ''}" id="toggle-advanced-filters" aria-expanded="${Boolean(state.showFilters || activeFilterCount > 0)}">
            ${uiIcon('filter', 13)} <span>Filters</span>
            ${activeFilterCount > 0 ? `<span class="filter-count-badge">${activeFilterCount}</span>` : ''}
          </button>
          ${filtersActive ? '<button type="button" class="btn btn-sm btn-outline comfy-clear-btn" id="clear-filters" title="Reset all filters">Clear</button>' : ''}
        </div>
      </div>

      ${segmentBanner}

      <div class="comfy-filters-drawer ${Boolean(state.showFilters || activeFilterCount > 0) ? 'is-open' : ''}" id="advanced-filters-drawer" style="${Boolean(state.showFilters || activeFilterCount > 0) ? '' : 'display:none;'}">
        <div class="filter-select-line">
          <div><label for="risk-filter">Risk</label>${selectControl('risk-filter','Risk level',['All risks','High','Medium','Low'],state.auditRisk)}</div>
          <div><label for="access-filter">Access level</label>${selectControl('access-filter','Access level',['All access levels','Admin','Write','Read','Editor','Viewer','None'],state.auditAccess)}</div>
          <div><label for="source-filter">Source</label>${selectControl('source-filter','Access source',['All sources','GitHub','Firestore'],state.auditSource)}</div>
          <div><label for="user-filter">User</label>${selectControl('user-filter','User',['All users',...new Set(people.map(p=>p.email))],state.auditUser)}</div>
          <div><label for="repo-filter">Resource</label>${selectControl('repo-filter','Resource',['All resources',...new Set(people.map(p=>p.repo))],state.auditRepo)}</div>
          <div><label for="action-filter">Recommended action</label>${selectControl('action-filter','Recommended action',['All actions','Reduce access','Revoke access','Keep access','Reviewed'],state.auditAction)}</div>
        </div>
      </div>

      <section class="table-panel audit-table comfy-table-wrap">
        <div class="comfy-table-header-meta">
          <span class="showing-count">Showing <strong>${filtered.length}</strong> of <strong>${people.length}</strong> access assignments</span>
        </div>
        ${filtered.length ? renderActivityTable(rows.length,rows,true) : '<div class="empty-state"><strong>No assignments match</strong>Try another search or reset your filters.</div>'}
        <div class="page-pagination">${pagination('audit',state.auditPage,filtered.length)}</div>
      </section>
    </section>
  </div>`;
}

"""

    content = content[:idx1] + new_audit_page + content[idx2:]

    # 3. Add click handlers for toggle-advanced-filters and chip-filter-medium
    needle = "if(b.id==='clear-filters')"
    if needle in content and "toggle-advanced-filters" not in content:
        insert_code = """if(b.id==='toggle-advanced-filters'){state.showFilters=!state.showFilters;render();}
  if(b.id==='chip-filter-medium'){state.auditRisk=state.auditRisk==='Medium'?'All risks':'Medium';state.auditSegment='all';state.auditPage=1;render();}
  """
        content = content.replace(needle, insert_code + needle)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: Updated app.js")
    return True


def append_comfy_css():
    path = r"D:\AccessReaper-v2\frontend\phase2.css"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if "/* --- Comfy Linear/Stripe Styles --- */" in content:
        print("INFO: phase2.css already contains comfy styles. Overwriting comfy section...")
        content = content[:content.find("/* --- Comfy Linear/Stripe Styles --- */")]

    comfy_css = """
/* --- Comfy Linear/Stripe Styles --- */
/* Designed for minimal cognitive load, soft dark mode, and high information clarity */

/* 1. Posture Strip Bar */
.comfy-posture-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 16px;
  margin-bottom: 14px;
  border-radius: 10px;
  background: var(--surface, #141a29);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
}

.comfy-posture-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.posture-org-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text, #f1f5f9);
}

.posture-sub {
  color: var(--muted, #94a3b8);
  font-size: 12px;
  font-weight: normal;
}

.posture-chips {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.posture-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 14px;
  font-size: 11.5px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}

.posture-chip .chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.posture-chip.chip-high {
  background: rgba(239, 68, 68, 0.08);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.18);
}
.posture-chip.chip-high .chip-dot { background: #ef4444; }
.posture-chip.chip-high.active, .posture-chip.chip-high:hover {
  background: rgba(239, 68, 68, 0.18);
  border-color: #ef4444;
}

.posture-chip.chip-medium {
  background: rgba(245, 158, 11, 0.08);
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.18);
}
.posture-chip.chip-medium .chip-dot { background: #f59e0b; }
.posture-chip.chip-medium.active, .posture-chip.chip-medium:hover {
  background: rgba(245, 158, 11, 0.18);
  border-color: #f59e0b;
}

.posture-chip.chip-healthy {
  background: rgba(148, 163, 184, 0.08);
  color: #94a3b8;
  border-color: rgba(148, 163, 184, 0.18);
}
.posture-chip.chip-healthy .chip-dot { background: #64748b; }

.posture-chip.chip-remediated {
  background: rgba(16, 185, 129, 0.08);
  color: #34d399;
  border-color: rgba(16, 185, 129, 0.18);
}
.posture-chip.chip-remediated .chip-dot { background: #10b981; }
.posture-chip.chip-remediated.active, .posture-chip.chip-remediated:hover {
  background: rgba(16, 185, 129, 0.18);
  border-color: #10b981;
}

.comfy-posture-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.comfy-audit-timestamp {
  font-size: 11.5px;
  color: var(--muted, #94a3b8);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.comfy-report-btn {
  font-size: 11.5px !important;
  padding: 3px 10px !important;
  border-radius: 6px !important;
  font-weight: 500 !important;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

/* 2. Executive Summary Disclosure */
.comfy-summary-disclosure {
  margin-bottom: 14px;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  background: var(--surface, #141a29);
  overflow: hidden;
}

.comfy-summary-disclosure summary {
  padding: 8px 14px;
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 500;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text, #f1f5f9);
}

.comfy-summary-disclosure summary::-webkit-details-marker {
  display: none;
}

.comfy-summary-content {
  padding: 12px 16px;
  border-top: 1px solid var(--border, rgba(255, 255, 255, 0.06));
}

/* 3. Register Card & Toolbar */
.comfy-register {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
}

.comfy-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 14px;
  background: var(--surface-soft, rgba(0, 0, 0, 0.12));
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.06));
}

.comfy-segmented-nav {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: rgba(0, 0, 0, 0.2);
  padding: 3px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

[data-theme='light'] .comfy-segmented-nav {
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.comfy-nav-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--muted, #94a3b8);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.comfy-nav-tab:hover {
  color: var(--text, #f1f5f9);
  background: rgba(255, 255, 255, 0.04);
}

.comfy-nav-tab.active {
  background: var(--surface, #1e2636);
  color: var(--text, #ffffff);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}

[data-theme='light'] .comfy-nav-tab.active {
  background: #ffffff;
  color: #0f172a;
}

.tab-pill {
  padding: 1px 5px;
  border-radius: 10px;
  font-size: 10.5px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.08);
  color: var(--muted, #94a3b8);
}

.comfy-nav-tab.active .pill-danger { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.comfy-nav-tab.active .pill-blue { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.comfy-nav-tab.active .pill-amber { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
.comfy-nav-tab.active .pill-slate { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }
.comfy-nav-tab.active .pill-emerald { background: rgba(16, 185, 129, 0.2); color: #34d399; }

.comfy-toolbar-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.comfy-search-box .search-field {
  margin: 0;
}

.comfy-search-box input {
  height: 31px;
  font-size: 12px;
  padding: 4px 10px 4px 28px;
  border-radius: 6px;
  width: 190px;
}

.comfy-filter-btn {
  font-size: 12px !important;
  padding: 4px 9px !important;
  border-radius: 6px !important;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.comfy-filter-btn.has-active {
  border-color: var(--orange, #ff4d1f) !important;
  color: var(--orange, #ff4d1f) !important;
}

.filter-count-badge {
  background: var(--orange, #ff4d1f);
  color: #fff;
  border-radius: 10px;
  padding: 0 5px;
  font-size: 10px;
  font-weight: 700;
}

.comfy-clear-btn {
  font-size: 11.5px !important;
  padding: 3px 8px !important;
  color: var(--muted, #94a3b8) !important;
}

/* 4. Segment Context Strip */
.comfy-segment-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 14px;
  font-size: 12.5px;
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.06));
}

.comfy-segment-strip.strip-high-risk {
  background: rgba(239, 68, 68, 0.05);
  color: #f87171;
  border-left: 3px solid #ef4444;
}

.comfy-segment-strip.strip-jit {
  background: rgba(59, 130, 246, 0.05);
  color: #60a5fa;
  border-left: 3px solid #3b82f6;
}

.comfy-segment-strip.strip-expiring {
  background: rgba(245, 158, 11, 0.05);
  color: #fbbf24;
  border-left: 3px solid #f59e0b;
}

.comfy-segment-strip.strip-inactive {
  background: rgba(148, 163, 184, 0.05);
  color: #94a3b8;
  border-left: 3px solid #64748b;
}

.comfy-segment-strip.strip-remediated {
  background: rgba(16, 185, 129, 0.05);
  color: #34d399;
  border-left: 3px solid #10b981;
}

.segment-strip-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.comfy-strip-close {
  background: transparent;
  border: 1px solid currentColor;
  color: inherit;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}

/* 5. Filters Drawer */
.comfy-filters-drawer {
  padding: 12px 14px;
  background: var(--surface, #141a29);
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.06));
}

.comfy-filters-drawer .filter-select-line {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.comfy-filters-drawer .filter-select-line label {
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: var(--muted, #94a3b8);
  margin-bottom: 3px;
  display: block;
}

.comfy-filters-drawer select {
  font-size: 12px;
  height: 31px;
  padding: 3px 8px;
  border-radius: 5px;
}

/* 6. Comfy Table Styling */
.comfy-table-wrap {
  padding: 0;
}

.comfy-table-header-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px 4px;
  font-size: 11.5px;
  color: var(--muted, #94a3b8);
}

.comfy-table-wrap .table {
  margin: 0;
}

.comfy-table-wrap .table tbody tr {
  height: 48px;
  transition: background 0.1s ease;
}

.comfy-table-wrap .table tbody tr:hover {
  background: rgba(255, 255, 255, 0.025);
}

[data-theme='light'] .comfy-table-wrap .table tbody tr:hover {
  background: rgba(0, 0, 0, 0.02);
}

.comfy-table-wrap .table th {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 10px 14px;
}

.comfy-table-wrap .table td {
  padding: 10px 14px;
  vertical-align: middle;
  font-size: 12.5px;
}
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content + comfy_css)
    print("SUCCESS: Appended comfy styles to phase2.css")
    return True


if __name__ == "__main__":
    ok1 = update_workspace_design()
    ok2 = update_app_js()
    ok3 = append_comfy_css()
    if ok1 and ok2 and ok3:
        print("ALL COMFY UPDATES APPLIED SUCCESSFULLY.")
    else:
        print("FAILURES OCCURRED DURING APPLICATION.")
        sys.exit(1)
