import re

print("=== UPDATING APP.JS & GOVERNANCE.JS ===")

# --- 1. frontend/app.js ---
app_path = r"D:\AccessReaper-v2\frontend\app.js"
with open(app_path, "r", encoding="utf-8") as f:
    app_code = f.read()

# Replace approvalsPage function
old_approvals_snippet = """function approvalsPage(){const filtered=approvals.filter(a=>(state.approvalFilter==='All requests'||a.status===state.approvalFilter)&&(`${a.person} ${a.repo} ${a.id} ${a.reason}`).toLowerCase().includes(state.approvalQuery.toLowerCase()));return `<div class="approvals-workbench">${pageHeading('Approvals','Review and manage repository access requests for payhive-eng.',`<button class="btn btn-primary" id="btn-open-request-modal">+ Request Access</button>`)}<section class="card request-metrics" aria-label="Request totals">${[['Pending','Awaiting review'],['Approved','Approved'],['Declined','Rejected']].map(([status,label])=>`<div><span>${label}</span><strong>${approvals.filter(a=>a.status===status).length}</strong></div>`).join('')}<div class="request-risk"><span>High-risk pending</span><strong>${approvals.filter(a=>a.status==='Pending'&&a.risk==='High').length}</strong></div></section><section class="request-queue"><div class="queue-heading"><div><span class="section-eyebrow">DECISION QUEUE</span><h2>${state.approvalFilter==='All requests'?'All requests':statusLabel(state.approvalFilter)+' requests'} <span>${filtered.length}</span></h2></div><p>Review the business reason before deciding. Approving grants permissions live on GitHub and emails the user.</p></div><div class="card queue-tools">${auditSearch('approval-search',state.approvalQuery,'Search requests or people…')}<label class="queue-status" for="approval-filter"><span>Request status</span>${selectControl('approval-filter','Request status',['Pending','Approved','Declined','All requests'],state.approvalFilter)}</label></div><div class="request-list">${filtered.length?filtered.map(a=>`<article class="card approval-card"><div class="approval-card-top"><div class="approval-kind">${a.type==='Role change'?'↻':a.type==='Access removal'?'−':'+'}</div><div style="flex:1"><h3>${safe(a.type)} · ${safe(a.repo)}${a.durationHours?` <span class="badge" style="background:#fefce8;color:#854d0e;border:1px solid #fef08a;font-size:11px;padding:2px 6px;border-radius:4px;font-weight:700;">⏱️ ${a.durationHours}h JIT Lease</span>`:''}</h3><p>${safe(a.id)} &nbsp;·&nbsp; ${safe(a.person)} <span class="request-email">${safe(a.email)}</span> &nbsp;·&nbsp; ${Governance.relativeMarkup(a.requestedAt,a.requested)}</p></div>${badge(a.status)}</div><div class="approval-info"><div><span>Current → requested access</span><strong><span class="request-current">${safe(people.find(p=>p.email===a.email&&p.repo===a.repo)?.access||'None')} → </span><span class="access-badge ${a.access==='Admin'?'admin':''}">${safe(a.access)}</span></strong></div><div><span>Request risk</span><strong>${riskPill(a.risk)}</strong></div><div><span>Business reason</span><strong>${safe(a.reason)}</strong></div></div>${a.status==='Pending'?`<div class="approval-actions"><button class="btn btn-outline btn-sm" data-review="${safe(a.id)}" data-action="Declined">Reject</button><button class="btn btn-primary btn-sm" data-review="${safe(a.id)}" data-action="Approved">Approve request</button></div>`:''}</article>`).join(''):'<div class="card empty-state">◷<strong>No requests in this view</strong>Try selecting another request status.</div>'}</div></section></div>`}"""

new_approvals_snippet = """function approvalsPage(){
  const filtered=approvals.filter(a=>(state.approvalFilter==='All requests'||a.status===state.approvalFilter)&&(`${a.person} ${a.repo} ${a.id} ${a.reason} ${a.githubLogin||''}`).toLowerCase().includes(state.approvalQuery.toLowerCase()));
  return `<div class="approvals-workbench">${pageHeading('Approvals','Review and manage repository access requests for payhive-eng.',`<button class="btn btn-primary" id="btn-open-request-modal">+ Request Access</button>`)}
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
      const isNewEmployee = a.isNewEmployee || (a.email && a.email.endsWith('@payhive.internal')) || (a.email && a.email.endsWith('@github.unmatched')) || (a.githubLogin && !people.some(p => p.email === a.email && p.source === 'GitHub'));
      const ghTag = a.githubLogin ? `@${a.githubLogin}` : (a.email.includes('@github.unmatched') ? `@${a.email.split('@')[0]}` : '');
      return `<article class="card approval-card" style="${isNewEmployee && a.status === 'Pending' ? 'border-left: 4px solid #ff4d1f;' : ''}">
        ${isNewEmployee ? `<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
          <span class="badge" style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;font-size:11px;padding:3px 8px;border-radius:6px;font-weight:700;">⚡ NEW EMPLOYEE ONBOARDING</span>
          ${ghTag ? `<span class="badge" style="background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;font-size:11px;padding:3px 8px;font-family:monospace;font-weight:600;">${safe(ghTag)}</span>` : ''}
        </div>` : ''}
        <div class="approval-card-top">
          <div class="approval-kind">${a.type==='Role change'?'↻':a.type==='Access removal'?'−':'+'}</div>
          <div style="flex:1">
            <h3>${safe(a.type)} · ${safe(a.repo)}${a.durationHours?` <span class="badge" style="background:#fefce8;color:#854d0e;border:1px solid #fef08a;font-size:11px;padding:2px 6px;border-radius:4px;font-weight:700;">⏱️ ${a.durationHours}h JIT Lease</span>`:''}</h3>
            <p>${safe(a.id)} &nbsp;·&nbsp; <strong>${safe(a.person)}</strong> ${ghTag ? `(${safe(ghTag)})` : ''} <span class="request-email">${safe(a.email)}</span> &nbsp;·&nbsp; ${Governance.relativeMarkup(a.requestedAt,a.requested)}</p>
          </div>
          ${badge(a.status)}
        </div>
        ${isNewEmployee && a.status === 'Pending' ? `
          <div style="background:#fffbeb;border:1px solid #fef3c7;border-radius:6px;padding:8px 12px;margin:10px 0;font-size:12px;color:#92400e;line-height:1.4;">
            <strong>⚡ Directory Conflict Detected:</strong> <code>${safe(ghTag || a.person)}</code> is requesting access to <strong>${safe(a.repo)}</strong>, but is not yet registered in your directory. Approving will automatically provision their employee identity in <strong>payhive-eng</strong>, map their GitHub account, grant collaborator permissions live on GitHub, and dispatch a welcome email.
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
          <button class="btn btn-outline btn-sm" data-review="${safe(a.id)}" data-action="Declined">Reject</button>
          <button class="btn btn-primary btn-sm" data-review="${safe(a.id)}" data-action="Approved" style="${isNewEmployee ? 'background:#16a34a;border-color:#16a34a;font-weight:700;' : ''}">
            ${isNewEmployee ? '✓ Approve & Onboard to GitHub' : 'Approve request'}
          </button>
        </div>`:''}
      </article>`;
    }).join(''):'<div class="card empty-state">◷<strong>No requests in this view</strong>Try selecting another request status.</div>'}</div>
  </section></div>`
}"""

norm_app = app_code.replace("\r\n", "\n")
norm_old_app = old_approvals_snippet.replace("\r\n", "\n")
norm_new_app = new_approvals_snippet.replace("\r\n", "\n")

if norm_old_app in norm_app:
    norm_app = norm_app.replace(norm_old_app, norm_new_app)
    print("SUCCESS: approvalsPage updated in app.js")
else:
    print("WARNING: approvalsPage target snippet not found, using regex...")
    pattern = re.compile(r"function approvalsPage\(\)\{.*?return `<div class=\"approvals-workbench\">.*?<\/section><\/div>`\s*\}", re.DOTALL)
    norm_app = pattern.sub(norm_new_app, norm_app)

# Replace modal opener and form submit handlers
old_modal_handler = """  if(b.id==='btn-open-request-modal'){
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
    bootstrap.Modal.getOrCreateInstance(document.querySelector('#request-modal')).show();
  }"""

new_modal_handler = """  if(b.id==='btn-open-request-modal'){
    const userSelect = document.querySelector('#req-user-select');
    const repoSelect = document.querySelector('#req-repo-select');
    const detectedSelect = document.querySelector('#req-detected-select');
    const detectedWrapper = document.querySelector('#req-detected-wrapper');

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

      // Wire detected unmatched accounts
      const unmapped = window.unmatchedGitHubAccounts || [];
      if(detectedSelect && detectedWrapper) {
        if(unmapped.length > 0) {
          detectedWrapper.style.display = 'block';
          detectedSelect.innerHTML = '<option value="">-- Or choose detected GitHub collaborator --</option>' +
            unmapped.map(u => `<option value="${safe(u.login)}">@${safe(u.login)} (${u.assignments_count || 0} active repos)</option>`).join('');
          detectedSelect.onchange = () => {
            if(detectedSelect.value) {
              const ghInput = document.querySelector('#req-github-input');
              if(ghInput) ghInput.value = detectedSelect.value;
            }
          };
        } else {
          detectedWrapper.style.display = 'none';
        }
      }

      // Wire tab switching
      const tabExisting = document.querySelector('#tab-existing-user');
      const tabNew = document.querySelector('#tab-new-user');
      const secExisting = document.querySelector('#section-existing-user');
      const secNew = document.querySelector('#section-new-user');

      if(tabExisting && tabNew && secExisting && secNew) {
        tabExisting.onclick = () => {
          secExisting.style.display = 'block';
          secNew.style.display = 'none';
          tabExisting.style.background = '#ff4d1f';
          tabExisting.style.color = '#fff';
          tabNew.style.background = 'transparent';
          tabNew.style.color = 'var(--text, #334155)';
        };
        tabNew.onclick = () => {
          secExisting.style.display = 'none';
          secNew.style.display = 'block';
          tabNew.style.background = '#ff4d1f';
          tabNew.style.color = '#fff';
          tabExisting.style.background = 'transparent';
          tabExisting.style.color = 'var(--text, #334155)';
        };
      }
    }
    bootstrap.Modal.getOrCreateInstance(document.querySelector('#request-modal')).show();
  }"""

norm_old_modal = old_modal_handler.replace("\r\n", "\n")
norm_new_modal = new_modal_handler.replace("\r\n", "\n")

if norm_old_modal in norm_app:
    norm_app = norm_app.replace(norm_old_modal, norm_new_modal)
    print("SUCCESS: modal opener updated in app.js")
else:
    print("WARNING: modal opener snippet not matched directly")

# Update form submit handler
old_submit_handler = """  if(e.target.id === 'access-request-form'){
    e.preventDefault();
    const email = document.querySelector('#req-user-select')?.value;
    const repo_name = document.querySelector('#req-repo-select')?.value;
    const access_level = document.querySelector('#req-access-select')?.value;
    const duration_val = parseInt(document.querySelector('#req-duration-select')?.value || '0', 10);
    const duration_hours = duration_val > 0 ? duration_val : null;
    const business_reason = document.querySelector('#req-reason-input')?.value.trim();
    if(!business_reason) return;
    const submitBtn = document.querySelector('#req-submit-btn');
    if(submitBtn) submitBtn.disabled = true;
    try {
      await ApiClient.createAccessRequest({ email, repo_name, access_level, duration_hours, business_reason });
      const data = await ApiClient.bootstrap();
      ApiClient.syncState(data);
      bootstrap.Modal.getInstance(document.querySelector('#request-modal')).hide();
      document.querySelector('#access-request-form').reset();
      render();
      decisionFeedback(`Access request submitted for ${email} on ${repo_name}${duration_hours ? ` (${duration_hours}h JIT)` : ''}.`);
    } catch(err) {
      showToast(err.message || 'Could not submit access request.');
    } finally {
      if(submitBtn) submitBtn.disabled = false;
    }
    return;
  }"""

new_submit_handler = """  if(e.target.id === 'access-request-form'){
    e.preventDefault();
    const isNewTab = document.querySelector('#section-new-user')?.style.display !== 'none';
    const repo_name = document.querySelector('#req-repo-select')?.value;
    const access_level = document.querySelector('#req-access-select')?.value;
    const duration_val = parseInt(document.querySelector('#req-duration-select')?.value || '0', 10);
    const duration_hours = duration_val > 0 ? duration_val : null;
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
      displayName = `@${github_login || payload.email}`;
    } else {
      const email = document.querySelector('#req-user-select')?.value;
      payload.email = email;
      displayName = email;
    }

    const submitBtn = document.querySelector('#req-submit-btn');
    if(submitBtn) submitBtn.disabled = true;
    try {
      await ApiClient.createAccessRequest(payload);
      const data = await ApiClient.bootstrap();
      ApiClient.syncState(data);
      bootstrap.Modal.getInstance(document.querySelector('#request-modal')).hide();
      document.querySelector('#access-request-form').reset();
      render();
      decisionFeedback(`Access request submitted for ${displayName} on ${repo_name}${duration_hours ? ` (${duration_hours}h JIT)` : ''}.`);
    } catch(err) {
      showToast(err.message || 'Could not submit access request.');
    } finally {
      if(submitBtn) submitBtn.disabled = false;
    }
    return;
  }"""

norm_old_submit = old_submit_handler.replace("\r\n", "\n")
norm_new_submit = new_submit_handler.replace("\r\n", "\n")

if norm_old_submit in norm_app:
    norm_app = norm_app.replace(norm_old_submit, norm_new_submit)
    print("SUCCESS: submit handler updated in app.js")
else:
    print("WARNING: submit handler snippet not matched directly")

with open(app_path, "w", encoding="utf-8") as f:
    f.write(norm_app.replace("\n", "\r\n"))
print("Saved app.js successfully!")

# --- 2. frontend/governance.js ---
gov_path = r"D:\AccessReaper-v2\frontend\governance.js"
with open(gov_path, "r", encoding="utf-8") as f:
    gov_code = f.read()

old_gov_approve = """  approve(id,action){const a=approvals.find(a=>a.id===id);if(!a||a.status!=='Pending')return;openDecision(action==='Approved'?'Approve this access request?':'Reject this access request?',`Business reason: ${a.reason}. ${action==='Approved'?`Grant ${a.access} permissions on GitHub to ${a.person} and dispatch notification email.`:`Decline access request and dispatch notification email to ${a.person}.`}`,`${a.person} · ${a.repo} · ${people.find(p=>p.email===a.email&&p.repo===a.repo)?.access||'None'} → ${a.type==='Access removal'?'None':a.access}`,action==='Approved'?'Approve request':'Reject request',async note=>{if(a.status!=='Pending')return;if(window.ApiClient&&!window.ApiClient.isDemoMode){try{await ApiClient.decideApproval(a.id,action,note);const data=await ApiClient.bootstrap();ApiClient.syncState(data);render();decisionFeedback(action==='Approved'?`Access request approved: granted on GitHub and notice email sent to ${a.email}.`:`Access request rejected: notice email sent to ${a.email}.`);return;}catch(err){showToast(err.message||'Failed to process request.');return;}}a.status=action;let p=people.find(p=>p.email===a.email&&p.repo===a.repo),before=p?.access||'None',after=before;if(action==='Approved'){after=a.type==='Access removal'?'None':a.access;if(!p&&after!=='None'){const owner=people.find(p=>p.email===a.email);p={name:a.person,email:a.email,initials:a.initials,role:owner?.role||'Team member',team:owner?.team||'Engineering',repo:a.repo,source:'GitHub',access:after,risk:after==='Admin'?'High':'Low',last:'Just now',reason:after==='Admin'?'Approved elevated access requires periodic review':'Access matches approved request',id:'FND-'+(Math.max(2840,...people.map(p=>Number(p.id.slice(4))))+1),resolved:false};people.push(p);this.normalize(p);}if(p){p.access=after;if(after==='Admin'&&before!=='Admin'){p.resolved=false;p.risk='High';p.finding.status='Open';}if(after!=='Admin'&&this.isOpen(p)){p.resolved=true;p.finding.status='Approved change';}p.reviewedAt=this.date(new Date().toISOString());}}this.record({title:`Access request ${action==='Declined'?'rejected':'approved'}`,tag:action,source:p?.source||'GitHub',assignmentId:p?.id||'',requestId:a.id,before,after,detail:`${a.person} · ${a.repo}`,note,tone:action==='Approved'?'green':'gray'});decisionFeedback(`Request ${action==='Declined'?'rejected':'approved'}; comment saved.`);});},"""

new_gov_approve = """  approve(id,action){
    const a=approvals.find(a=>a.id===id);if(!a||a.status!=='Pending')return;
    const isNewEmployee = a.isNewEmployee || (a.email && a.email.endsWith('@payhive.internal')) || (a.email && a.email.endsWith('@github.unmatched'));
    const ghTag = a.githubLogin ? `@${a.githubLogin}` : (a.email.includes('@github.unmatched') ? `@${a.email.split('@')[0]}` : '');
    const modalTitle = action==='Approved' 
      ? (isNewEmployee ? `Approve & Onboard ${a.person} to GitHub?` : `Approve access for ${a.person}?`) 
      : `Reject access request for ${a.person}?`;
    const modalBody = action==='Approved'
      ? (isNewEmployee 
          ? `⚡ <strong>New Employee Onboarding:</strong> Approving will automatically provision <strong>${safe(a.person)}</strong> as an employee in payhive-eng, map GitHub account <code>${safe(ghTag || a.person)}</code>, grant <strong>${safe(a.access)}</strong> access live on GitHub repository <strong>${safe(a.repo)}</strong>, and dispatch an automated welcome notice email.`
          : `Business reason: ${a.reason}. Grant <strong>${safe(a.access)}</strong> access on GitHub to <strong>${safe(a.person)}</strong> and dispatch notification email.`)
      : `Decline access request for <strong>${safe(a.person)}</strong> and dispatch notification email.`;
    const btnText = action==='Approved' ? (isNewEmployee ? '✓ Onboard & Grant Access' : 'Approve request') : 'Reject request';
    
    openDecision(modalTitle, modalBody, `${a.person} ${ghTag ? `(${ghTag})` : ''} · ${a.repo} · ${people.find(p=>p.email===a.email&&p.repo===a.repo)?.access||'None'} → ${a.type==='Access removal'?'None':a.access}`, btnText, async note=>{
      if(a.status!=='Pending')return;
      if(window.ApiClient&&!window.ApiClient.isDemoMode){
        try{
          await ApiClient.decideApproval(a.id,action,note);
          const data=await ApiClient.bootstrap();
          ApiClient.syncState(data);
          render();
          decisionFeedback(action==='Approved'
            ? (isNewEmployee ? `Onboarding complete: ${a.person} registered, granted on GitHub, and welcome email sent.` : `Access request approved: granted on GitHub and notice email sent to ${a.email}.`)
            : `Access request rejected: notice email sent to ${a.email}.`);
          return;
        }catch(err){
          showToast(err.message||'Failed to process request.');
          return;
        }
      }
      a.status=action;
      render();
      decisionFeedback(`Request ${action==='Declined'?'rejected':'approved'}; comment saved.`);
    });
  },"""

norm_gov = gov_code.replace("\r\n", "\n")
norm_old_gov = old_gov_approve.replace("\r\n", "\n")
norm_new_gov = new_gov_approve.replace("\r\n", "\n")

if norm_old_gov in norm_gov:
    norm_gov = norm_gov.replace(norm_old_gov, norm_new_gov)
    print("SUCCESS: Governance.approve updated in governance.js")
else:
    print("WARNING: Governance.approve target not matched directly, using regex...")
    pattern_gov = re.compile(r"approve\(id,action\)\{.*?decisionFeedback\(`Request \${action==='Declined'\?'rejected':'approved'}.*?\}\);\},", re.DOTALL)
    norm_gov = pattern_gov.sub(norm_new_gov, norm_gov)

with open(gov_path, "w", encoding="utf-8") as f:
    f.write(norm_gov.replace("\n", "\r\n"))
print("Saved governance.js successfully!")
