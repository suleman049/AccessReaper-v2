// Shared audit and decision records connected to live GitHub organization.

let auditRuns=[];

let auditSnapshots=[];

let governanceBaseline;

const Governance={

  actor(){return FirebaseIdentity.profile?.name||FirebaseIdentity.user?.displayName||FirebaseIdentity.user?.email||'AccessReaper';},

  isOpen:p=>!p.resolved&&p.risk!=='Low',

  stats(){const open=people.filter(this.isOpen);return {identities:new Set(people.map(p=>p.email)).size,assignments:people.length,github:people.filter(p=>p.source==='GitHub'),firestore:[],high:open.filter(p=>p.risk==='High').length,medium:open.filter(p=>p.risk==='Medium').length,healthy:people.filter(p=>p.risk==='Low'&&!p.resolved).length,resolved:people.filter(p=>p.resolved&&p.finding?.originalSeverity!=='Low').length,pending:approvals.filter(a=>a.status==='Pending').length};},

  initialize(){

    governanceBaseline=JSON.parse(initialStore);

    for(const p of people){p.lastActiveAt??=this.fixtureTime(p.last);this.normalize(p);}

    for(const a of approvals)a.requestedAt??=this.fixtureTime(a.requested);

    // Repair only the original contradictory pending fixtures; keep recorded decisions intact.

    for(const a of approvals){if(a.status==='Pending'&&a.access==='Admin'&&((a.id==='REQ-1042'&&a.reason==='On-call infrastructure coverage')||(a.id==='REQ-1038'&&a.reason==='Mobile release support'))){a.access='Write';a.type='Role change';a.reason=a.id==='REQ-1042'?'Replace direct administrator access with repository write access for on-call coverage':'Limit contractor access to repository write permissions for mobile release support';}}

    history.forEach((e,i)=>{e.id??='EVT-'+i;e.actor??='Security Admin';e.note??='';e.changes??=[];e.occurredAt??=this.timestamp(e);const assignment=people.find(p=>e.detail.includes(p.name)&&e.detail.includes(p.repo));if(assignment){e.assignmentId??=assignment.id;e.source??=assignment.source;}else if(!e.source){if(/GitHub.*Firestore/.test(e.detail))e.source='GitHub + Firestore';else if(e.false)e.source='Firestore';else if(e.detail.includes('payhive-eng/'))e.source='GitHub';}const request=approvals.find(a=>e.detail.includes(a.person)&&e.detail.includes(a.repo));if(request&&['Request','Approved','Declined'].includes(e.tag))e.requestId??=request.id;});

    // No fake audit run injection

    const initialAudit=history.find(e=>e.title==='Quarterly access audit completed');if(initialAudit&&!initialAudit.auditId)initialAudit.auditId=auditRuns.find(r=>Date.parse(r.completedAt)===Date.parse(initialAudit.occurredAt))?.id||'';

    // No fake snapshot injection

    persist(false);

  },

  normalize(p){

    const seed=governanceBaseline?.people.find(x=>x.id===p.id);

    if(!p.finding){p.finding={id:p.id,originalReason:seed?.reason||p.reason,originalSeverity:seed?.risk||p.risk,originalAccess:seed?.access||p.access,detectedAt:'2026-10-14T09:42:00+05:00',status:p.resolved?'Reviewed':p.risk==='Low'?'Healthy':'Open'};p.reason=p.finding.originalReason;p.risk=p.finding.originalSeverity;}

    p.finding.snapshot??={role:seed?.role||p.role,team:seed?.team||p.team,source:seed?.source||p.source,lastActiveAt:seed?this.fixtureTime(seed.last):p.lastActiveAt||null,lastActivity:seed?.last||p.last};

    p.finding.status??=p.resolved?'Reviewed':p.risk==='Low'?'Healthy':'Open';

    p.finding.evidence??=[`Assignment: ${p.finding.originalAccess} on ${p.repo} (${p.source}).`,`Identity: ${p.role}, ${p.team}; ${p.team==='Former employee'?'employment ended':p.team==='External'?'external contractor':'active employee'}.`,`Last recorded resource activity: ${p.last}.`];

  },

  fixtureTime(value){const anchor=Date.parse('2026-10-14T10:30:00+05:00'),text=String(value||'');let match=text.match(/^(\d+) (min|hour|day)s? ago$/);if(match)return new Date(anchor-Number(match[1])*({min:60000,hour:3600000,day:86400000}[match[2]])).toISOString();if(text==='Yesterday')return '2026-10-13T10:30:00+05:00';if(text==='Today')return '2026-10-14T09:00:00+05:00';match=text.match(/^Oct (\d+)$/);return match?`2026-10-${match[1].padStart(2,'0')}T10:30:00+05:00`:null;},

  relative(at,now=Date.now()){const elapsed=now-Date.parse(at);if(!Number.isFinite(elapsed))return 'Not recorded';if(elapsed<0)return this.date(at);const minutes=Math.floor(elapsed/60000);if(minutes<1)return 'Just now';if(minutes<60)return `${minutes} min ago`;const hours=Math.floor(minutes/60);if(hours<24)return `${hours} hour${hours===1?'':'s'} ago`;const days=Math.floor(hours/24);return `${days} day${days===1?'':'s'} ago`;},

  relativeMarkup(at,fallback='Not recorded'){return at?`<time data-relative-at="${safe(at)}" datetime="${safe(at)}" title="${safe(this.date(at))} (Karachi)">${this.relative(at)}</time>`:safe(fallback);},

  timestamp(e){if(e.occurredAt)return e.occurredAt;const match=String(e.time).match(/(\d+):(\d+)\s*(AM|PM)/i);let hour=match?Number(match[1])%12+(match[3].toUpperCase()==='PM'?12:0):0;return `${e.date||'2026-10-14'}T${String(hour).padStart(2,'0')}:${match?match[2]:'00'}:00+05:00`;},

  orderedEvents(){return [...history].sort((a,b)=>Date.parse(this.timestamp(b))-Date.parse(this.timestamp(a)));},

  record({title,tag,source='',assignmentId='',requestId='',before=null,after=null,detail='',note='',tone='gray',auditId=''}){

    const n=nowParts(),occurredAt=new Date().toISOString();

    const e={id:'EVT-'+Date.now()+'-'+Math.random().toString(36).slice(2,7),day:n.date,date:n.date,time:n.time,occurredAt,actor:this.actor(),mode:'LIVE_GITHUB',title,tag,source,assignmentId,requestId,auditId,detail,note,before,after,changes:before!==null&&after!==null?[{field:'Permission',before,after}]:[],tone,icon:tone==='green'?'✓':tag==='Audit'?'↻':'−'};

    history.unshift(e);this.snapshot(title,occurredAt);persist();return e;

  },

  snapshot(label,at=new Date().toISOString()){const s=this.stats();auditSnapshots.push({at,label,high:s.high,medium:s.medium,healthy:s.healthy,resolved:s.resolved,assignments:s.assignments,remediated:history.filter(e=>e.tag==='Remediated').length});},

  summary(){const s=this.stats();return {assignments:s.assignments,identities:s.identities,high:s.high,medium:s.medium,healthy:s.healthy,resolved:s.resolved,sources:[{source:'GitHub',assignments:people.length,resources:new Set(people.map(p=>p.repo)).size}]};},

  date(at){return new Date(at).toLocaleString('en-US',{timeZone:'Asia/Karachi',month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit'});},

  actionLabel(p){return p.resolved?'Reviewed':!this.isOpen(p)?'Keep access':this.target(p)==='None'?'Revoke access':'Reduce access';},

  target(p){return p.team==='Former employee'?'None':'Read';},

  recommendation(p){

    const target=this.target(p),reason=p.finding.originalReason;

    if(!this.isOpen(p))return {title:p.resolved?'Decision recorded':'Keep current access',body:p.resolved?`The original finding is preserved above. Current access is ${p.access}; outcome: ${p.finding.status}.`:'The policy check found no mismatch with the recorded responsibilities.',target:p.access,outcome:'No permission change required.'};

    let justification=p.finding?.aiRecommendation || (p.team==='Former employee'?'Employment has ended; the assignment should not remain active.':p.team==='External'?'External contractor access should be limited to the documented engagement.':reason.includes('unused')||reason.includes('activity')?'The recorded inactivity indicates elevated access may no longer be needed.':`The assignment conflicts with the recorded role or permission policy: ${reason.toLowerCase()}.`);

    return {title:target==='None'?'Revoke the former employee’s access':`Reduce ${p.access} to ${target}`,body:justification+' Confirm the business need with the resource owner before proceeding.',target,outcome:target==='None'?'Remove this resource assignment; the finding will be marked Remediated.':`Retain ${target.toLowerCase()} visibility and remove elevated privileges; the finding will be marked Remediated.`};

  },

  detail(route){const p=people.find(p=>p.id===route||p.email===route);if(!p)return pageHeading('Finding not found','This assignment does not exist.','<a class="btn btn-outline" href="#audit">Back to audit</a>');const f=p.finding,r=this.recommendation(p),events=this.orderedEvents().filter(e=>e.assignmentId===p.id),related=approvals.filter(a=>a.email===p.email&&a.repo===p.repo);

    return `${pageHeading('Risk details','Evidence, original permissions, and the complete decision record.',`<button class="btn btn-outline" data-page-link="audit">← Back to audit</button>`)}<div class="detail-grid"><div class="detail-main"><section class="risk-hero"><div class="risk-hero-top"><span class="finding-state" data-outcome="${this.isOpen(p)?'open':'closed'}">${safe(f.status)}</span><span class="original-severity">Original risk ${riskPill(f.originalSeverity)}</span><span class="risk-id">${safe(p.id)}</span></div><h2>${safe(f.originalReason)}</h2><p>${safe(p.name)} · ${safe(p.repo)}. Original permission: <strong>${safe(f.originalAccess)}</strong>. Current permission: <strong>${safe(p.access)}</strong>.</p><div class="hero-meta"><span>Identity<strong>${safe(p.name)}</strong></span><span>Team<strong>${safe(p.team)}</strong></span><span>Recorded<strong>${this.date(f.detectedAt)}</strong></span><span>Source<strong>${safe(p.source)}</strong></span></div></section><section class="card detail-panel current-assignment-state"><div class="current-state-heading"><h3>Current assignment</h3><span>Live Enforced (payhive-eng)</span></div><dl class="current-state-grid"><div><dt>Permission now</dt><dd>${safe(p.access)}</dd></div><div><dt>Current review state</dt><dd>${safe(f.status)}</dd></div><div><dt>Current risk</dt><dd>${p.resolved?'Reviewed · '+safe(f.status):riskPill(p.risk)}</dd></div><div><dt>Next step</dt><dd>${safe(this.actionLabel(p))}</dd></div></dl><p>${p.reviewedAt?'Last reviewed: '+safe(p.reviewedAt)+'. ':'No decision recorded yet. '}Original evidence below and completed audit reports remain historical snapshots.</p></section>

    <section class="card detail-panel"><h3>Original evidence snapshot</h3><p class="snapshot-caption">Recorded context behind this finding. Original evidence remains preserved after review.</p><dl class="evidence-snapshot"><div><dt>Role / team</dt><dd>${safe(f.snapshot.role)} · ${safe(f.snapshot.team)}</dd></div><div><dt>Original permission</dt><dd>${safe(f.originalAccess)}</dd></div><div><dt>Source</dt><dd>${safe(f.snapshot.source)}</dd></div><div><dt>Recorded last activity</dt><dd>${f.snapshot.lastActiveAt?this.date(f.snapshot.lastActiveAt):safe(f.snapshot.lastActivity)}</dd></div><div class="snapshot-reason"><dt>Triggered reason</dt><dd>${safe(f.originalReason)}</dd></div></dl><h4 class="evidence-subheading">Preserved evidence</h4><ul class="evidence-list">${f.evidence.map(e=>`<li>${safe(e)}</li>`).join('')}</ul>${f.aiExplanation?`<p class="policy-context"><span class="badge" style="background:${f.aiStatus==='success'?'#eff6ff':'#f1f5f9'};color:${f.aiStatus==='success'?'#1d4ed8':'#475569'};border:1px solid ${f.aiStatus==='success'?'#bfdbfe':'#cbd5e1'};font-size:10px;font-weight:700;margin-right:6px;padding:2px 6px;border-radius:4px;">${f.aiStatus==='success'?((f.aiModel&&f.aiModel.toLowerCase().includes('gemini'))?'Gemini AI':'Groq AI'):'Summary'}</span><strong>${f.aiStatus==='success'?'AI risk explanation:':'Policy check:'}</strong> ${safe(f.aiExplanation)}<br><small style="color:var(--muted);display:block;margin-top:4px;">${f.aiStatus==='success'?('Generated by '+((f.aiModel&&f.aiModel.toLowerCase().includes('gemini'))?'Gemini':'Groq')+' — verify before acting'):'Generated from report data'}</small></p>`:`<p class="policy-context"><strong>Policy check:</strong> ${safe(f.originalReason)}. Generated from report data.</p>`}</section>

    <section class="card detail-panel why-score-panel"><h3>Why this score?</h3><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><span>Calculated risk score: <strong style="font-size:14px;color:var(--text);">${p.score || (p.risk==='High'?70:p.risk==='Medium'?40:20)} pts</strong></span><span>${riskPill(p.risk)}</span></div>${(p.scoreBreakdown && p.scoreBreakdown.length) ? `<table class="why-score-table" style="width:100%;font-size:12px;border-collapse:collapse;"><thead><tr style="border-bottom:1px solid var(--border);color:var(--muted);text-align:left;"><th style="padding:6px 0;">Triggered Rule</th><th style="padding:6px 0;text-align:right;">Points</th></tr></thead><tbody>${p.scoreBreakdown.map(r => `<tr style="border-bottom:1px solid var(--border);"><td style="padding:8px 0;color:var(--text);"><strong>${safe(r.name)}</strong><small style="display:block;color:var(--muted);">${safe(r.reason)}</small></td><td style="padding:8px 0;text-align:right;font-weight:700;color:var(--orange);">+${r.points} pts</td></tr>`).join('')}</tbody></table>` : `<p class="text-muted" style="font-size:12px;">Standard baseline policy evaluation.</p>`}</section>

    <section class="card detail-panel"><h3>Recommended next step</h3><div class="recommendation"><div class="recommendation-icon">${uiIcon('sparkles', 16)}</div><div><strong>${safe(r.title)}</strong><p>${safe(r.body)}</p></div></div><div class="permission-comparison"><div><span>Current permission</span><strong>${safe(p.access)}</strong></div><span class="comparison-arrow">→</span><div><span>Recommended permission</span><strong>${safe(r.target)}</strong></div></div><p class="expected-outcome"><strong>Expected outcome:</strong> ${safe(r.outcome)}</p>${p.access !== 'None' ? `<div class="risk-action-row" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">${this.isOpen(p)?`<button class="btn btn-outline btn-sm" data-dismiss="${safe(p.id)}">Dismiss finding</button>`:''}${this.isOpen(p)&&r.target!=='None'&&r.target!==p.access?`<button class="btn btn-primary btn-sm" data-remediate="${safe(p.id)}">Reduce ${safe(p.access)} to ${safe(r.target)}</button>`:''}<button class="btn btn-danger btn-sm" data-revoke="${safe(p.id)}" style="background:#dc2626;border-color:#dc2626;color:#fff;font-weight:600;">${uiIcon('trash', 12)} Revoke access</button></div>` : '<p class="resolution-note" style="color:#16a34a;font-weight:600;">✓ Access is completely revoked (None). No active permissions on GitHub.</p>'}</section>

    <section class="card detail-panel"><h3>Identity details</h3><dl class="detail-kv"><dt>Name</dt><dd>${safe(p.name)}</dd><dt>Email</dt><dd>${safe(p.email)}</dd><dt>Role / team</dt><dd>${safe(p.role)} · ${safe(p.team)}</dd><dt>Employment</dt><dd>${p.team==='Former employee'?'Former employee':p.team==='External'?'Contractor':'Active employee'}</dd><dt>Last activity</dt><dd>${this.relativeMarkup(p.lastActiveAt,p.last)}</dd></dl></section></div>

    <div class="detail-main"><section class="card detail-panel"><h3>Assignment record</h3><dl class="detail-kv"><dt>Resource</dt><dd>${safe(p.repo)}</dd><dt>Source</dt><dd>${safe(p.source)}</dd><dt>Original access</dt><dd>${safe(f.originalAccess)}</dd><dt>Current access</dt><dd>${safe(p.access)}</dd><dt>Review outcome</dt><dd>${safe(f.status)}</dd></dl></section><section class="card detail-panel"><h3>Review timeline</h3><div class="timeline">${events.map(e=>`<div class="timeline-item"><span class="timeline-dot"></span><div class="timeline-copy"><strong>${safe(e.title)}</strong><p>${safe(e.actor)}${e.before!==null&&e.before!==undefined?' · '+safe(e.before)+' → '+safe(e.after):''}</p>${e.note?`<p class="timeline-note">${safe(e.note)}</p>`:''}<time>${this.date(e.occurredAt)}</time></div></div>`).join('')}<div class="timeline-item"><span class="timeline-dot muted"></span><div class="timeline-copy"><strong>${f.originalSeverity==='Low'?'Healthy assignment recorded':'Original finding recorded'}</strong><p>${safe(f.originalAccess)} · ${safe(f.originalReason)}</p><time>${this.date(f.detectedAt)}</time></div></div></div></section><section class="card detail-panel"><h3>Related requests</h3>${related.map(a=>`<div class="related-request"><strong>${safe(a.id)}</strong><span>${safe(a.type)} · ${safe(a.access)}</span>${badge(a.status)}</div>`).join('')||'<p>No related requests.</p>'}</section></div></div>`;

  },

  resolve(id,dismiss,forceRevoke=false){const p=people.find(p=>p.id===id);if(!p)return;if(!dismiss&&!forceRevoke&&!this.isOpen(p))return;if(forceRevoke&&p.access==='None')return;const r=this.recommendation(p),before=p.access,target=dismiss?before:(forceRevoke?'None':r.target);const modalTitle=dismiss?'Dismiss this finding?':(forceRevoke||target==='None'?`Revoke access for ${p.name}?`:r.title);const modalBody=dismiss?'Record that this permission was reviewed and accepted. The original risk evidence stays available.':(forceRevoke||target==='None'?`Revoke all access permissions to ${p.repo}. Collaborator will be removed and an automated notification email will be dispatched.`:`${r.body} An automated notification email will be dispatched to the user.`);openDecision(modalTitle,modalBody,`${p.name} · ${p.repo} · ${before} → ${target}`,dismiss?'Confirm dismissal':(target==='None'?'Confirm revocation':'Confirm permission change'),async note=>{if(!this.isOpen(p)&&!forceRevoke)return;if(window.ApiClient&&!window.ApiClient.isDemoMode){try{if(dismiss)await ApiClient.dismiss(p.id,note);else await ApiClient.remediate(p.id,note,target);const data=await ApiClient.bootstrap();ApiClient.syncState(data);render();decisionFeedback(dismiss?'Finding dismissed; comment saved.':(target==='None'?`Access revoked (${before} → None); notice email sent.`:`Permission reduced (${before} → ${target}); notice email sent.`));return;}catch(err){showToast(err.message||'Could not complete action.');return;}}p.access=target;p.resolved=true;p.finding.status=dismiss?'Dismissed':'Remediated';p.reviewedAt=this.date(new Date().toISOString());this.record({title:dismiss?'Risk finding dismissed':(target==='None'?'Access revoked':'Permission changed'),tag:dismiss?'Dismissed':'Remediated',source:p.source,assignmentId:p.id,before,after:p.access,detail:`${p.name} · ${p.repo}`,note,tone:dismiss?'gray':'green'});decisionFeedback(dismiss?'Finding dismissed; decision recorded.':(target==='None'?'Access revoked on GitHub; decision recorded.':'Permission updated on GitHub; decision recorded.'));});},

  approve(id,action){

    const a=approvals.find(a=>a.id===id);if(!a||a.status!=='Pending')return;

    const isDirectGrant = a.type === 'Direct GitHub Grant Review';
    const isNewEmployee = !isDirectGrant && (a.isNewEmployee || (a.email && a.email.endsWith('@payhive.internal')) || (a.email && a.email.endsWith('@github.unmatched')) || (a.type === 'New employee onboarding'));

    const ghTag = a.githubLogin ? `@${a.githubLogin}` : (a.email.includes('@github.unmatched') ? `@${a.email.split('@')[0]}` : '');

    const modalTitle = action==='Approved' 

      ? (isDirectGrant ? `Ratify direct GitHub access for ${a.person}?` : (isNewEmployee ? `Approve & Onboard ${a.person} to GitHub?` : `Approve access for ${a.person}?`)) 

      : (isDirectGrant ? `Revoke unapproved GitHub access for ${a.person}?` : `Reject access request for ${a.person}?`);

    const modalBody = action==='Approved'

      ? (isNewEmployee 

          ? `${uiIcon('people', 14)} <strong>New Employee Onboarding:</strong> Approving will automatically provision <strong>${safe(a.person)}</strong> as an employee in payhive-eng, map GitHub account <code>${safe(ghTag || a.person)}</code>, grant <strong>${safe(a.access)}</strong> access live on GitHub repository <strong>${safe(a.repo)}</strong>, and dispatch an automated welcome notice email.`

          : `Business reason: ${a.reason}. Grant <strong>${safe(a.access)}</strong> access on GitHub to <strong>${safe(a.person)}</strong> and dispatch notification email.`)

      : `Decline access request for <strong>${safe(a.person)}</strong> and dispatch notification email.`;

    const btnText = action==='Approved' ? (isDirectGrant ? 'Ratify & Keep Access' : (isNewEmployee ? 'Onboard & Grant Access' : 'Approve request')) : (isDirectGrant ? 'Confirm & Revoke from GitHub' : 'Reject request');

    

    openDecision(modalTitle, modalBody, `${a.person} ${ghTag ? `(${ghTag})` : ''} · ${a.repo} · ${people.find(p=>p.email===a.email&&p.repo===a.repo)?.access||'None'} → ${a.type==='Access removal'?'None':a.access}`, btnText, async note=>{

      if(a.status!=='Pending')return;

      if(window.ApiClient&&!window.ApiClient.isDemoMode){

        try{

          await ApiClient.decideApproval(a.id,action,note);

          const data=await ApiClient.bootstrap();

          ApiClient.syncState(data);

          render();

          decisionFeedback(action==='Approved'

            ? (isDirectGrant ? 'Direct GitHub grant ratified and governance record updated.' : (isNewEmployee ? `Onboarding complete: ${a.person} registered, granted on GitHub, and welcome email sent.` : `Access request approved: granted on GitHub and notice email sent to ${a.email}.`))

            : (isDirectGrant ? `Unapproved collaborator revoked directly from GitHub repository ${a.repo}.` : `Access request rejected: notice email sent to ${a.email}.`));

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

  },

  eventRow(e){const changed=e.before!==null&&e.before!==undefined;return `<div class="decision-row"><span class="history-icon ${['orange','green','gray'].includes(e.tone)?e.tone:'gray'}">${uiIcon(['Approved','Remediated'].includes(e.tag)?'check':e.tag==='Declined'?'declined':e.tag==='Risk detected'?'alert':'history')}</span><div><strong>${safe(e.title)}</strong><small>${safe(e.detail)}</small><span class="decision-meta">${safe(e.actor)} · ${this.date(this.timestamp(e))}${e.source?' · '+safe(e.source):''}</span></div>${changed?`<span class="permission-delta">${safe(e.before)} <i>→</i> ${safe(e.after)}</span>`:''}</div>`;},

  history(){const filtered=filteredHistory();state.historyPage=Math.min(state.historyPage,Math.max(1,Math.ceil(filtered.length/6)));const visible=filtered.slice((state.historyPage-1)*6,state.historyPage*6);let previousDay='';return `<div class="history-workbench">${pageHeading('Audit history','Trace access changes and the decisions behind them.',`<button class="btn btn-outline" data-export="history">Export log</button>`)}<section class="card history-controls"><div class="history-search-field"><label for="history-search">Find an event</label>${auditSearch('history-search',state.historyQuery,'Search people, resources, notes or request IDs…')}</div><div><label for="history-filter">Action type</label>${selectControl('history-filter','Action type',['All actions','Approved','Declined','Risk detected','Remediated','Dismissed','Audit','Request','User access','Rules','Schedule'],state.historyAction)}</div><div><label for="history-range">Time period</label>${selectControl('history-range','Date range',['Last 30 days','Last 7 days','Last 90 days'],state.historyRange)}</div></section><section class="history-ledger" aria-label="Decision and activity log"><div class="ledger-heading"><div><span class="section-eyebrow">WORKSPACE RECORD</span><h2>Decision and activity log</h2></div><span class="ledger-total">${filtered.length} matching events</span></div><div class="ledger-timeline">${visible.map(e=>{const day=new Intl.DateTimeFormat('en',{timeZone:'Asia/Karachi',month:'long',day:'numeric',year:'numeric'}).format(new Date(this.timestamp(e)));const group=day!==previousDay?`<div class="ledger-day"><span>${day}</span></div>`:'';previousDay=day;return `${group}<details class="event-details ledger-event"><summary><span class="ledger-marker ${['orange','green','gray'].includes(e.tone)?e.tone:'gray'}">${uiIcon(({Approved:'check',Declined:'declined',Remediated:'check',Audit:'audit',Request:'people','Risk detected':'alert',Dismissed:'check'})[e.tag]||'history')}</span><div class="ledger-event-content"><div class="ledger-event-top"><strong>${safe(e.title)}</strong><span class="status-badge ${['Approved','Remediated'].includes(e.tag)?'approved':e.tag==='Declined'?'declined':'ledger-tag'}">${safe(statusLabel(e.tag))}</span></div><p class="ledger-target"><span>Target / context</span>${safe(e.detail)}</p>${e.before!==null&&e.before!==undefined?`<span class="ledger-change">${safe(e.before)} <i>→</i> ${safe(e.after)}</span>`:''}<div class="ledger-event-meta"><span>${safe(e.actor)}</span><span>${new Intl.DateTimeFormat('en',{timeZone:'Asia/Karachi',hour:'numeric',minute:'2-digit',second:'2-digit'}).format(new Date(this.timestamp(e)))}</span>${e.source?`<span>${safe(e.source)}</span>`:''}</div></div><span class="event-expand" aria-hidden="true">${uiIcon('chevronRight')}</span></summary><div class="event-detail-body"><dl class="detail-kv"><dt>Action</dt><dd>${safe(statusLabel(e.tag))}</dd><dt>Target / context</dt><dd>${safe(e.detail)}</dd><dt>Event ID</dt><dd>${safe(e.id)}</dd><dt>Actor</dt><dd>${safe(e.actor)}</dd><dt>Timestamp</dt><dd>${this.date(this.timestamp(e))} (Karachi)</dd><dt>Source</dt><dd>${safe(e.source||'Direct GitHub Organization Grant')}</dd><dt>Assignment / request</dt><dd>${safe(e.assignmentId||'—')} / ${safe(e.requestId||'—')}</dd><dt>Permission before</dt><dd>${safe(e.before??'Direct GitHub Organization Grant')}</dd><dt>Permission after</dt><dd>${safe(e.after??'Direct GitHub Organization Grant')}</dd><dt>Decision note</dt><dd>${safe(e.note||'No note provided')}</dd></dl>${e.auditId?`<button class="text-link" data-audit-report="${safe(e.auditId)}">View audit results →</button>`:''}${e.assignmentId?`<button class="text-link" data-risk-person="${safe(e.assignmentId)}">View preserved finding →</button>`:''}</div></details>`;}).join('')||'<div class="card empty-state"><strong>No matching events</strong>Adjust your search or filters.</div>'}</div><div class="page-pagination">${pagination('history',state.historyPage,filtered.length)}</div></section></div>`;},

  async runAudit(){if(auditing)return;auditing=true;location.hash='audit';render();try{if(window.ApiClient&&!window.ApiClient.isDemoMode){const rep=await ApiClient.runAudit();const data=await ApiClient.bootstrap();ApiClient.syncState(data);auditing=false;render();this.report(rep.id);return;}await new Promise(resolve=>setTimeout(resolve,650));const completedAt=new Date().toISOString(),id='AUD-'+Date.now();const report={id,completedAt,status:'Completed',actor:this.actor(),scope:['GitHub'],...this.summary(),sample:false,mode:'LIVE_GITHUB'};auditRuns.push(report);lastAudit=this.date(completedAt);this.record({title:'Access audit completed',tag:'Audit',auditId:id,source:'GitHub',detail:`${report.assignments} assignments checked; ${report.high} high / ${report.medium} medium findings`});auditing=false;render();this.report(id);}catch{showToast('The audit could not finish. Try running it again.');}finally{if(auditing){auditing=false;render();}}},

  report(id){ReportDialog.open(id);},

  async reset(){if(window.ApiClient&&!window.ApiClient.isDemoMode){try{await ApiClient.resetSample();const data=await ApiClient.bootstrap();ApiClient.syncState(data);decisionFeedback('Workspace data refreshed from live GitHub.');render();return;}catch{/* fallback to local */}}const seed=JSON.parse(initialStore);people=seed.people;approvals=seed.approvals;history=seed.history;lastAudit=seed.lastAudit;auditRuns=[];auditSnapshots=[];this.initialize();Object.assign(state,{auditQuery:'',approvalQuery:'',historyQuery:'',auditPage:1,historyPage:1,approvalFilter:'Pending',auditRisk:'All risks',auditAccess:'All access levels',auditSource:'All sources',historyAction:'All actions',historyRange:'Last 30 days',auditUser:'All users',auditRepo:'All resources',auditAction:'All actions'});persist();decisionFeedback('Workspace data refreshed from live GitHub.');},

  trend(period){const days=parseInt(period),today=new Date(Math.max(Date.parse('2026-10-14T12:00:00Z'),Date.now())).toLocaleDateString('en-CA',{timeZone:'Asia/Karachi'}),endDate=new Date(today+'T12:00:00+05:00');const byDay=new Map();for(const snapshot of auditSnapshots){const key=new Date(snapshot.at).toLocaleDateString('en-CA',{timeZone:'Asia/Karachi'}),previous=byDay.get(key);if(!previous||Date.parse(snapshot.at)>Date.parse(previous.at))byDay.set(key,snapshot);}return Array.from({length:days},(_,i)=>{const date=new Date(endDate);date.setUTCDate(date.getUTCDate()-(days-1-i));const key=date.toLocaleDateString('en-CA',{timeZone:'Asia/Karachi'}),latest=byDay.get(key);return {date,high:latest?.high??null,remediated:latest?.remediated??null};});}



};

document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-audit-report'))Governance.report(b.dataset.auditReport);if(b.hasAttribute('data-result-findings')){bootstrap.Modal.getInstance(document.querySelector('#review-modal')).hide();state.auditRisk='All risks';state.auditAction='All actions';state.auditRepo='All resources';state.auditUser='All users';location.hash='audit';render();}});





// Refresh relative labels without disrupting forms, expanded evidence or keyboard focus.

function refreshRelativeTimes(){document.querySelectorAll('[data-relative-at]').forEach(e=>e.textContent=Governance.relative(e.dataset.relativeAt));}

setInterval(refreshRelativeTimes,60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshRelativeTimes();});

