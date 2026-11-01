// Device-local presentation preference, independent of the sample audit store.
const Theme={
  key:'accessreaper-appearance-v1',
  current:'light',
  icon(name){return `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${name==='sun'?'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5L19 19 M5 19l1.5-1.5 M17.5 6.5L19 5':'M20 15.3A9 9 0 0 1 8.7 4 9 9 0 1 0 20 15.3z'}"/></svg>`;},
  apply(mode,save=false){this.current=mode==='dark'?'dark':'light';document.documentElement.dataset.theme=this.current;document.documentElement.style.colorScheme=this.current;document.querySelector('meta[name="theme-color"]')?.setAttribute('content',this.current==='dark'?'#10151d':'#e9ece9');if(save){try{localStorage.setItem(this.key,this.current);document.dispatchEvent(new CustomEvent('theme-storage-result',{detail:{ok:true}}));}catch{document.dispatchEvent(new CustomEvent('theme-storage-result',{detail:{ok:false}}));}}this.sync();},
  sync(){document.querySelectorAll('[data-theme-toggle]').forEach(button=>{button.setAttribute('role','switch');button.setAttribute('aria-label','Dark mode');button.setAttribute('aria-checked',String(this.current==='dark'));button.title=this.current==='dark'?'Switch to light mode':'Switch to dark mode';button.innerHTML=`<span class="theme-sun">${this.icon('sun')}</span><span class="theme-moon">${this.icon('moon')}</span><span class="theme-thumb"></span>`;});},
  initialize(){let stored='light';try{stored=localStorage.getItem(this.key)||'light';}catch{}this.apply(stored);}
};
Theme.initialize();
document.addEventListener('DOMContentLoaded',()=>Theme.sync());
document.addEventListener('click',event=>{if(event.target.closest('[data-theme-toggle]'))Theme.apply(Theme.current==='dark'?'light':'dark',true);});
