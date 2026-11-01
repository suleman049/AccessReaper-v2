import os

# 1. Update frontend/app.js
app_path = r'D:\AccessReaper-v2\frontend\app.js'
with open(app_path, 'r', encoding='utf-8') as f:
    app_code = f.read()

# Add auditSegment to state
if "auditSegment:" not in app_code:
    app_code = app_code.replace(
        "const state={auditRisk:'All risks',",
        "const state={auditSegment:'all',auditRisk:'All risks',"
    )
    print("Added auditSegment to state")

# Add auditSegment reset to clear-filters
if "auditSegment:'all'" not in app_code:
    app_code = app_code.replace(
        "if(b.id==='clear-filters'){Object.assign(state,{",
        "if(b.id==='clear-filters'){Object.assign(state,{auditSegment:'all',"
    )
    print("Added auditSegment to clear-filters")

# Update filteredPeople function to include auditSegment logic
old_filtered = """function filteredPeople(){return people.filter(p=>(state.auditRisk==='All risks'||(!p.resolved&&p.risk===state.auditRisk))&&(state.auditAccess==='All access levels'||p.access===state.auditAccess)&&(state.auditSource==='All sources'||p.source===state.auditSource)&&(state.auditUser==='All users'||p.email===state.auditUser)&&(state.auditRepo==='All resources'||p.repo===state.auditRepo)&&(state.auditAction==='All actions'||Governance.actionLabel(p)===state.auditAction)&&`${p.name} ${p.email} ${p.repo} ${p.team} ${p.reason} ${p.source}`.toLowerCase().includes(state.auditQuery.toLowerCase()));}"""

new_filtered = """function filteredPeople(){
  return people.filter(p=>{
    if(state.auditSegment==='high_risk'&&(p.risk!=='High'||p.resolved))return false;
    if(state.auditSegment==='jit'&&(!p.isTemporary||p.access==='None'))return false;
    if(state.auditSegment==='expiring'){
      const isExpiringLease=p.isTemporary&&p.expiresAt&&(new Date(p.expiresAt).getTime()-Date.now()<86400000*3);
      const isContractor=(p.team==='External'||(p.job_role&&p.job_role.toLowerCase().includes('contractor'))||p.employment_status==='contractor'||(p.reason&&p.reason.toLowerCase().includes('contractor')));
      if(!isExpiringLease&&!isContractor)return false;
    }
    if(state.auditSegment==='inactive'){
      const isInactive=(p.reason&&(p.reason.toLowerCase().includes('inactive')||p.reason.toLowerCase().includes('dormant')))||(p.last&&p.last.toLowerCase().includes('not recorded'))||(p.lastActiveAt&&(Date.now()-new Date(p.lastActiveAt).getTime()>86400000*30));
      if(!isInactive)return false;
    }
    if(state.auditSegment==='remediated'&&!p.resolved)return false;
    return (state.auditRisk==='All risks'||(!p.resolved&&p.risk===state.auditRisk))&&(state.auditAccess==='All access levels'||p.access===state.auditAccess)&&(state.auditSource==='All sources'||p.source===state.auditSource)&&(state.auditUser==='All users'||p.email===state.auditUser)&&(state.auditRepo==='All resources'||p.repo===state.auditRepo)&&(state.auditAction==='All actions'||Governance.actionLabel(p)===state.auditAction)&&`${p.name} ${p.email} ${p.repo} ${p.team} ${p.reason} ${p.source}`.toLowerCase().includes(state.auditQuery.toLowerCase());
  });
}"""

if old_filtered in app_code:
    app_code = app_code.replace(old_filtered, new_filtered)
    print("Replaced filteredPeople with segmented triage filtering")
else:
    print("Warning: old_filtered not found exactly, attempting normalized replace")
    old_filtered_norm = old_filtered.replace('\r\n', '\n')
    app_code_norm = app_code.replace('\r\n', '\n')
    if old_filtered_norm in app_code_norm:
        app_code_norm = app_code_norm.replace(old_filtered_norm, new_filtered)
        app_code = app_code_norm
        print("Replaced normalized filteredPeople")

# Update auditPage() to display Triage Filter Tabs
old_audit_page_start = """function auditPage(){

  const filtered=filteredPeople();state.auditPage=Math.min(state.auditPage,Math.max(1,Math.ceil(filtered.length/6)));

  const rows=filtered.slice((state.auditPage-1)*6,state.auditPage*6);

  const filtersActive=state.auditQuery||state.auditRisk!=='All risks'||state.auditAccess!=='All access levels'||state.auditSource!=='All sources'||state.auditUser!=='All users'||state.auditRepo!=='All resources'||state.auditAction!=='All actions';

  return `<div class="audit-workbench">${pageHeading('Access audit','Inspect permissions. Review risk. Keep access appropriate.',`<button class="btn btn-outline" data-export="audit">Export CSV</button>${window.AutomationTimer ? window.AutomationTimer.renderChip() : ''}`)}${WorkspaceDesign.auditOverview()}

    <section class="card audit-register"><div class="register-heading"><div><span class="section-eyebrow">PERMISSION INVENTORY</span><h2>Access assignments</h2></div><span class="register-count">${filtered.length} of ${people.length} assignments</span></div><div class="audit-filters">"""

new_audit_page_start = """function auditPage(){
  const countAll = people.length;
  const countHigh = people.filter(p => p.risk === 'High' && !p.resolved).length;
  const countJit = people.filter(p => p.isTemporary && p.access !== 'None').length;
  const countExpiring = people.filter(p => (p.isTemporary && p.expiresAt && (new Date(p.expiresAt).getTime() - Date.now() < 86400000 * 3)) || p.team === 'External' || p.employment_status === 'contractor' || (p.reason && p.reason.toLowerCase().includes('contractor'))).length;
  const countInactive = people.filter(p => (p.reason && (p.reason.toLowerCase().includes('inactive') || p.reason.toLowerCase().includes('dormant'))) || (p.last && p.last.toLowerCase().includes('not recorded')) || (p.lastActiveAt && (Date.now() - new Date(p.lastActiveAt).getTime() > 86400000 * 30))).length;
  const countRemediated = people.filter(p => p.resolved).length;

  const filtered=filteredPeople();
  state.auditPage=Math.min(state.auditPage,Math.max(1,Math.ceil(filtered.length/6)));
  const rows=filtered.slice((state.auditPage-1)*6,state.auditPage*6);
  const filtersActive=state.auditSegment!=='all'||state.auditQuery||state.auditRisk!=='All risks'||state.auditAccess!=='All access levels'||state.auditSource!=='All sources'||state.auditUser!=='All users'||state.auditRepo!=='All resources'||state.auditAction!=='All actions';

  return `<div class="audit-workbench">${pageHeading('Access audit','Inspect permissions. Review risk. Keep access appropriate.',`<button class="btn btn-outline" data-export="audit">Export CSV</button>${window.AutomationTimer ? window.AutomationTimer.renderChip() : ''}`)}${WorkspaceDesign.auditOverview()}

    <section class="card audit-register">
      <div class="register-heading">
        <div><span class="section-eyebrow">PERMISSION INVENTORY</span><h2>Access assignments</h2></div>
        <span class="register-count">${filtered.length} of ${people.length} assignments</span>
      </div>

      <div class="audit-triage-tabs" style="display:flex;gap:6px;padding:8px 12px;background:var(--bg-subtle, #f8fafc);border-radius:8px;margin-bottom:14px;flex-wrap:wrap;align-items:center;">
        <span style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;margin-right:4px;">Triage Segments:</span>
        <button type="button" class="btn btn-sm ${state.auditSegment==='all'?'btn-primary':'btn-outline'}" data-audit-segment="all" style="border-radius:6px;font-size:12px;font-weight:600;">
          All (${countAll})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='high_risk'?'btn-primary':'btn-outline'}" data-audit-segment="high_risk" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='high_risk'?'background:#dc2626;border-color:#dc2626;color:#fff;':''}">
          🔥 High Risk (${countHigh})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='jit'?'btn-primary':'btn-outline'}" data-audit-segment="jit" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='jit'?'background:#2563eb;border-color:#2563eb;color:#fff;':''}">
          ⏱️ JIT Leases (${countJit})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='expiring'?'btn-primary':'btn-outline'}" data-audit-segment="expiring" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='expiring'?'background:#d97706;border-color:#d97706;color:#fff;':''}">
          ⏳ Expiring / Contracts (${countExpiring})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='inactive'?'btn-primary':'btn-outline'}" data-audit-segment="inactive" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='inactive'?'background:#475569;border-color:#475569;color:#fff;':''}">
          💤 Dormant / Inactive (${countInactive})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='remediated'?'btn-primary':'btn-outline'}" data-audit-segment="remediated" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='remediated'?'background:#16a34a;border-color:#16a34a;color:#fff;':''}">
          ✓ Remediated (${countRemediated})
        </button>
      </div>

      <div class="audit-filters">"""

app_code_norm = app_code.replace('\r\n', '\n')
old_audit_page_norm = old_audit_page_start.replace('\r\n', '\n')
if old_audit_page_norm in app_code_norm:
    app_code_norm = app_code_norm.replace(old_audit_page_norm, new_audit_page_start)
    app_code = app_code_norm
    print("Added Triage Segments Bar to auditPage")
else:
    print("Warning: old_audit_page_start not matched")

# Add click event handler for data-audit-segment
segment_click = """  if(b.matches('[data-audit-segment]')){
    state.auditSegment=b.dataset.auditSegment;
    state.auditPage=1;
    render();
  }
"""
if "data-audit-segment" not in app_code:
    app_code = app_code.replace(
        "if(b.matches('[data-page-link]'))location.hash=b.dataset.pageLink;",
        segment_click + "\n  if(b.matches('[data-page-link]'))location.hash=b.dataset.pageLink;"
    )
    print("Added data-audit-segment click handler")

# Update renderActivityTable to enrich table badges for JIT, contractor, dormant
old_row_render = """<td><span class=\"access-badge ${p.access==='Admin'?'admin':''}\">${safe(p.access)}</span>${p.isTemporary?`<span class=\"badge\" style=\"background:#fefce8;color:#854d0e;border:1px solid #fef08a;font-size:10px;padding:2px 5px;border-radius:4px;font-weight:700;margin-left:4px;\" title=\"JIT Temporary Access\">⏱️ JIT</span>`:''}</td><td>${p.resolved?`<span class=\"status-badge approved\">${safe(p.finding?.status||'Reviewed')}</span>`:riskPill(p.risk)}</td><td class=\"sub-cell\">${Governance.relativeMarkup(p.lastActiveAt,p.last)}</td>"""

new_row_render = """<td>
  <span class=\"access-badge ${p.access==='Admin'?'admin':''}\">${safe(p.access)}</span>
  ${p.isTemporary?`<span class=\"badge\" style=\"background:#fefce8;color:#854d0e;border:1px solid #fef08a;font-size:10px;padding:2px 5px;border-radius:4px;font-weight:700;margin-left:4px;\" title=\"JIT Temporary Access\">⏱️ JIT</span>`:''}
  ${(p.team==='External'||(p.job_role&&p.job_role.toLowerCase().includes('contractor'))||p.employment_status==='contractor'||(p.reason&&p.reason.toLowerCase().includes('contractor')))?`<span class=\"badge\" style=\"background:#fdf4ff;color:#86198f;border:1px solid #f5d0fe;font-size:10px;padding:2px 5px;border-radius:4px;font-weight:600;margin-left:4px;\" title=\"Contractor / Temporary\">🏷️ Contractor</span>`:''}
</td>
<td>${p.resolved?`<span class=\"status-badge approved\">${safe(p.finding?.status||'Reviewed')}</span>`:riskPill(p.risk)}</td>
<td class=\"sub-cell\">
  ${Governance.relativeMarkup(p.lastActiveAt,p.last)}
  ${((p.reason&&p.reason.toLowerCase().includes('inactive'))||(p.last&&p.last.toLowerCase().includes('not recorded')))?`<span class=\"badge\" style=\"display:block;margin-top:2px;font-size:10px;color:#64748b;background:#f1f5f9;border:1px solid #e2e8f0;width:fit-content;\">💤 Dormant</span>`:''}
</td>"""

old_row_norm = old_row_render.replace('\r\n', '\n')
app_code_norm = app_code.replace('\r\n', '\n')
if old_row_norm in app_code_norm:
    app_code_norm = app_code_norm.replace(old_row_norm, new_row_render)
    app_code = app_code_norm
    print("Enhanced row badges in renderActivityTable")

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(app_code)
print("Updated frontend/app.js successfully!")
