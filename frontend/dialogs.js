/* Use Bootstrap dialogs when loaded; provide accessible dialogs offline. */
if (!window.bootstrap) {
  const instances=new WeakMap();
  class OfflineModal {
    constructor(element){this.element=element;instances.set(element,this);this.onKey=e=>{if(e.key==='Escape')this.hide();if(e.key==='Tab'){const focus=[...element.querySelectorAll('button,input,textarea,a[href]')].filter(e=>!e.disabled);const first=focus[0],last=focus.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}};element.addEventListener('click',e=>{if(e.target===element||e.target.closest('[data-bs-dismiss="modal"]'))this.hide();});}
    show(){this.previous=document.activeElement;this.element.classList.add('show');this.element.removeAttribute('aria-hidden');this.element.setAttribute('aria-modal','true');this.element.setAttribute('role','dialog');document.body.classList.add('modal-open');document.addEventListener('keydown',this.onKey);this.element.querySelector('input,button,textarea')?.focus();this.element.dispatchEvent(new Event('shown.bs.modal'));}
    hide(){this.element.classList.remove('show');this.element.setAttribute('aria-hidden','true');this.element.removeAttribute('aria-modal');document.body.classList.remove('modal-open');document.removeEventListener('keydown',this.onKey);this.previous?.focus();}
    static getOrCreateInstance(e){return instances.get(e)||new OfflineModal(e);}
    static getInstance(e){return instances.get(e);}
  }
  window.bootstrap={Modal:OfflineModal};
}
