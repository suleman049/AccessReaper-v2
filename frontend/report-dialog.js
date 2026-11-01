// Audit reports are preserved snapshots; this dialog is presentation only.
const ReportDialog={
  open(id){
    const report=auditRuns.find(r=>r.id===id)||auditRuns.at(-1);if(!report)return;
    confirmAction=null;
    const modal=document.querySelector('#review-modal'),onAudit=location.hash.split('?')[0]==='#audit';
    modal.classList.add('is-audit-report');modal.setAttribute('aria-labelledby','audit-result-title');
    const categories=[{key:'high',label:'High risk',tone:'high'},{key:'medium',label:'Medium risk',tone:'medium'},{key:'healthy',label:'Healthy',tone:'healthy'},{key:'resolved',label:'Reviewed',tone:'reviewed'}];
    document.querySelector('#review-modal-body').innerHTML=`
      <header class="report-header"><div class="report-heading"><span class="report-success-icon">${uiIcon('check')}</span><div><p class="report-kicker">ACCESS AUDIT / REPORT <span class="status-badge approved" style="font-size:10px;padding:2px 6px;">LIVE PRODUCTION</span></p><h2 id="audit-result-title">Audit completed</h2></div></div><button class="btn-close report-close" data-bs-dismiss="modal" aria-label="Close audit report"></button></header>
      <div class="report-body" tabindex="0" aria-label="Audit report content">
        <div class="report-meta"><span class="report-id">${safe(report.id)}</span><span>${Governance.date(report.completedAt)}</span><span>By ${safe(report.actor)}</span><span>Rules v${report.ruleVersion || 1}</span></div>
        <section class="report-coverage"><div><span>Assignments checked</span><strong>${report.assignments}</strong></div><div><span>Identities covered</span><strong>${report.identities}</strong></div><div><span>Sources checked</span><strong>${report.sources.length}<small>GitHub + Firestore</small></strong></div></section>
        <section class="report-section"><div class="report-section-title"><h3>Historical risk at audit completion</h3><span>${report.assignments} assignments</span></div><div class="report-risk-bar" role="img" aria-label="${report.high} high risk, ${report.medium} medium risk, ${report.healthy} healthy and ${report.resolved} reviewed"><span class="high" style="flex:${report.high}"></span><span class="medium" style="flex:${report.medium}"></span><span class="healthy" style="flex:${report.healthy}"></span><span class="reviewed" style="flex:${report.resolved}"></span></div><div class="report-risk-counts">${categories.map(c=>`<div><span class="report-risk-label"><i class="${c.tone}"></i>${c.label}</span><strong>${report[c.key]}</strong></div>`).join('')}</div></section>
        ${AuditSummary.preview(report)}
        <section class="report-section report-sources"><div class="report-section-title"><h3>Source coverage</h3><span>Live Organization Data</span></div>${report.sources.map(source=>`<div class="report-source-row"><span class="report-source-icon">${uiIcon(source.source==='GitHub'?'repo':'overview')}</span><div><strong>${safe(source.source)}</strong><small>${source.resources} ${source.source==='GitHub'?'repositories':'applications'} · ${source.assignments} assignments</small></div><span class="report-source-state">${uiIcon('check')} Checked</span></div>`).join('')}</section>
      </div>
      <footer class="report-footer"><p>Snapshot at completion.<br>Current permissions may differ after later decisions.</p><div style="display:flex;gap:8px;"><button type="button" class="btn btn-outline" id="download-report-pdf" data-run-id="${safe(report.id)}">Download PDF</button>${onAudit?'<button class="btn btn-primary" data-bs-dismiss="modal">Done</button>':'<button class="btn btn-primary" data-result-findings>Open access audit</button>'}</div></footer>`;
    document.querySelector('#download-report-pdf')?.addEventListener('click', () => {
      if (window.ApiClient) ApiClient.downloadPdf(report.id);
    });
    bootstrap.Modal.getOrCreateInstance(modal).show();
  }
};

// Global event delegation for Download PDF button
document.addEventListener('click', (e) => {
  const btn = e.target.closest('#download-report-pdf, [data-download-audit-pdf]');
  if (btn) {
    const runId = btn.dataset.runId;
    if (runId && window.ApiClient) {
      ApiClient.downloadPdf(runId);
    }
  }
});
