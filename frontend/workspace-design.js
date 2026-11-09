// Existing workspace content, reorganized for clear administrative decisions.

const WorkspaceDesign={

  auditOverview(){const s=Governance.stats(),report=auditRuns.at(-1);

    const unmapped = window.unmatchedGitHubAccounts || (window.GitHubSettings && window.GitHubSettings.unmatched) || [];

    const unmappedAuditBanner = unmapped.length > 0 ? `

      <div class="alert alert-warning mb-3" style="border-left: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.08); padding: 10px 14px; border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px;">

        <span style="font-size: 13px; display:inline-flex; align-items:center; gap:6px;">${uiIcon('alert', 16)} <strong>${unmapped.length} GitHub account(s) have hidden emails</strong> (${unmapped.map(u => '@' + u.login).join(', ')}). Revocation emails cannot reach them until linked.</span>

        <a href="#settings" class="btn btn-sm btn-outline" style="font-size: 12px; padding: 2px 10px; text-decoration: none;">Add emails</a>

      </div>

    ` : '';

    return `${unmappedAuditBanner}<section class="card audit-brief"><div class="audit-brief-main"><span class="section-eyebrow">CURRENT ACCESS POSTURE</span><div class="posture-totals"><div><strong>${s.high}</strong><span>High risk</span></div><div><strong>${s.medium ?? people.filter(p=>p.risk==='Medium'&&!p.resolved).length}</strong><span>Medium risk</span></div><div><strong>${people.filter(p=>p.risk==='Low'&&!p.resolved).length}</strong><span>Healthy</span></div><div><strong>${people.filter(p=>p.resolved).length}</strong><span>Reviewed</span></div></div><div class="audit-scope"><span>${uiIcon('repo')} GitHub (payhive-eng)</span><span>${s.assignments} assignments</span></div></div><div class="audit-brief-report"><span class="audit-state">Latest completed audit</span><strong>${report?Governance.date(report.completedAt):'No audit recorded'}</strong><small>${safe(report?.id||(window.automationStatus?.nextRunAt ? ('The first automatic audit runs ' + new Date(window.automationStatus.nextRunAt).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})) : 'The first automatic audit runs at 02:00 PKT'))}</small><small>Report is frozen at completion; current counts reflect later decisions.</small>${report?`<button class="text-link" data-audit-report="${report.id}">View full report →</button>`:''}</div><details class="audit-summary-disclosure"><summary><span>${AuditSummary.disclosureHeader(report)}</span><span class="disclosure-hint">Expand</span></summary>${AuditSummary.preview(report)}</details></section>`;},

  dashboard(){

    const s=Governance.stats(),last=auditRuns.at(-1);

    const metric=(label,value,icon,detail,tone='',href='')=>`<article class="card stat-card overview-metric ${tone}" ${href?`data-page-link="${href}" style="cursor:pointer;"`:''}><div class="stat-top"><span>${label}</span><span class="stat-icon">${uiIcon(icon)}</span></div><div class="stat-value">${value}</div><div class="stat-bottom">${detail}</div></article>`;

    const open=people.filter(Governance.isOpen).sort((a,b)=>({High:0,Medium:1,Low:2}[a.risk]-{High:0,Medium:1,Low:2}[b.risk]));

    const sample=s.github.slice(0, 5);

    const unmapped = window.unmatchedGitHubAccounts || (window.GitHubSettings && window.GitHubSettings.unmatched) || [];

    const unmappedBanner = unmapped.length > 0 ? `

      <div class="card p-3 mb-4 alert-warning-card" style="border-left: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.08); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; padding: 14px 18px; border-radius: 8px;">

        <div style="display: flex; align-items: center; gap: 14px;">

          <span style="color:#f59e0b; display:flex; align-items:center;">${uiIcon('alert', 28)}</span>

          <div>

            <strong style="font-size: 14px; color: var(--text-primary); display: block;">Hidden Emails Detected: ${unmapped.length} GitHub account(s) need manual email setup</strong>

            <span style="font-size: 13px; color: var(--text-secondary);">

              ${unmapped.map(u => '@' + u.login).join(', ')} keep their email addresses hidden on GitHub. Enter their company email addresses manually so AccessReaper can dispatch automated revocation notices.

            </span>

          </div>

        </div>

        <a href="#settings" class="btn btn-sm btn-primary" style="white-space: nowrap; text-decoration: none;">Add Emails in Settings →</a>

      </div>

    ` : '';

    const healthScore = Math.max(0, Math.min(100, 100 - (s.high * 15) - (s.medium * 5) + Math.min(10, s.resolved * 2)));

    const healthGrade = healthScore >= 95 ? 'A+' : (healthScore >= 85 ? 'A' : (healthScore >= 75 ? 'B' : (healthScore >= 60 ? 'C' : 'Critical')));

    const healthColor = healthScore >= 85 ? '#16a34a' : (healthScore >= 70 ? '#eab308' : '#dc2626');

    const healthBg = healthScore >= 85 ? 'rgba(22, 163, 74, 0.1)' : (healthScore >= 70 ? 'rgba(234, 179, 8, 0.1)' : 'rgba(220, 38, 38, 0.1)');

    const activeJitCount = people.filter(p => p.isTemporary && p.access !== 'None').length;



    const healthCard = `

      <section class="card mb-4" style="background:linear-gradient(135deg, rgba(255,77,31,0.04) 0%, rgba(22,163,74,0.05) 100%); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:18px 24px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px; margin-bottom:20px;">

        <div style="display:flex; align-items:center; gap:20px;">

          <div style="width:64px; height:64px; min-width:64px; min-height:64px; border-radius:50%; background:${healthBg}; border:3px solid ${healthColor}; display:flex; align-items:center; justify-content:center; font-size:${healthGrade.length > 5 ? '11px' : (healthGrade.length > 2 ? '15px' : '22px')}; font-weight:800; color:${healthColor}; flex-shrink:0; box-sizing:border-box; text-align:center; padding:2px; line-height:1; letter-spacing:${healthGrade.length > 5 ? '0.2px' : 'normal'};">

            ${healthGrade}

          </div>

          <div>

            <div style="display:flex; align-items:center; gap:8px;">

              <strong style="font-size:16px; color:var(--text-primary);">Security Health Score: ${healthScore}/100 (${healthGrade})</strong>

              <span style="font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px; background:${healthBg}; color:${healthColor};">${healthScore >= 85 ? 'OPTIMAL POSTURE' : 'ACTION RECOMMENDED'}</span>

            </div>

            <p style="margin:4px 0 0 0; font-size:13px; color:var(--text-secondary);">

              Continuous automated compliance for <strong>payhive-eng</strong> &bull; <a href="#audit?segment=inactive" style="color:var(--text-secondary);text-decoration:underline;">Dormant accounts triage</a> &bull; <a href="#audit?segment=jit" class="badge" style="background:#2563eb;color:#fff;text-decoration:none;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">${uiIcon('clock', 12)} ${activeJitCount} Active JIT Leases &rarr;</a>

            </p>

          </div>

        </div>

        <div style="display:flex; align-items:center; gap:10px;">

          <button class="btn btn-sm btn-outline" data-page-link="audit" style="font-size:13px;">View Security Audit &rarr;</button>

        </div>

      </section>

    `;



    return `<div class="workspace-heading"><div><span class="workspace-eyebrow">ACCESS GOVERNANCE</span><h1>Workspace overview</h1><p>Real-time access security and governance for payhive-eng.</p></div><div class="heading-actions">${window.AutomationTimer ? window.AutomationTimer.renderChip() : ''}</div></div>

      ${healthCard}

      ${unmappedBanner}

      <section class="stat-grid governance-stats overview-metrics">${metric('Total identities',s.identities,'people',s.assignments+' access assignments','','users')}${metric('GitHub repositories',new Set(s.github.map(p=>p.repo)).size,'repo',s.github.length+' permissions reviewed')}${metric('High-risk access',s.high,'alert','Open findings','metric-risk','audit?segment=high_risk')}${metric('Pending approvals',s.pending,'clock','Awaiting decision','metric-pending','approvals')}${metric('Reviewed & safe',s.resolved,'check',people.filter(p=>p.resolved).length+' recorded decisions','','audit?segment=remediated')}</section>

      
      <section class="dashboard-grid overview-primary"><article class="card panel attention-panel"><div class="panel-header"><div><span class="section-eyebrow">PRIORITY REVIEW</span><h2>Needs your attention</h2></div><span class="attention-total">${open.length} open</span></div><div class="risk-list">${open.slice(0,3).map(p=>`<div class="risk-row"><span class="risk-score ${p.risk==='Medium'?'medium':''}">${safe(p.risk[0])}</span><div class="risk-details"><strong>${safe(p.reason)}</strong><small>${safe(p.name)} · ${safe(p.repo)}</small></div><button class="risk-arrow" data-risk-person="${safe(p.id)}" aria-label="Review ${safe(p.name)}">${uiIcon('chevronRight')}</button></div>`).join('')||'<div class="empty-state"><strong>All findings reviewed</strong>No open risk findings remain.</div>'}</div><div class="attention-footer"><button class="text-link" data-page-link="audit?segment=high_risk">Review high-risk findings <span>→</span></button><small>payhive-eng Organization</small></div></article>${AuditSummary.card(last,auditing)}</section>

      
      <section class="card recent-decisions overview-decisions"><div class="panel-header"><div><span class="section-eyebrow">DECISION RECORD</span><h2>Recent decisions</h2></div><button class="text-link" data-page-link="history">View history →</button></div>${Governance.orderedEvents().filter(e=>['Approved','Declined','Remediated','Dismissed'].includes(e.tag)).slice(0,4).map(e=>Governance.eventRow(e)).join('')||'<div class="empty-state">No decisions have been recorded.</div>'}</section>`;

  },

  settings(){return `<div class="workspace-heading"><div><span class="workspace-eyebrow">WORKSPACE PREFERENCES</span><h1>Settings</h1><p>Manage your organization, access sources, and security preferences.</p></div></div>

    <div class="settings-layout"><div class="settings-main"><section class="card settings-card"><div class="settings-card-heading"><span class="settings-icon">${uiIcon('overview')}</span><div><h2>Workspace</h2><p>Organization details for this workspace.</p></div></div><div class="organization-banner"><span class="organization-emblem" style="background:#ff4d1f;color:#fff;">P</span><div><strong>payhive-eng</strong><small>GitHub Organization</small></div></div><dl class="settings-properties"><div><dt>Execution mode</dt><dd style="color:#16a34a;font-weight:700;">LIVE_GITHUB · Active enforcement</dd></div><div><dt>Storage</dt><dd data-storage-label>Live SQLite Database</dd></div></dl></section>

    <section class="card settings-card"><div class="settings-card-heading"><span class="settings-icon">${uiIcon('repo')}</span><div><h2>Connected services</h2><p>The access sources managed by AccessReaper.</p></div></div><div class="settings-service"><span class="service-icon">${uiIcon('repo')}</span><div><strong>GitHub Organization (payhive-eng)</strong><small>Repository permissions & collaborator access · Live management active</small></div><span class="connection-state" style="color:#16a34a;font-weight:600;">Connected</span></div></section>

    

    

</div>

    <div class="settings-aside"><section class="card settings-card session-card"><div class="settings-card-heading"><span class="settings-icon">${uiIcon('people')}</span><div><h2>Current session</h2><p>Your workspace session details.</p></div></div><div class="settings-session"><span class="profile-avatar">AD</span><div><strong>Security Admin</strong><small>Workspace administrator</small></div><button type="button" class="btn btn-outline" data-sign-out>Sign out</button></div></section></div></div>`;}

};

