const SearchPalette={
  active:0,
  query(query){
    const container=document.querySelector('.search-suggestions'),q=query.trim().toLowerCase();this.active=0;
    const row=(icon,title,subtitle,attributes)=>`<button class="command-result" role="option" ${attributes}><span class="command-result-icon">${uiIcon(icon)}</span><span class="command-result-copy"><strong>${safe(title)}</strong><small>${safe(subtitle)}</small></span><span class="command-result-arrow">↵</span></button>`;
    const group=(title,rows)=>rows.length?`<section class="command-group"><h3>${title}<span>${rows.length}</span></h3>${rows.join('')}</section>`:'';
    if(!q){container.innerHTML=group('Jump to',[row('audit','Access audit','Inspect GitHub permissions and application roles','data-search-page="audit"'),row('clock','Pending approvals','Review requests awaiting a decision','data-search-page="approvals"'),row('history','Audit history','Find decisions and permission changes','data-search-page="history"')]);}
    else {
      const found=people.filter(p=>`${p.name} ${p.email} ${p.repo} ${p.source}`.toLowerCase().includes(q));
      const identities=[...new Map(found.map(p=>[p.email,p])).values()].slice(0,5);
      const resources=[...new Map(found.map(p=>[p.source+':'+p.repo,p])).values()].slice(0,5);
      const requests=approvals.filter(a=>`${a.id} ${a.person} ${a.repo} ${a.status}`.toLowerCase().includes(q)).slice(0,4);
      const events=Governance.orderedEvents().filter(e=>`${e.title} ${e.detail} ${e.note} ${e.requestId||''}`.toLowerCase().includes(q)).slice(0,4);
      container.innerHTML=group('People',identities.map(p=>row('people',p.name,p.email,`data-search-page="risk?${encodeURIComponent(p.id)}"`)))+group('Resources',resources.map(p=>row(p.source==='GitHub'?'repo':'overview',p.repo,p.source+' · Show all assignments',`data-search-resource="${safe(p.repo)}"`)))+group('Requests',requests.map(a=>row('clock',a.id+' · '+a.person,a.repo+' · '+a.status,`data-search-request="${safe(a.id)}"`)))+group('Activity',events.map(e=>row('history',e.title,e.detail,`data-search-event="${safe(e.id)}"`)));
      if(!container.innerHTML)container.innerHTML=`<div class="command-empty">${uiIcon('search')}<strong>No results for “${safe(query)}”</strong><p>Try a person, resource, request ID, or decision note.</p></div>`;
    }
    this.highlight();document.querySelector('#command-result-count').textContent=q?`${container.querySelectorAll('button').length} results`:'Workspace shortcuts';
  },
  highlight(){const rows=[...document.querySelectorAll('.command-result')];rows.forEach((row,i)=>{row.classList.toggle('command-active',i===this.active);row.setAttribute('aria-selected',String(i===this.active));row.id='command-result-'+i;});const input=document.querySelector('#global-search');if(rows.length){input.setAttribute('aria-activedescendant',rows[this.active].id);}else input.removeAttribute('aria-activedescendant');},
  key(e){if(e.target.id!=='global-search')return;if(!['ArrowDown','ArrowUp','Enter'].includes(e.key))return;const rows=[...document.querySelectorAll('.command-result')];if(!rows.length)return;e.preventDefault();if(e.key==='Enter'){rows[this.active].click();return;}this.active=(this.active+(e.key==='ArrowDown'?1:-1)+rows.length)%rows.length;this.highlight();rows[this.active].scrollIntoView({block:'nearest'});}
};
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
  if(b.hasAttribute('data-search-resource')){state.auditQuery=b.dataset.searchResource;state.auditRisk='All risks';state.auditAccess='All access levels';state.auditSource='All sources';state.auditUser='All users';state.auditRepo='All resources';state.auditAction='All actions';state.auditPage=1;location.hash='audit';render();}
  else if(b.hasAttribute('data-search-request')){state.approvalQuery=b.dataset.searchRequest;state.approvalFilter='All requests';location.hash='approvals';render();}
  else if(b.hasAttribute('data-search-event')){state.historyQuery=b.dataset.searchEvent;state.historyAction='All actions';state.historyRange='Last 90 days';state.historyPage=1;location.hash='history';render();}
  else return;
  bootstrap.Modal.getInstance(document.querySelector('#search-modal'))?.hide();
});
