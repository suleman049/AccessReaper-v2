let people=[];

const requests=[];

let history=[];

let approvals=[];

const state={auditSegment:'all',auditRisk:'All risks',auditAccess:'All access levels',auditSource:'All sources',auditUser:'All users',auditRepo:'All resources',auditAction:'All actions',auditQuery:'',approvalQuery:'',approvalFilter:'Pending',historyQuery:'',historyAction:'All actions',historyRange:'Last 30 days',auditPage:1,historyPage:1,chartPeriod:'7 days'};const pageTitles={dashboard:'Overview',audit:'Access audit',approvals:'Approvals',history:'Audit history',users:'Users',settings:'Settings',request:'Request Repository Access'};const pageContent=document.querySelector('#page-content');

const safe=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const statusLabel=value=>value==='Declined'?'Rejected':String(value??'');

function isPersonDormant(p) {
  if (p.lastActiveAt) {
    const days = Math.floor((Date.now() - new Date(p.lastActiveAt).getTime()) / 86400000);
    return days >= 30;
  }
  if (typeof p.lastActiveDays === 'number') {
    return p.lastActiveDays >= 30;
  }
  const lastText = (p.last || '').toLowerCase();
  if (lastText.includes('not recorded') || lastText.includes('no recorded') || lastText.includes('dormant')) {
    return true;
  }
  return false;
}

const initials=s=>String(s).split(' ').map(v=>v[0]).slice(0,2).join('');

const badge=value=>`<span class="status-badge ${['pending','approved','declined'].includes(String(value).toLowerCase())?String(value).toLowerCase():'reviewed'}">${safe(statusLabel(value))}</span>`;

const avatar=(name,init)=>`<span class="person-avatar">${safe(init||initials(name))}</span>`;

const personCell=(name,init,email)=>`<div class="person-cell">${avatar(name,init)}<div><strong>${safe(name)}</strong><small title="${safe(email)}">${safe(email)}</small></div></div>`;

const riskPill=risk=>`<span class="status-badge ${['high','medium','low'].includes(String(risk).toLowerCase())?String(risk).toLowerCase():'reviewed'}">${safe(risk)}</span>`;

function pageHeading(title,sub,actions=''){return `<div class="page-heading"><div><h1>${safe(title)}</h1><p>${safe(sub)}</p></div><div class="heading-actions">${actions}</div></div>`}function auditSearch(id,value,placeholder){return `<div class="search-control"><span class="search-control-icon" aria-hidden="true">${uiIcon('search')}</span><input id="${id}" class="form-control" value="${safe(value)}" placeholder="${placeholder}"></div>`}

function renderActivityTable(limit=people.length,rows=people,showActions=false){const id=showActions?'audit-assignment-table':'overview-assignment-table';return `<div class="assignment-table-region"><p class="table-scroll-hint" id="${id}-hint">${uiIcon('chevronRight')} Scroll sideways for more columns. On phones, identity and review controls stay visible.</p><div class="table-responsive assignment-table-scroll" tabindex="0" role="region" aria-label="Access assignments, horizontally scrollable" aria-describedby="${id}-hint"><table class="table"><thead><tr><th>IDENTITY</th><th>RESOURCE / SOURCE</th><th>ACCESS</th><th>RISK</th><th>LAST ACTIVE</th>${showActions?'<th>RECOMMENDED ACTION</th>':''}<th><span class="visually-hidden">Details</span></th></tr></thead><tbody>${rows.slice(0,limit).map(p=>{
  const empStatus = p.employmentStatus || p.employment_status || '';
  const isContractor = (p.team==='External'||(p.role&&p.role.toLowerCase().includes('contractor'))||(p.job_role&&p.job_role.toLowerCase().includes('contractor'))||empStatus==='contractor'||(p.reason&&p.reason.toLowerCase().includes('contractor')));
  const isInactive = isPersonDormant(p);

  let jitBadge = '';
  if(p.isTemporary){
    let timeRemaining = 'JIT Lease';
    if(p.expiresAt){
      const msLeft = new Date(p.expiresAt).getTime() - Date.now();
      if(msLeft > 0){
        if(msLeft < 60000){
          timeRemaining = `${Math.ceil(msLeft / 1000)}s left`;
        } else if(msLeft < 3600000){
          timeRemaining = `${Math.ceil(msLeft / 60000)}m left`;
        } else {
          const hoursLeft = Math.round(msLeft / 3600000);
          timeRemaining = hoursLeft <= 48 ? `${hoursLeft}h left` : `${Math.round(hoursLeft/24)}d left`;
        }
      } else {
        timeRemaining = 'Expired (Reaping…)';
      }
    }
    jitBadge = `<span class="badge" data-jit-badge="${safe(p.id)}" data-expires-at="${safe(p.expiresAt || '')}" style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:700;margin-left:4px;display:inline-flex;align-items:center;gap:3px;" title="Just-In-Time Temporary Lease">${uiIcon('clock', 11)} <span class="jit-countdown-text">${timeRemaining}</span></span>`;
  }

  return `<tr><td>${personCell(p.name,p.initials,p.email)}</td><td class="repo-name">${safe(p.repo)}<small class="source-label">${safe(p.source)}</small></td><td>
  <span class="access-badge ${p.access==='Admin'?'admin':''}">${safe(p.access)}</span>
  ${jitBadge}
  ${isContractor?`<span class="badge" style="background:#fdf4ff;color:#86198f;border:1px solid #f5d0fe;font-size:10px;padding:2px 5px;border-radius:4px;font-weight:600;margin-left:4px;" title="Contractor / External">${uiIcon('briefcase', 11)} Contractor</span>`:''}
</td>
<td>${p.resolved?`<span class="status-badge approved">${safe(p.finding?.status||'Reviewed')}</span>`:riskPill(p.risk)}</td>
<td class="sub-cell">
  ${Governance.relativeMarkup(p.lastActiveAt,p.last)}
  ${isInactive?`<span class="badge" style="display:inline-flex;align-items:center;gap:3px;margin-top:2px;font-size:10px;color:#64748b;background:#f1f5f9;border:1px solid #e2e8f0;width:fit-content;">${uiIcon('userMinus', 11)} Dormant</span>`:''}
</td>${showActions?`<td class="recommended-action-cell">${safe(Governance.actionLabel(p))}</td>`:''}<td><button class="table-action" data-risk-person="${safe(p.id)}">${p.risk==='Low'||p.resolved?'Details':'Review'}</button></td></tr>`;
}).join('')}</tbody></table></div></div>`}

function auditPage(){
  const countAll = people.length;
  const countHigh = people.filter(p => p.risk === 'High' && !p.resolved).length;
  const countJit = people.filter(p => p.isTemporary && p.access !== 'None').length;
  const countExpiring = people.filter(p => {
    const empStatus = p.employmentStatus || p.employment_status || '';
    const isExpiringLease = p.isTemporary && p.expiresAt && (new Date(p.expiresAt).getTime() - Date.now() < 86400000 * 3);
    const isContractor = p.team === 'External' || (p.role && p.role.toLowerCase().includes('contractor')) || (p.job_role && p.job_role.toLowerCase().includes('contractor')) || empStatus === 'contractor' || (p.reason && p.reason.toLowerCase().includes('contractor'));
    return isExpiringLease || isContractor;
  }).length;
  const countInactive = people.filter(p => isPersonDormant(p)).length;
  const countRemediated = people.filter(p => p.resolved).length;

  const filtered=filteredPeople();
  state.auditPage=Math.min(state.auditPage,Math.max(1,Math.ceil(filtered.length/6)));
  const rows=filtered.slice((state.auditPage-1)*6,state.auditPage*6);
  const filtersActive=state.auditSegment!=='all'||state.auditQuery||state.auditRisk!=='All risks'||state.auditAccess!=='All access levels'||state.auditSource!=='All sources'||state.auditUser!=='All users'||state.auditRepo!=='All resources'||state.auditAction!=='All actions';

  let segmentBanner = '';
  if (state.auditSegment === 'high_risk') {
    segmentBanner = `
      <div class="alert mb-3" style="background:rgba(220,38,38,0.08);border-left:4px solid #dc2626;padding:10px 16px;border-radius:6px;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <span style="font-size:13px;color:#dc2626;">${uiIcon('shieldAlert', 15)} <strong>High-Risk Exposure List (${countHigh})</strong>: Users with unreviewed administrative rights, direct bypasses, or missing company mapping. Immediate review or revocation recommended.</span>
        <button class="btn btn-sm btn-outline" data-audit-segment="all" style="font-size:11px;padding:2px 8px;">Show All (${countAll})</button>
      </div>`;
  } else if (state.auditSegment === 'jit') {
    segmentBanner = `
      <div class="alert mb-3" style="background:rgba(37,99,235,0.08);border-left:4px solid #2563eb;padding:10px 16px;border-radius:6px;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <span style="font-size:13px;color:#2563eb;">${uiIcon('clock', 15)} <strong>Just-In-Time (JIT) Temporary Leases (${countJit})</strong>: Users granted time-bound repository privileges with automated revocation timers.</span>
        <button class="btn btn-sm btn-outline" data-audit-segment="all" style="font-size:11px;padding:2px 8px;">Show All (${countAll})</button>
      </div>`;
  } else if (state.auditSegment === 'expiring') {
    segmentBanner = `
      <div class="alert mb-3" style="background:rgba(217,119,6,0.08);border-left:4px solid #d97706;padding:10px 16px;border-radius:6px;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <span style="font-size:13px;color:#d97706;">${uiIcon('hourglass', 15)} <strong>Expiring Access & External Contractors (${countExpiring})</strong>: Contractors, external staff, and temporary assignments concluding shortly. Verify engagement renewals.</span>
        <button class="btn btn-sm btn-outline" data-audit-segment="all" style="font-size:11px;padding:2px 8px;">Show All (${countAll})</button>
      </div>`;
  } else if (state.auditSegment === 'inactive') {
    segmentBanner = `
      <div class="alert mb-3" style="background:rgba(71,85,105,0.08);border-left:4px solid #475569;padding:10px 16px;border-radius:6px;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <span style="font-size:13px;color:#475569;">${uiIcon('userMinus', 15)} <strong>Dormant & Inactive Accounts (${countInactive})</strong>: Assignments with no recorded activity in 30+ days. Prime candidates for least-privilege revocation.</span>
        <button class="btn btn-sm btn-outline" data-audit-segment="all" style="font-size:11px;padding:2px 8px;">Show All (${countAll})</button>
      </div>`;
  } else if (state.auditSegment === 'remediated') {
    segmentBanner = `
      <div class="alert mb-3" style="background:rgba(22,163,74,0.08);border-left:4px solid #16a34a;padding:10px 16px;border-radius:6px;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <span style="font-size:13px;color:#16a34a;">${uiIcon('checkCircle', 15)} <strong>Remediated & Reviewed Access List (${countRemediated})</strong>: Permissions reviewed, reduced, or approved by administrator with documented compliance justification.</span>
        <button class="btn btn-sm btn-outline" data-audit-segment="all" style="font-size:11px;padding:2px 8px;">Show All (${countAll})</button>
      </div>`;
  }

  return `<div class="audit-workbench">${pageHeading('Access audit','Inspect permissions. Review risk. Keep access appropriate.',`<button class="btn btn-outline" data-export="audit">Export CSV</button>${window.AutomationTimer ? window.AutomationTimer.renderChip() : ''}`)}${WorkspaceDesign.auditOverview()}

    <section class="card audit-register">
      <div class="register-heading">
        <div><span class="section-eyebrow">PERMISSION INVENTORY</span><h2>Access assignments</h2></div>
        <span class="register-count">${filtered.length} of ${people.length} assignments</span>
      </div>

      <div class="audit-triage-tabs" style="display:flex;gap:6px;padding:8px 12px;background:var(--surface-soft, #f1f4f9);border:1px solid var(--border, #e2e8f0);border-radius:8px;margin-bottom:14px;flex-wrap:wrap;align-items:center;">
        <span style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;margin-right:4px;">Triage Segments:</span>
        <button type="button" class="btn btn-sm ${state.auditSegment==='all'?'btn-primary':'btn-outline'}" data-audit-segment="all" style="border-radius:6px;font-size:12px;font-weight:600;">
          ${uiIcon('layers', 13)} All (${countAll})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='high_risk'?'btn-primary':'btn-outline'}" data-audit-segment="high_risk" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='high_risk'?'background:#dc2626;border-color:#dc2626;color:#fff;':''}">
          ${uiIcon('shieldAlert', 13)} High Risk (${countHigh})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='jit'?'btn-primary':'btn-outline'}" data-audit-segment="jit" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='jit'?'background:#2563eb;border-color:#2563eb;color:#fff;':''}">
          ${uiIcon('clock', 13)} JIT Leases (${countJit})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='expiring'?'btn-primary':'btn-outline'}" data-audit-segment="expiring" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='expiring'?'background:#d97706;border-color:#d97706;color:#fff;':''}">
          ${uiIcon('hourglass', 13)} Expiring / Contracts (${countExpiring})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='inactive'?'btn-primary':'btn-outline'}" data-audit-segment="inactive" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='inactive'?'background:#475569;border-color:#475569;color:#fff;':''}">
          ${uiIcon('userMinus', 13)} Dormant / Inactive (${countInactive})
        </button>
        <button type="button" class="btn btn-sm ${state.auditSegment==='remediated'?'btn-primary':'btn-outline'}" data-audit-segment="remediated" style="border-radius:6px;font-size:12px;font-weight:600;${state.auditSegment==='remediated'?'background:#16a34a;border-color:#16a34a;color:#fff;':''}">
          ${uiIcon('checkCircle', 13)} Remediated (${countRemediated})
        </button>
      </div>
      ${segmentBanner}

      <div class="audit-filters"><div class="filter-search-line">${auditSearch('audit-search',state.auditQuery,'Search people or resources…')}${filtersActive?'<button class="btn btn-outline btn-sm" id="clear-filters">Clear filters</button>':''}</div><div class="filter-select-line"><div><label for="risk-filter">Risk</label>${selectControl('risk-filter','Risk level',['All risks','High','Medium','Low'],state.auditRisk)}</div><div><label for="access-filter">Access level</label>${selectControl('access-filter','Access level',['All access levels','Admin','Write','Read','Editor','Viewer','None'],state.auditAccess)}</div><div><label for="source-filter">Source</label>${selectControl('source-filter','Access source',['All sources','GitHub','Firestore'],state.auditSource)}</div><div><label for="user-filter">User</label>${selectControl('user-filter','User',['All users',...new Set(people.map(p=>p.email))],state.auditUser)}</div><div><label for="repo-filter">Resource</label>${selectControl('repo-filter','Resource',['All resources',...new Set(people.map(p=>p.repo))],state.auditRepo)}</div><div><label for="action-filter">Recommended action</label>${selectControl('action-filter','Recommended action',['All actions','Reduce access','Revoke access','Keep access','Reviewed'],state.auditAction)}</div></div></div>

    <section class="table-panel audit-table">${filtered.length?renderActivityTable(rows.length,rows,true):'<div class="empty-state"><strong>No assignments match</strong>Try another search or clear your filters.</div>'}<div class="page-pagination">${pagination('audit',state.auditPage,filtered.length)}</div></section></section></div>`;
}

function dashboard(){return WorkspaceDesign.dashboard();}

function detailPage(email=decodeURIComponent(location.hash.split('?')[1]||people[0].id)){return Governance.detail(email);}

function approvalsPage(){

  const filtered=approvals.filter(a=>(state.approvalFilter==='All requests'||a.status===state.approvalFilter)&&(`${a.person} ${a.repo} ${a.id} ${a.reason} ${a.githubLogin||''}`).toLowerCase().includes(state.approvalQuery.toLowerCase()));

  return `<div class="approvals-workbench">${pageHeading('Approvals','Review and manage repository access requests for payhive-eng.',`<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;"><button class="btn btn-outline" id="btn-share-request-link" title="Copy public link to share with friends or collaborators" style="font-size:12.5px;padding:6px 12px;display:inline-flex;align-items:center;gap:6px;">${uiIcon('link', 13)} Share Request Link</button><button class="btn btn-primary" id="btn-open-request-modal" style="font-size:12.5px;padding:6px 14px;display:inline-flex;align-items:center;gap:6px;background:#16a34a;border-color:#16a34a;font-weight:700;">${uiIcon('people', 14)} + Onboard & Request Access</button></div>`)}

  <section class="card request-metrics" aria-label="Request totals">

    ${[['Pending','Awaiting review'],['Approved','Approved'],['Declined','Rejected']].map(([status,label])=>`<div><span>${label}</span><strong>${approvals.filter(a=>a.status===status).length}</strong></div>`).join('')}

    <div class="request-risk"><span>High-risk pending</span><strong>${approvals.filter(a=>a.status==='Pending'&&a.risk==='High').length}</strong></div>

  </section>

  <section class="request-queue">

    <div class="queue-heading">

      <div>

        <span class="section-eyebrow">DECISION QUEUE</span>

        <h2>${state.approvalFilter==='All requests'?'All requests':statusLabel(state.approvalFilter)+' requests'} <span>${filtered.length}</span></h2>

      </div>

      <p>Review business justifications and onboard new employees. One-click approval executes live permission grants on GitHub and emails the user.</p>

    </div>

    <div class="card queue-tools">

      ${auditSearch('approval-search',state.approvalQuery,'Search requests, people or GitHub handles…')}

      <label class="queue-status" for="approval-filter">

        <span>Request status</span>

        ${selectControl('approval-filter','Request status',['Pending','Approved','Declined','All requests'],state.approvalFilter)}

      </label>

    </div>

    <div class="request-list">${filtered.length?filtered.map(a=>{

      const isDirectGrant = a.type === 'Direct GitHub Grant Review';
      const isNewEmployee = !isDirectGrant && (a.isNewEmployee || (a.email && a.email.endsWith('@payhive.internal')) || (a.email && a.email.endsWith('@github.unmatched')) || (a.githubLogin && !people.some(p => p.email === a.email && p.source === 'GitHub')) || a.type === 'New employee onboarding');

      const ghTag = a.githubLogin ? `@${a.githubLogin}` : (a.email.includes('@github.unmatched') ? `@${a.email.split('@')[0]}` : '');
      const bannerHtml = isDirectGrant
        ? `<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;"><span class="badge" style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;font-size:11px;padding:3px 8px;border-radius:6px;font-weight:700;">${uiIcon('alert', 12)} DIRECT GITHUB ACCESS DETECTED</span>${ghTag ? `<span class="badge" style="background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;font-size:11px;padding:3px 8px;font-family:monospace;font-weight:600;">${safe(ghTag)}</span>` : ''}</div>`
        : (isNewEmployee
            ? `<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;"><span class="badge" style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;font-size:11px;padding:3px 8px;border-radius:6px;font-weight:700;">${uiIcon('people', 12)} NEW EMPLOYEE ONBOARDING</span>${ghTag ? `<span class="badge" style="background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;font-size:11px;padding:3px 8px;font-family:monospace;font-weight:600;">${safe(ghTag)}</span>` : ''}</div>`
            : '');

      return `<article class="card approval-card" style="${(isNewEmployee || isDirectGrant) && a.status === 'Pending' ? 'border-left: 4px solid #ff4d1f;' : ''}">

        ${bannerHtml}

        <div class="approval-card-top">

          <div class="approval-kind">${a.type==='Role change'?'↻':a.type==='Access removal'?'−':'+'}</div>

          <div style="flex:1">

            <h3>${safe(a.type)} · ${safe(a.repo)}${a.durationHours?` <span class="badge" style="background:#fefce8;color:#854d0e;border:1px solid #fef08a;font-size:11px;padding:2px 6px;border-radius:4px;font-weight:700;">${uiIcon('clock', 11)} ${a.durationHours}h JIT Lease</span>`:''}</h3>

            <p>${safe(a.id)} &nbsp;·&nbsp; <strong>${safe(a.person)}</strong> ${ghTag ? `(${safe(ghTag)})` : ''} <span class="request-email">${safe(a.email)}</span> &nbsp;·&nbsp; ${Governance.relativeMarkup(a.requestedAt,a.requested)}</p>

          </div>

          ${badge(a.status)}

        </div>

        ${isNewEmployee && a.status === 'Pending' ? `

          <div style="background:#fffbeb;border:1px solid #fef3c7;border-radius:6px;padding:8px 12px;margin:10px 0;font-size:12px;color:#92400e;line-height:1.4;">

            <strong>${uiIcon('alert', 13)} Directory Conflict Detected:</strong> <code>${safe(ghTag || a.person)}</code> is requesting access to <strong>${safe(a.repo)}</strong>, but is not yet registered in your directory. Approving will automatically provision their employee identity in <strong>payhive-eng</strong>, map their GitHub account, grant collaborator permissions live on GitHub, and dispatch a welcome email.

          </div>

        ` : ''}

        <div class="approval-info">

          <div>

            <span>Current → requested access</span>

            <strong>

              <span class="request-current">${safe(people.find(p=>p.email===a.email&&p.repo===a.repo)?.access||'None')} → </span>

              <span class="access-badge ${a.access==='Admin'?'admin':''}">${safe(a.access)}</span>

            </strong>

          </div>

          <div><span>Request risk</span><strong>${riskPill(a.risk)}</strong></div>

          <div><span>Business reason</span><strong>${safe(a.reason)}</strong></div>

        </div>

        ${a.status==='Pending'?`<div class="approval-actions">

          <button class="btn btn-outline btn-sm" data-review="${safe(a.id)}" data-action="Declined" style="${isDirectGrant ? 'color:#dc2626;border-color:#fca5a5;' : ''}">${isDirectGrant ? 'Reject & Revoke from GitHub' : 'Reject'}</button>

          <button class="btn btn-primary btn-sm" data-review="${safe(a.id)}" data-action="Approved" style="${isNewEmployee ? 'background:#16a34a;border-color:#16a34a;font-weight:700;' : ''}">

            ${isDirectGrant ? 'Approve & Ratify Grant' : (isNewEmployee ? 'Approve & Onboard to GitHub' : 'Approve request')}

          </button>

        </div>`:''}

      </article>`;

    }).join(''):'<div class="card empty-state">◷<strong>No requests in this view</strong>Try selecting another request status.</div>'}</div>

  </section></div>`

}

function historyPage(){return Governance.history();}

function settingsPage(){return WorkspaceDesign.settings();}

// The live workspace store is synchronized directly with the backend API.

const STORE_KEY = 'accessreaper-live-v1';

let lastAudit = 'Oct 25, 2026';

let auditing = false;

const StorageStatus={ok:true,dirty:false,themeFailed:false};

const initialStore = JSON.stringify({people:[],approvals:[],history:[],lastAudit});

try {

  localStorage.removeItem('accessreaper-demo-v3');

  localStorage.removeItem('accessreaper-demo-v2');

  const stored = JSON.parse(localStorage.getItem(STORE_KEY));

  if (stored && Array.isArray(stored.people) && stored.people.length > 0 && stored.people.every(p => p.source === 'GitHub' && !p.email?.includes('@acme.io') && !p.repo?.startsWith('acme/'))) {

    people=stored.people; approvals=stored.approvals||[]; history=stored.history||[]; lastAudit=stored.lastAudit || lastAudit; auditRuns=stored.auditRuns||[]; auditSnapshots=stored.auditSnapshots||[];

  }

} catch { /* A blocked browser store leaves this session fully usable. */ }

function syncStorageWarning(){const warning=!StorageStatus.ok||StorageStatus.themeFailed;document.querySelectorAll('[data-storage-warning]').forEach(el=>{el.hidden=!warning;el.querySelector('[data-storage-message]').textContent=!StorageStatus.ok?'Browser saving is unavailable. Changes are kept in this session only and may be lost when you reload or close this page.':'Your theme changed for this session, but the preference could not be saved.';});document.querySelectorAll('[data-storage-label]').forEach(el=>el.textContent=StorageStatus.ok?'Saved in this browser':'Session memory only · not saved');}

function persist(markDirty=true){try{localStorage.setItem(STORE_KEY,JSON.stringify({people,approvals,history,lastAudit,auditRuns,auditSnapshots}));StorageStatus.ok=true;StorageStatus.dirty=false;syncStorageWarning();return true;}catch{StorageStatus.ok=false;StorageStatus.dirty=StorageStatus.dirty||markDirty;syncStorageWarning();return false;}}

function decisionFeedback(message){showToast(StorageStatus.ok?message:message.replace(/comment saved/g,'comment kept in session')+' Not saved to this browser; reloading may lose this change.');}

window.addEventListener('beforeunload',e=>{if(StorageStatus.dirty){e.preventDefault();e.returnValue='';}});

document.addEventListener('theme-storage-result',e=>{StorageStatus.themeFailed=!e.detail.ok;syncStorageWarning();});

let tableResizeObserver;

function syncTableScroll(){tableResizeObserver?.disconnect();const update=el=>el.closest('.assignment-table-region').classList.toggle('has-overflow',el.scrollWidth>el.clientWidth+1);if(window.ResizeObserver)tableResizeObserver=new ResizeObserver(entries=>entries.forEach(e=>update(e.target)));document.querySelectorAll('.assignment-table-scroll').forEach(el=>{update(el);tableResizeObserver?.observe(el);});}



function nowParts(){const d=new Date(); return {date:d.toLocaleDateString('en-CA',{timeZone:'Asia/Karachi'}),time:d.toLocaleTimeString('en-US',{timeZone:'Asia/Karachi',hour:'2-digit',minute:'2-digit'})};}

function filteredPeople(){
  return people.filter(p=>{
    const empStatus = p.employmentStatus || p.employment_status || '';
    if(state.auditSegment==='high_risk'&&(p.risk!=='High'||p.resolved))return false;
    if(state.auditSegment==='jit'&&(!p.isTemporary||p.access==='None'))return false;
    if(state.auditSegment==='expiring'){
      const isExpiringLease=p.isTemporary&&p.expiresAt&&(new Date(p.expiresAt).getTime()-Date.now()<86400000*3);
      const isContractor=(p.team==='External'||(p.role&&p.role.toLowerCase().includes('contractor'))||(p.job_role&&p.job_role.toLowerCase().includes('contractor'))||empStatus==='contractor'||(p.reason&&p.reason.toLowerCase().includes('contractor')));
      if(!isExpiringLease&&!isContractor)return false;
    }
    if(state.auditSegment==='inactive'){
      if(!isPersonDormant(p))return false;
    }
    if(state.auditSegment==='remediated'&&!p.resolved)return false;
    return (state.auditRisk==='All risks'||(!p.resolved&&p.risk===state.auditRisk))&&(state.auditAccess==='All access levels'||p.access===state.auditAccess)&&(state.auditSource==='All sources'||p.source===state.auditSource)&&(state.auditUser==='All users'||p.email===state.auditUser)&&(state.auditRepo==='All resources'||p.repo===state.auditRepo)&&(state.auditAction==='All actions'||Governance.actionLabel(p)===state.auditAction)&&`${p.name} ${p.email} ${p.repo} ${p.team} ${p.reason} ${p.source}`.toLowerCase().includes(state.auditQuery.toLowerCase());
  });
}

function filteredHistory(){const days=Number(state.historyRange.match(/\d+/)[0]),end=Date.now(),start=end-days*86400000;return Governance.orderedEvents().filter(e=>{const at=Date.parse(Governance.timestamp(e));return Number.isFinite(at)&&at>=start&&at<=end&&`${e.id} ${e.title} ${e.actor} ${e.detail} ${e.tag} ${e.note||''} ${e.requestId||''} ${e.source||''}`.toLowerCase().includes(state.historyQuery.toLowerCase())&&(state.historyAction==='All actions'||e.tag===state.historyAction);});}

function selectControl(id,label,options,value){return `<select id="${id}" aria-label="${label}" class="form-control select-control">${options.map(o=>`<option value="${safe(o)}"${o===value?' selected':''}>${safe(statusLabel(o))}</option>`).join('')}</select>`;}

function pagination(kind,page,total){const max=Math.max(1,Math.ceil(total/6));return `<span>Showing ${total?(page-1)*6+1:0}–${Math.min(page*6,total)} of ${total} ${kind==='audit'?'assignments':'events'}</span><div class="pagination-buttons"><button class="page-button" data-pagination="${kind}" data-direction="-1" aria-label="Previous page" ${page<=1?'disabled':''}>←</button><span class="pagination-position">${page} / ${max}</span><button class="page-button" data-pagination="${kind}" data-direction="1" aria-label="Next page" ${page>=max?'disabled':''}>→</button></div>`;}

function publicRequestPage() {
  const isAuth = window.FirebaseIdentity && window.FirebaseIdentity.authorized;
  return `
    <div style="max-width: 680px; margin: 32px auto; padding: 0 16px;">
      <div style="text-align: center; margin-bottom: 24px;">
        <div style="display:inline-flex;align-items:center;justify-content:center;width:52px;height:52px;border-radius:14px;background:rgba(255,77,31,0.1);color:#ff4d1f;margin-bottom:12px;">
          ${uiIcon('shield', 28)}
        </div>
        <h1 style="font-size: 24px; font-weight: 800; margin: 0 0 8px 0; color: var(--text, #0f172a);">Request Repository Access</h1>
        <p style="font-size: 14px; color: var(--muted, #64748b); max-width: 520px; margin: 0 auto; line-height: 1.5;">
          Submit your GitHub handle and requested access. Your request generates a real-time approval notification for administrators.
        </p>
      </div>

      <div class="card" style="padding: 28px; border-radius: 14px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08); border: 1px solid var(--border, #e2e8f0);" id="public-request-card">
        <form id="public-access-request-form">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
            <div>
              <label class="form-label" style="font-size:12.5px;font-weight:700;">Your Full Name <span class="text-danger">*</span></label>
              <input type="text" class="form-control" id="pub-name-input" placeholder="e.g. John Doe" required />
            </div>
            <div>
              <label class="form-label" style="font-size:12.5px;font-weight:700;">Your Email <span class="text-danger">*</span></label>
              <input type="email" class="form-control" id="pub-email-input" placeholder="e.g. team-member@payhive.com" required />
            </div>
          </div>

          <div style="margin-bottom:16px;">
            <label class="form-label" style="font-size:12.5px;font-weight:700;">GitHub Account Username <span class="text-danger">*</span></label>
            <div style="position:relative;">
              <span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--muted,#94a3b8);font-weight:700;">@</span>
              <input type="text" class="form-control" id="pub-github-input" placeholder="octocat or username" style="padding-left:28px;" required />
            </div>
            <small style="font-size:11.5px;color:var(--muted,#64748b);display:block;margin-top:4px;">
              This exact GitHub username will be invited to the repository upon administrator approval.
            </small>
          </div>

          <div style="display:grid;grid-template-columns:1.5fr 1fr;gap:16px;margin-bottom:16px;">
            <div>
              <label class="form-label" style="font-size:12.5px;font-weight:700;">Target GitHub Repository <span class="text-danger">*</span></label>
              <select class="form-control" id="pub-repo-select" required>
                <option value="payhive-eng/payment-gateway">payhive-eng/payment-gateway</option>
                <option value="payhive-eng/auth-service">payhive-eng/auth-service</option>
                <option value="payhive-eng/infra-terraform">payhive-eng/infra-terraform</option>
                <option value="payhive-eng/billing-engine">payhive-eng/billing-engine</option>
                <option value="payhive-eng/mobile-app">payhive-eng/mobile-app</option>
                <option value="payhive-eng/customer-web">payhive-eng/customer-web</option>
                <option value="payhive-eng/data-pipelines">payhive-eng/data-pipelines</option>
                <option value="payhive-eng/internal-wiki">payhive-eng/internal-wiki</option>
                <option value="payhive-eng/hackathon-bot">payhive-eng/hackathon-bot</option>
                <option value="payhive-eng/demo-repository">payhive-eng/demo-repository</option>
              </select>
            </div>
            <div>
              <label class="form-label" style="font-size:12.5px;font-weight:700;">Requested Role <span class="text-danger">*</span></label>
              <select class="form-control" id="pub-access-select" required>
                <option value="Read">Read (View & Pull)</option>
                <option value="Write" selected>Write (Contributor / Push)</option>
                <option value="Admin">Admin (Full Access)</option>
              </select>
            </div>
          </div>

          <div style="margin-bottom:16px;">
            <label class="form-label" style="font-size:12.5px;font-weight:700;">Duration / Lease Type</label>
            <select class="form-control" id="pub-duration-select">
              <option value="0.0167">⚡ 1 Minute (Live Demo Test)</option>
              <option value="1">⏱️ 1 Hour JIT Lease</option>
              <option value="8">⏱️ 8 Hours (Workday Lease)</option>
              <option value="24">⏱️ 24 Hours (1 Day)</option>
              <option value="0" selected>♾️ Permanent Role Assignment</option>
            </select>
          </div>

          <div style="margin-bottom:20px;">
            <label class="form-label" style="font-size:12.5px;font-weight:700;">Business Justification <span class="text-danger">*</span></label>
            <textarea class="form-control" id="pub-reason-input" rows="3" placeholder="Explain why you require access to this repository and what work you will be doing..." required></textarea>
          </div>

          <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
            ${isAuth ? `<button type="button" class="btn btn-outline" onclick="location.hash='approvals'">← Back to Approvals</button>` : `<div></div>`}
            <button type="submit" class="btn btn-primary" id="pub-submit-btn" style="padding:9px 24px;font-weight:700;">
              Submit Access Request →
            </button>
          </div>
        </form>
      </div>
    </div>
  `;
}

function renderAuth(mode){AccessReaperAuth.render(mode);Theme.sync();syncStorageWarning();FirebaseUI.syncForm();}

function render(){let page=location.hash.slice(1).split('?')[0]||'login';if(page==='audit'){if(location.hash.includes('?')){const q=new URLSearchParams(location.hash.slice(location.hash.indexOf('?')+1));state.auditSegment=q.get('segment')||'all';}else{state.auditSegment='all';}}if(FirebaseUI.guard(page))return;const auth=['login','signup'].includes(page);document.querySelector('#app').classList.toggle('d-none',auth);document.querySelector('#login-screen').classList.toggle('d-none',!auth);if(auth){renderAuth(page);document.title=`${page==='login'?'Sign in':'Sign up'} · AccessReaper`;return;}if(!pageTitles[page]&&page!=='risk'){location.hash='dashboard';return;}document.title=`${page==='risk'?'Risk details':pageTitles[page]} · AccessReaper`;document.querySelector('#crumb-title').textContent=page==='risk'?'Risk details':pageTitles[page];document.querySelectorAll('.main-nav a').forEach(a=>{const active=a.dataset.page===(page==='risk'?'audit':page);a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');a.title=a.textContent.trim();});const pages={dashboard,audit:auditPage,approvals:approvalsPage,history:historyPage,users:()=>(typeof UsersPage !== 'undefined' ? UsersPage.render() : ''),settings:settingsPage,request:publicRequestPage};try {pageContent.innerHTML=page==='risk'?detailPage():pages[page]();}catch{pageContent.innerHTML='<section class="card load-error" role="alert"><strong>This view could not be loaded.</strong><p>Your records have not been changed. Try reloading the view.</p><button class="btn btn-outline" data-retry-view>Try again</button></section>';}

if(page==='users'&&window.UsersPage){

  if (!UsersPage.initialized) {

    UsersPage.initialized = true;

    Promise.all([UsersPage.fetchUsers(), UsersPage.fetchPeople()]).then(() => {
      if (location.hash.slice(1).split('?')[0] === 'users' && typeof render === 'function') render();
    });

  }

  UsersPage.attachEvents(pageContent);

}

if(page==='settings'){

  const settingsMain = pageContent.querySelector('.settings-main');

  if (settingsMain) {

    if (!settingsMain.querySelector('#risk-rules-settings-card') && typeof RulesSettings !== 'undefined') {

      const div = document.createElement('div');

      div.innerHTML = RulesSettings.renderCard();

      while (div.firstChild) settingsMain.appendChild(div.firstChild);

    }

    if (!settingsMain.querySelector('#schedule-settings-card') && typeof ScheduleSettings !== 'undefined') {

      const div = document.createElement('div');

      div.innerHTML = ScheduleSettings.renderCard();

      while (div.firstChild) settingsMain.appendChild(div.firstChild);

    }

    if (!settingsMain.querySelector('#autopilot-settings-card') && typeof AutoPilotSettings !== 'undefined') {

      const div = document.createElement('div');

      div.innerHTML = AutoPilotSettings.renderCard();

      while (div.firstChild) settingsMain.appendChild(div.firstChild);

    }

    if (!settingsMain.querySelector('#notifications-settings-card') && typeof NotificationsSettings !== 'undefined') {

      const div = document.createElement('div');

      div.innerHTML = NotificationsSettings.renderCard();

      while (div.firstChild) settingsMain.appendChild(div.firstChild);

    }

  }

  if(typeof RulesSettings !== 'undefined'){ RulesSettings.init(); RulesSettings.attachEvents(pageContent); }

  if(typeof ScheduleSettings !== 'undefined'){ ScheduleSettings.init(); ScheduleSettings.attachEvents(pageContent); }
  if(typeof AutoPilotSettings !== 'undefined'){ AutoPilotSettings.init(); AutoPilotSettings.attachEvents(pageContent); }

  if(typeof NotificationsSettings !== 'undefined'){ NotificationsSettings.init(); NotificationsSettings.attachEvents(pageContent); }

  if(typeof GitHubSettings !== 'undefined'){ GitHubSettings.init(); }

}

if(typeof GitHubSettings !== 'undefined') GitHubSettings.updateHeaderBadge();

if(window.UsersPage)UsersPage.updateNavBadge();document.querySelector('#nav-risk-count').textContent=people.filter(p=>p.risk==='High'&&!p.resolved).length;document.querySelector('#nav-approval-count').textContent=approvals.filter(a=>a.status==='Pending').length;document.querySelectorAll('.search-control input').forEach(el=>el.setAttribute('aria-label',el.placeholder));document.querySelectorAll('.risk-arrow').forEach(el=>el.setAttribute('aria-label',`Review ${people.find(p=>p.id===el.dataset.riskPerson)?.name||'finding'}`));document.querySelectorAll('#chart-period button').forEach(b=>{b.classList.toggle('active',b.textContent===state.chartPeriod);b.setAttribute('aria-pressed',String(b.textContent===state.chartPeriod));});if(page==='dashboard')updateChart();if(page==='audit'&&auditing){let b=document.querySelector('#run-audit');if(b){b.disabled=true;b.textContent='Auditing…';}}refreshIcons(page);FirebaseUI.syncIdentity();Theme.sync();syncStorageWarning();syncTableScroll();document.querySelector('#approval-filter')?.querySelectorAll('option').forEach(o=>o.selected=o.textContent===state.approvalFilter);document.querySelector('#risk-filter')?.setAttribute('aria-label','Risk level');document.querySelector('#approval-filter')?.setAttribute('aria-label','Request status');}

let chartResizeObserver;

function updateChart(){

  chartResizeObserver?.disconnect();

  const svg=document.querySelector('.trend-chart svg');

  if(!svg){chartResizeObserver?.disconnect();return;}

  const high=Governance.stats().high;

  const snapshots=Governance.trend(state.chartPeriod);

  const chartNote=document.querySelector('.chart-data-note');if(chartNote)chartNote.textContent=`${snapshots.filter(s=>s.high!==null).length} recorded day(s) in this period. Dates without records are left blank.`;

  const values=snapshots.map(s=>s.high);

  const remediated=snapshots.map(s=>s.remediated);

  const dates=snapshots.map(s=>[s.date.toLocaleDateString('en-US',{timeZone:'Asia/Karachi',month:'short'}),s.date.toLocaleDateString('en-US',{timeZone:'Asia/Karachi',day:'2-digit'})]);

  function draw(){

    if(!svg.isConnected)return;

    const width=Math.max(240,svg.getBoundingClientRect().width),height=210,left=36,right=22,top=14,bottom=158,maxY=Math.max(12,Math.ceil(Math.max(...values.filter(v=>v!==null),...remediated.filter(v=>v!==null),0)/6)*6);

    const x=i=>left+(width-left-right)*i/Math.max(1,snapshots.length-1);

    const y=value=>bottom-(bottom-top)*value/maxY;

    function smooth(series){let line='',last=null;for(let i=0;i<series.length;i++){if(series[i]===null){last=null;continue;}if(last===null)line+=` M ${x(i)} ${y(series[i])}`;else {const mid=(x(last)+x(i))/2;line+=` C ${mid} ${y(series[last])}, ${mid} ${y(series[i])}, ${x(i)} ${y(series[i])}`;}last=i;}return line;}

    const riskPath=smooth(values),resolvedPath=smooth(remediated);

    const tickCount=width<360?3:width<520?4:7;const shown=[...new Set(Array.from({length:tickCount},(_,i)=>Math.round(i*(snapshots.length-1)/(tickCount-1))))];

    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);

    svg.setAttribute('preserveAspectRatio','xMidYMid meet');

    svg.setAttribute('aria-label',`${state.chartPeriod} access risk trend from ${dates[0].join(' ')} to ${dates.at(-1).join(' ')}; ${high} current high-risk findings.`);

    svg.innerHTML=`<defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ff4d1f" stop-opacity=".12"/><stop offset="100%" stop-color="#ff4d1f" stop-opacity="0"/></linearGradient></defs>${[maxY,maxY*2/3,maxY/3,0].map(value=>`<line class="chart-grid" x1="${left}" y1="${y(value)}" x2="${width-right}" y2="${y(value)}"/><text class="chart-label" x="${left-12}" y="${y(value)+4}" text-anchor="end">${Math.round(value)}</text>`).join('')}<path class="chart-line" d="${riskPath}" vector-effect="non-scaling-stroke"/><path class="chart-line-secondary" d="${resolvedPath}" vector-effect="non-scaling-stroke"/>${values.map((v,i)=>v===null?'':`<circle class="chart-dot" cx="${x(i)}" cy="${y(v)}" r="3.5"/>`).join('')}${remediated.map((v,i)=>v===null?'':`<circle class="chart-dot-secondary" cx="${x(i)}" cy="${y(v)}" r="3"/>`).join('')}${shown.map(i=>`<text class="chart-date" x="${x(i)}" y="181" text-anchor="middle"><tspan class="chart-date-day" x="${x(i)}">${dates[i][1]}</tspan><tspan class="chart-date-month" x="${x(i)}" dy="15">${dates[i][0]}</tspan></text>`).join('')}`;

  }

  draw();

  chartResizeObserver=new ResizeObserver(draw);

  chartResizeObserver.observe(svg.parentElement);

}



function showToast(message){const el=document.createElement('div');el.className='toast-card';el.textContent=message;document.querySelector('#toast-container').replaceChildren(el);setTimeout(()=>el.remove(),3500);}

function exportCsv(kind){

  let rows;

  if(kind==='audit'||kind==='dashboard')rows=(kind==='audit'?filteredPeople():people).map(p=>({assignmentId:p.id,name:p.name,email:p.email,resource:p.repo,source:p.source,team:p.team,currentAccess:p.access,recommendedAction:Governance.actionLabel(p),originalAccess:p.finding.originalAccess,originalSeverity:p.finding.originalSeverity,findingStatus:p.finding.status,originalReason:p.finding.originalReason,detectedAt:p.finding.detectedAt}));

  else if(kind==='approvals')rows=approvals.filter(a=>(state.approvalFilter==='All requests'||a.status===state.approvalFilter)&&`${a.person} ${a.repo} ${a.id} ${a.reason}`.toLowerCase().includes(state.approvalQuery.toLowerCase())).map(a=>({...a,requested:Governance.relative(a.requestedAt),requestedAt:a.requestedAt||''}));

  else rows=filteredHistory().map(e=>({eventId:e.id,timestamp:Governance.timestamp(e),actor:e.actor,action:e.tag,title:e.title,source:e.source||'',assignmentId:e.assignmentId||'',requestId:e.requestId||'',auditId:e.auditId||'',resourceAndIdentity:e.detail,permissionBefore:e.before??'',permissionAfter:e.after??'',decisionNote:e.note||''}));

  if(!rows.length){showToast('There are no records to export in this view.');return;}

  const keys=[...new Set(rows.flatMap(r=>Object.keys(r)))];

  const cell=value=>{let text=String(value??'');if(/^[=+@-]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';};

  const csv=[keys.map(cell).join(','),...rows.map(r=>keys.map(k=>cell(r[k])).join(','))].join('\r\n');

  const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));

  const link=document.createElement('a');link.href=url;link.download=`accessreaper-${kind}-report.csv`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);showToast(`${rows.length} organization records exported.`);

}

let confirmAction=null;

function openDecision(title,description,summary,button,action,requireNote=true){document.querySelector('#review-modal').classList.remove('is-audit-report');document.querySelector('#review-modal-body').innerHTML=`<div class="d-flex justify-content-between mb-3"><span class="eyebrow mb-0">${requireNote?'GOVERNANCE DECISION':'REFRESH WORKSPACE'}</span><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div><h2 id="decision-title">${safe(title)}</h2><p>${description}</p><div class="review-detail-box"><strong>${safe(summary)}</strong><span style="color:#16a34a;font-weight:600;">[Live Enforcement] Executed live on payhive-eng GitHub organization with automated audit logging.</span></div>${requireNote?'<label class="field-label" for="review-note">Decision comment <span>(required)</span></label><textarea id="review-note" class="form-control review-note" required maxlength="500" aria-describedby="decision-note-help decision-note-error" placeholder="Explain the business reason for your decision…"></textarea><small id="decision-note-help">This comment is saved with the decision in audit history.</small><p id="decision-note-error" class="decision-error" role="alert"></p>':'<ul class="reset-effects"><li>Refresh all assignments directly from GitHub and live database.</li><li>Synchronize latest security findings and approval state.</li><li>Keep your light/dark theme preference.</li></ul><p class="decision-error">Locally recorded changes cannot be recovered after reset.</p>'}<div class="review-modal-actions"><button class="btn btn-outline" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" id="confirm-review">${safe(button)}</button></div>`;confirmAction=action;document.querySelector('#review-modal').dataset.requireNote=String(requireNote);document.querySelector('#review-modal').setAttribute('aria-labelledby','decision-title');bootstrap.Modal.getOrCreateInstance(document.querySelector('#review-modal')).show();}

function openReview(id,action){Governance.approve(id,action);}

function runAudit(){Governance.runAudit();}

function updateInput(key,value,id){state[key]=value;state.auditPage=1;state.historyPage=1;const input=document.getElementById(id),position=input.selectionStart;render();const next=document.getElementById(id);next.focus();next.setSelectionRange(position,position);}

function searchWorkspace(query){SearchPalette.query(query);}

document.addEventListener('input',e=>{const map={'audit-search':'auditQuery','approval-search':'approvalQuery','history-search':'historyQuery'};if(map[e.target.id])updateInput(map[e.target.id],e.target.value,e.target.id);if(e.target.id==='review-note'){e.target.removeAttribute('aria-invalid');document.querySelector('#decision-note-error').textContent='';}if(e.target.id==='global-search')searchWorkspace(e.target.value);});

document.addEventListener('change',e=>{
  if (e.target.id === 'req-duration-select') {
    const customBox = document.getElementById('custom-duration-container');
    if (customBox) customBox.style.display = e.target.value === 'custom' ? 'flex' : 'none';
  }const map={'risk-filter':'auditRisk','access-filter':'auditAccess','source-filter':'auditSource','user-filter':'auditUser','repo-filter':'auditRepo','action-filter':'auditAction','approval-filter':'approvalFilter','history-filter':'historyAction','history-range':'historyRange'};if(map[e.target.id]){state[map[e.target.id]]=e.target.value;state.auditPage=1;state.historyPage=1;render();}});

document.addEventListener('click',e=>{

 const b=e.target.closest('button,a,[data-page-link]');if(!b)return;

 if(b.matches('[data-retry-save]')){const ok=persist(StorageStatus.dirty);if(StorageStatus.themeFailed)Theme.apply(Theme.current,true);showToast(ok?'Workspace records saved to this browser.':'Saving is still unavailable. Keep this page open to retain session changes.');}

 if(b.matches('[data-retry-view]'))render();

 if(b.matches('[data-toast]'))showToast(b.dataset.toast);

 if(b.matches('[data-audit-segment]')){const seg=b.dataset.auditSegment;state.auditSegment=seg;state.auditPage=1;const targetHash=seg==='all'?'#audit':`#audit?segment=${encodeURIComponent(seg)}`;if(location.hash!==targetHash){location.hash=targetHash;return;}render();}if(b.matches('[data-page-link]'))location.hash=b.dataset.pageLink;

 if(b.id==='btn-trigger-auto-audit'){
    b.disabled = true;
    const origHtml = b.innerHTML;
    b.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" style="width:11px;height:11px;border-width:2px;margin-right:4px;"></span> Running…';
    (async () => {
      try {
        await ApiClient.triggerAutoAudit();
        const data = await ApiClient.bootstrap();
        ApiClient.syncState(data);
        if (window.AutomationTimer) await AutomationTimer.fetchStatus();
        if (window.NotificationsCenter) await NotificationsCenter.fetchNotifications();
        render();
        showToast("Automated IAM audit cycle completed successfully.");
      } catch (err) {
        showToast(err.message || "Could not execute automated audit.");
      } finally {
        b.disabled = false;
        b.innerHTML = origHtml;
      }
    })();
    return;
  }

  if(b.matches('[data-export]'))exportCsv(b.dataset.export);

 if(b.matches('[data-risk-person]'))location.hash='risk?'+encodeURIComponent(b.dataset.riskPerson);

 if(b.matches('[data-review]'))openReview(b.dataset.review,b.dataset.action);

 if(b.matches('[data-run-audit]')||b.id==='run-audit'){ /* manual audit button removed in Stage 1 */ }

 if(b.id==='clear-filters'){Object.assign(state,{auditSegment:'all',auditQuery:'',auditRisk:'All risks',auditAccess:'All access levels',auditSource:'All sources',auditUser:'All users',auditRepo:'All resources',auditAction:'All actions',auditPage:1});if(location.hash!=='#audit'){location.hash='#audit';return;}render();}

 if(b.matches('[data-pagination]')){state[b.dataset.pagination+'Page']+=Number(b.dataset.direction);render();}

 if(b.closest('#chart-period')){state.chartPeriod=b.textContent;render();}

 if(b.matches('[data-revoke]'))Governance.resolve(b.dataset.revoke,false,true);

 if(b.matches('[data-remediate],[data-dismiss]'))Governance.resolve(b.dataset.remediate||b.dataset.dismiss,b.hasAttribute('data-dismiss'),false);

 if(b.id==='confirm-review'&&confirmAction){const input=document.querySelector('#review-note'),note=input?.value.trim()||'';if(document.querySelector('#review-modal').dataset.requireNote==='true'&&!note){input.setAttribute('aria-invalid','true');document.querySelector('#decision-note-error').textContent='Add a decision comment before continuing.';input.focus();return;}const fn=confirmAction;confirmAction=null;b.disabled=true;fn(note);bootstrap.Modal.getInstance(document.querySelector('#review-modal')).hide();render();}

 if(b.matches('[data-reset-demo]'))openDecision('Refresh workspace data?','This refreshes all assignments, approvals, and history directly from GitHub and the live database.','payhive-eng','Refresh data',()=>ApiClient.loadAndRender(),false);

 if(b.matches('.show-password')){const input=document.querySelector('#password');input.type=input.type==='password'?'text':'password';b.textContent=input.type==='password'?'Show':'Hide';b.setAttribute('aria-label',`${b.textContent} password`);b.setAttribute('aria-pressed',String(input.type==='text'));}



  if(b.id==='tab-existing-user'||b.id==='tab-new-user'){
    const isNew = b.id==='tab-new-user';
    const tabExist = document.querySelector('#tab-existing-user');
    const tabNew = document.querySelector('#tab-new-user');
    const secExist = document.querySelector('#section-existing-user');
    const secNew = document.querySelector('#section-new-user');
    if(tabExist && tabNew && secExist && secNew){
      tabExist.style.background = isNew ? 'transparent' : '#ff4d1f';
      tabExist.style.color = isNew ? 'var(--text, #334155)' : '#fff';
      tabNew.style.background = isNew ? '#ff4d1f' : 'transparent';
      tabNew.style.color = isNew ? '#fff' : 'var(--text, #334155)';
      secExist.style.display = isNew ? 'none' : 'block';
      secNew.style.display = isNew ? 'block' : 'none';
    }
  }

 if(b.id==='btn-share-request-link'){
   const url = `${location.origin}/#request`;
   if(navigator.clipboard && navigator.clipboard.writeText){
     navigator.clipboard.writeText(url).then(()=>{
       showToast("📋 Public access request link copied! Share this link with friends or team: " + url);
     }).catch(()=>{
       prompt("Copy this public access request link:", url);
     });
   } else {
     prompt("Copy this public access request link:", url);
   }
   return;
 }

  if(b.id==='btn-open-request-modal' || b.id==='btn-open-onboard-modal'){
    const userSelect = document.querySelector('#req-user-select');
    const repoSelect = document.querySelector('#req-repo-select');
    if(userSelect && repoSelect){
      const usersMap = new Map();
      people.forEach(p => {
        if(p.email && !p.email.includes('@github.unmatched')) {
          usersMap.set(p.email, `${p.name} (${p.email})`);
        }
      });
      userSelect.innerHTML = Array.from(usersMap.entries()).map(([email, label]) => `<option value="${safe(email)}">${safe(label)}</option>`).join('');
      const repos = Array.from(new Set(people.map(p => p.repo).filter(Boolean))).sort();
      repoSelect.innerHTML = repos.map(r => `<option value="${safe(r)}">${safe(r)}</option>`).join('');
    }

    const detectedWrapper = document.querySelector('#req-detected-wrapper');
    const detectedSelect = document.querySelector('#req-detected-select');
    const unmapped = window.unmatchedGitHubAccounts || (window.GitHubSettings && window.GitHubSettings.unmatched) || [];
    if(detectedWrapper && detectedSelect){
      if(unmapped.length > 0){
        detectedWrapper.style.display = 'block';
        detectedSelect.innerHTML = '<option value="">-- Choose detected GitHub collaborator --</option>' +
          unmapped.map(u => `<option value="${safe(u.login)}">@${safe(u.login)} (${safe(Array.isArray(u.repos) && u.repos.length ? u.repos.join(', ') : 'Collaborator')})</option>`).join('');
      } else {
        detectedWrapper.style.display = 'none';
      }
    }

    bootstrap.Modal.getOrCreateInstance(document.querySelector('#request-modal')).show();
    return;
  }

  if(b.matches('[data-search-page],[data-search-history]')){bootstrap.Modal.getInstance(document.querySelector('#search-modal')).hide();if(b.dataset.searchHistory){state.historyQuery=b.dataset.searchHistory;state.historyPage=1;location.hash='history';render();}else location.hash=b.dataset.searchPage;}

 if(b.id==='search-open'){document.querySelector('#toast-container').replaceChildren();bootstrap.Modal.getOrCreateInstance(document.querySelector('#search-modal')).show();searchWorkspace(document.querySelector('#global-search').value);}

 if(b.id==='mobile-menu'){const sidebar=document.querySelector('#sidebar');sidebar.classList.toggle('mobile-open');b.setAttribute('aria-expanded',String(sidebar.classList.contains('mobile-open')));}

 if(b.id==='sidebar-collapse'){document.body.classList.toggle('collapsed');b.innerHTML=uiIcon(document.body.classList.contains('collapsed')?'chevronRight':'chevronLeft');b.setAttribute('aria-expanded',String(!document.body.classList.contains('collapsed')));b.setAttribute('aria-label',document.body.classList.contains('collapsed')?'Expand sidebar':'Collapse sidebar');}

 if(b.matches('a[data-page]')){document.querySelector('#sidebar').classList.remove('mobile-open');document.querySelector('#mobile-menu').setAttribute('aria-expanded','false');}

});

document.addEventListener('submit',async e=>{

  if(e.target.id === 'access-request-form'){

    e.preventDefault();

    const isNewTab = document.querySelector('#section-new-user')?.style.display !== 'none';

    const repo_name = document.querySelector('#req-repo-select')?.value;

    const access_level = document.querySelector('#req-access-select')?.value;

    const durSelect = document.querySelector('#req-duration-select');
    let duration_hours = null;
    if (durSelect && durSelect.value === 'custom') {
      const val = parseFloat(document.querySelector('#custom-duration-val')?.value || '0');
      const unit = document.querySelector('#custom-duration-unit')?.value || 'days';
      if (val > 0) {
        if (unit === 'hours') duration_hours = val;
        else if (unit === 'days') duration_hours = val * 24;
        else if (unit === 'months') duration_hours = val * 24 * 30;
      }
    } else {
      const duration_val = parseFloat(durSelect?.value || '0');
      duration_hours = duration_val > 0 ? duration_val : null;
    }

    const business_reason = document.querySelector('#req-reason-input')?.value.trim();

    if(!business_reason) return;



    let payload = { repo_name, access_level, duration_hours, business_reason };

    let displayName = "";



    if (isNewTab) {

      const github_login = document.querySelector('#req-github-input')?.value.trim().replace(/^@/, '');

      const name = document.querySelector('#req-new-name-input')?.value.trim();

      const email = document.querySelector('#req-new-email-input')?.value.trim();

      if (!github_login && !email) {

        showToast('Please provide a GitHub username or work email for the new employee.');

        return;

      }

      payload.github_login = github_login;

      payload.name = name || github_login;

      payload.email = email || (github_login ? `${github_login}@payhive.internal` : null);
      payload.type = 'New employee onboarding';

      displayName = `@${github_login || payload.email}`;

    } else {

      const email = document.querySelector('#req-user-select')?.value;

      payload.email = email;

      const personObj = people.find(p => p.email && p.email.toLowerCase() === (email || '').toLowerCase() && p.githubLogin);
      if (personObj && personObj.githubLogin) {
        payload.github_login = personObj.githubLogin;
      }

      displayName = personObj && personObj.githubLogin ? `@${personObj.githubLogin}` : email;

    }



    // Separation of Duties check for self-onboarding:
    const loggedInEmail = (window.FirebaseIdentity?.user?.email || '').trim().toLowerCase();
    const targetEmail = (payload.email || '').trim().toLowerCase();
    const targetGithub = (payload.github_login || '').trim().toLowerCase();
    if (loggedInEmail && (loggedInEmail === targetEmail || (targetGithub && loggedInEmail.split('@')[0] === targetGithub))) {
      showToast('Separation of Duties violation: administrators cannot directly onboard or grant repository permissions to themselves. Another administrator must review your request.');
      return;
    }

    const submitBtn = document.querySelector('#req-submit-btn');

    if(submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Provisioning on GitHub…';
    }

    try {

      await ApiClient.createAccessRequest(payload);

      const data = await ApiClient.bootstrap();

      ApiClient.syncState(data);

      bootstrap.Modal.getInstance(document.querySelector('#request-modal')).hide();

      document.querySelector('#access-request-form').reset();

      render();

      decisionFeedback(`Access granted & collaborator provisioned for ${displayName} on ${repo_name}${duration_hours ? ` (${duration_hours}h JIT)` : ''}!`);

    } catch(err) {

      showToast(err.message || 'Could not grant access.');

    } finally {

      if(submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Grant & Provision Access';
      }

    }

    return;

  }

  if(e.target.id === 'public-access-request-form'){
    e.preventDefault();
    const name = document.querySelector('#pub-name-input')?.value.trim();
    const email = document.querySelector('#pub-email-input')?.value.trim();
    const github_login = document.querySelector('#pub-github-input')?.value.trim().replace(/^@/, '');
    const repo_name = document.querySelector('#pub-repo-select')?.value;
    const access_level = document.querySelector('#pub-access-select')?.value;
    const duration_val = parseFloat(document.querySelector('#pub-duration-select')?.value || '0');
    const duration_hours = duration_val > 0 ? duration_val : null;
    const business_reason = document.querySelector('#pub-reason-input')?.value.trim();

    if(!github_login || !business_reason) return;

    const submitBtn = document.querySelector('#pub-submit-btn');
    if(submitBtn){
      submitBtn.disabled = true;
      submitBtn.textContent = 'Submitting…';
    }

    try {
      await ApiClient.createPublicRequest({
        name,
        email,
        github_login,
        repo_name,
        access_level,
        duration_hours,
        business_reason,
        type: 'Public self-service request',
      });

      const card = document.querySelector('#public-request-card');
      if(card){
        card.innerHTML = `
          <div style="text-align:center;padding:24px 12px;">
            <div style="display:inline-flex;align-items:center;justify-content:center;width:56px;height:56px;border-radius:50%;background:#dcfce7;color:#16a34a;margin-bottom:16px;">
              ${uiIcon('check', 30)}
            </div>
            <h3 style="font-size:20px;font-weight:800;margin-bottom:8px;color:#15803d;">Access Request Submitted!</h3>
            <p style="font-size:14px;color:var(--text,#334155);margin-bottom:16px;line-height:1.5;">
              Your request for <strong>${safe(access_level)}</strong> access to <strong>${safe(repo_name)}</strong> on behalf of <code>@${safe(github_login)}</code> has been submitted.
            </p>
            <div style="background:var(--bg-subtle,#f8fafc);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;font-size:12.5px;color:var(--muted,#64748b);margin-bottom:20px;text-align:left;">
              <div><strong>Requester:</strong> ${safe(name)} (${safe(email)})</div>
              <div><strong>Target Account:</strong> @${safe(github_login)}</div>
              <div><strong>Status:</strong> <span class="badge" style="background:#fef3c7;color:#92400e;font-weight:700;">Pending Administrator Review</span></div>
            </div>
            <p style="font-size:12px;color:var(--muted,#64748b);margin-bottom:20px;">
              Our security administrators have received a live alert. Once approved, collaborator permissions will be automatically applied to your GitHub account.
            </p>
            <button type="button" class="btn btn-outline btn-sm" onclick="location.reload()">Submit Another Request</button>
          </div>
        `;
      }
      if(typeof showToast === 'function') showToast('Access request submitted successfully!');
    } catch(err) {
      if(submitBtn){
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Access Request →';
      }
      if(typeof showToast === 'function') showToast(err.message || 'Could not submit access request.');
    }
    return;
  }

  if(e.target.id!=='auth-form')return;

  e.preventDefault();

  FirebaseUI.submit(e.target);

});

document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!document.querySelector('#app').classList.contains('d-none')){e.preventDefault();document.querySelector('#search-open').click();}if(e.key==='Escape'){document.querySelector('#sidebar').classList.remove('mobile-open');document.querySelector('#mobile-menu').setAttribute('aria-expanded','false');}SearchPalette.key(e);});

document.querySelector('#search-modal').addEventListener('shown.bs.modal',()=>document.querySelector('#global-search').focus());

window.addEventListener('hashchange',()=>{document.querySelector('#sidebar').classList.remove('mobile-open');document.querySelector('#mobile-menu').setAttribute('aria-expanded','false');render();window.scrollTo(0,0);});

Governance.initialize();

if(!location.hash)historyReplaceLogin();else render();

FirebaseUI.start();

if(window.ApiClient){

  ApiClient.loadAndRender();

}

document.addEventListener('identity-changed',()=>{

  if(window.FirebaseIdentity?.authorized&&window.ApiClient){

    ApiClient.loadAndRender();

    if(window.UsersPage)UsersPage.fetchUsers();

    if(window.RulesSettings)RulesSettings.init();

    if(window.ScheduleSettings)ScheduleSettings.init();

  }else if(!window.FirebaseIdentity?.authorized&&window.ApiClient){

    ApiClient.loaded=false;

  }

});

function historyReplaceLogin(){window.history.replaceState(null,'','#login');render();}







function auditResultsStrip(){return AuditSummary.card(auditRuns.at(-1),auditing);}




document.addEventListener('change', e => {
  if (e.target && e.target.id === 'req-detected-select') {
    const val = e.target.value;
    if (val) {
      const ghInput = document.querySelector('#req-github-input');
      const nameInput = document.querySelector('#req-new-name-input');
      const emailInput = document.querySelector('#req-new-email-input');
      if (ghInput) ghInput.value = val;
      if (nameInput && !nameInput.value) nameInput.value = val;
      if (emailInput && !emailInput.value) emailInput.value = `${val}@payhive.internal`;
    }
  }
});
