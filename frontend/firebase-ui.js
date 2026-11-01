// Authentication presentation and route access. No tokens or passwords are rendered.
const FirebaseUI = {
  busy:false,notice:'',
  start(){ FirebaseIdentity.initialize(); },
  guard(page){
    if(page === 'request') return false;
    const publicPage=['login','signup'].includes(page),identity=FirebaseIdentity;
    if(identity.authorized){if(publicPage){location.hash='dashboard';return true;}return false;}
    if(publicPage&&!identity.user){return false;}
    document.querySelector('#app').classList.add('d-none');
    document.querySelector('#login-screen').classList.remove('d-none');
    if(identity.phase==='signed-out'){
      document.title='Sign in · AccessReaper';
      if(!publicPage)window.history.replaceState(null,'','#login');
      AccessReaperAuth.render('login');this.syncForm();Theme.sync();syncStorageWarning();return true;
    }
    if(['loading','checking-profile'].includes(identity.phase)){
      document.title='Sign in · AccessReaper';
      if(!document.querySelector('#auth-form'))AccessReaperAuth.render('login');
      this.syncForm();Theme.sync();syncStorageWarning();return true;
    }
    this.renderGate();return true;
  },
  renderGate(){
    const identity=FirebaseIdentity,pending=identity.phase==='pending',error=identity.phase==='error';
    const checking=['loading','checking-profile'].includes(identity.phase);
    document.title=(pending?'Access pending':error?'Sign-in unavailable':'Checking access')+' · AccessReaper';
    const title=checking?'Checking your access…':pending?'Workspace access pending':'Unable to load your access';
    const message=checking?'Please wait while your session and workspace role are checked.':pending?'You are signed in. An administrator must activate your account for this workspace before you can open the dashboard.':identity.error;
    document.querySelector('#auth-content').innerHTML=`<section class="identity-gate" aria-labelledby="identity-gate-title"><span class="auth-step-label">ACCESSREAPER ACCOUNT</span><h2 id="identity-gate-title">${safe(title)}</h2><p role="status">${safe(message)}</p>${identity.user?`<p class="identity-email">${safe(identity.user.email)}</p>`:''}<div class="identity-gate-actions">${!checking?'<button class="btn btn-primary" type="button" data-check-access>Check access again</button>':''}${identity.user?'<button class="btn btn-outline" type="button" data-sign-out>Sign out</button>':''}</div><p class="identity-gate-note">Need workspace access? Contact your administrator.</p></section>`;
    Theme.sync();syncStorageWarning();
  },
  syncForm(){
    const identity=FirebaseIdentity,form=document.querySelector('#auth-form');if(!form)return;
    const ready=Boolean(identity.auth)&&!['loading','checking-profile'].includes(identity.phase);
    const submit=form.querySelector('[type="submit"]');submit.disabled=this.busy||!ready;
    submit.querySelector('span').textContent=this.busy||identity.phase==='checking-profile'?'Signing in…':form.dataset.mode==='signup'?'Create account':'Sign in';
    form.setAttribute('aria-busy',String(this.busy||!ready));
    form.querySelectorAll('input,button').forEach(el=>{if(el!==submit)el.disabled=this.busy||identity.phase==='checking-profile';});
    const help=form.querySelector('[data-auth-help]');if(help)help.disabled=this.busy||!ready;
    const status=form.querySelector('#firebase-auth-status');
    if(status){status.textContent=identity.phase==='error'?identity.error:this.notice;status.hidden=!status.textContent;}
    const retry=form.querySelector('[data-auth-retry]');if(retry)retry.hidden=identity.phase!=='error';
  },
  syncIdentity(){
    const identity=FirebaseIdentity;if(!identity.authorized)return;
    const name=identity.profile.name||identity.user.displayName||identity.user.email;
    document.querySelectorAll('.top-user strong,.profile-info strong,.settings-session strong').forEach(el=>{el.textContent=name;el.title=name;});
    document.querySelectorAll('.top-user small,.profile-info small,.settings-session small').forEach(el=>el.textContent='Workspace administrator');
    document.querySelectorAll('.top-avatar,.profile-avatar').forEach(el=>el.textContent=initials(name));
  },
  async submit(form){
    if(this.busy)return;this.notice='';this.busy=true;this.syncForm();
    const error=form.querySelector('#auth-error');error.textContent='';
    const email=form.querySelector('#email').value.trim(),password=form.querySelector('#password').value;
    try{
      if(form.dataset.mode==='signup')await FirebaseIdentity.signUp(form.querySelector('#full-name').value.trim(),email,password);
      else await FirebaseIdentity.signIn(email,password);
    }catch(e){
      const current=document.querySelector('#auth-error');if(current)current.textContent=FirebaseIdentity.message(e);
      else{FirebaseIdentity.phase='error';FirebaseIdentity.error=FirebaseIdentity.message(e);render();}
    }finally{
      this.busy=false;
      // Credentials are not retained in application state or local audit storage.
      if(!form.isConnected)form.reset();
      this.syncForm();
    }
  },
  forgotPassword(){ this.openPasswordReset(); },
  openPasswordReset(){
    if(this.busy||document.querySelector('#password-reset-dialog'))return;
    const dialog=document.createElement('dialog');dialog.id='password-reset-dialog';dialog.className='password-reset-dialog';
    dialog.setAttribute('aria-labelledby','reset-title');
    dialog.innerHTML=`<form id="password-reset-form"><span class="auth-step-label">ACCOUNT RECOVERY</span><h2 id="reset-title">Forgot password?</h2><p>Enter your account email. We’ll send you a link to choose a new password.</p><label for="reset-email">Email address</label><input class="form-control" id="reset-email" name="email" type="email" autocomplete="email" placeholder="you@company.com" required><p id="reset-feedback" role="status" aria-live="polite"></p><button type="submit" class="btn btn-primary">Send reset link</button><button type="button" class="btn btn-outline" data-close-reset>Back to sign in</button></form>`;
    const email=dialog.querySelector('input'),feedback=dialog.querySelector('#reset-feedback'),submit=dialog.querySelector('[type="submit"]');
    email.value=document.querySelector('#email')?.value.trim()||'';
    dialog.querySelector('[data-close-reset]').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('close',()=>dialog.remove(),{once:true});
    dialog.querySelector('form').addEventListener('submit',async event=>{
      event.preventDefault();if(submit.disabled)return;
      if(!FirebaseIdentity.auth){feedback.textContent='Please wait for the connection, then try again.';return;}
      if(email.value.trim().toLowerCase().endsWith('.example')){feedback.textContent='This sample account has no email inbox. Password recovery needs a real email address. Contact your administrator to update the account email.';return;}
      submit.disabled=true;email.disabled=true;submit.textContent='Sending…';feedback.textContent='';
      try{
        try{await FirebaseIdentity.resetPassword(email.value.trim());}catch(error){if(error.code!=='auth/user-not-found')throw error;}
        feedback.textContent='If an account exists for this email, a reset link is on its way. Check your inbox and spam folder. Follow the link, then return here to sign in with your new password.';
        submit.textContent='Reset link requested';
      }catch(error){feedback.textContent=FirebaseIdentity.message(error);submit.disabled=false;email.disabled=false;submit.textContent='Try again';}
    });
    document.body.append(dialog);dialog.showModal();email.focus();
  },
  async signOut(){
    if(this.busy)return;this.busy=true;
    try{
      document.querySelectorAll('.modal.show').forEach(el=>bootstrap.Modal.getInstance(el)?.hide());
      confirmAction=null;await FirebaseIdentity.signOut();location.hash='login';render();
    }catch{showToast('Could not sign out. Check your connection and try again.');}
    finally{this.busy=false;this.syncForm();}
  }
};
document.addEventListener('identity-changed',()=>{
  if(!FirebaseIdentity.authorized){document.querySelectorAll('.modal.show').forEach(el=>bootstrap.Modal.getInstance(el)?.hide());if(typeof confirmAction!=='undefined')confirmAction=null;}
  render();FirebaseUI.syncForm();FirebaseUI.syncIdentity();
});
document.addEventListener('click',async e=>{
  const button=e.target.closest('button,a');if(!button)return;
  if(button.matches('[data-sign-out]')){e.preventDefault();FirebaseUI.signOut();}
  if(button.matches('[data-auth-help]')){e.preventDefault();FirebaseUI.forgotPassword();}
  if(button.matches('[data-admin-login]')){
    e.preventDefault();if(FirebaseUI.busy||FirebaseIdentity.phase==='checking-profile')return;
    const email=document.querySelector('#email'),password=document.querySelector('#password');
    if(email&&password){email.value='admin@accessreaper.example';email.dispatchEvent(new Event('input',{bubbles:true}));password.focus();}
  }
  if(button.matches('[data-auth-retry],[data-check-access]')){e.preventDefault();if(FirebaseUI.busy)return;FirebaseUI.busy=true;button.disabled=true;try{await FirebaseIdentity.refresh();}finally{FirebaseUI.busy=false;FirebaseUI.syncForm();}}
});

window.FirebaseUI = FirebaseUI;
