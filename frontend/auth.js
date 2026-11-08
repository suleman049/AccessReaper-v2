// Firebase email/password forms. No credentials enter the local audit store.
const AccessReaperAuth = {
  fieldIcon(name) {
    const paths={mail:'M3 5h18v14H3z M3 6l9 7 9-7',person:'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M4 21v-2a8 8 0 0 1 16 0v2',lock:'M5 10h14v11H5z M8 10V7a4 4 0 0 1 8 0v3',arrow:'M4 12h16 M14 6l6 6-6 6'};
    return `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name]}"/></svg>`;
  },
  render(mode) {
    const signup=mode==='signup';
    document.querySelector('#login-screen').dataset.mode=mode;
    const icon=name=>this.fieldIcon(name);
    document.querySelector('#auth-content').innerHTML=`
      <nav class="auth-mode-nav" aria-label="Account access"><a href="#login" ${signup?'':'aria-current="page"'}>Sign in</a><a href="#signup" ${signup?'aria-current="page"':''}>Sign up</a></nav>
      <div class="auth-heading"><span class="auth-step-label">${signup?'YOUR NEXT CHAPTER':'BACK IN CONTROL'}</span><h2>${signup?'A clearer view<br>starts here.':'Welcome<br>back.'}<span class="heading-period">/</span></h2><p>${signup?'Create your account, then wait for administrator approval.':'Sign in to your authorized AccessReaper workspace.'}</p></div>
      <form id="auth-form" data-mode="${mode}" novalidate>
        ${signup?`<div class="auth-field"><label for="full-name">Full name</label><div class="auth-input-wrap"><span class="auth-field-icon">${icon('person')}</span><input class="form-control" id="full-name" autocomplete="name" placeholder="Jordan Davis" required maxlength="80"></div></div>`:''}
        <div class="auth-field"><label for="email">Work email</label><div class="auth-input-wrap"><span class="auth-field-icon">${icon('mail')}</span><input class="form-control" id="email" name="username" type="email" autocomplete="username" value="itzsuleman110@gmail.com" placeholder="itzsuleman110@gmail.com"  required></div></div>
        <div class="auth-field"><div class="auth-label-row"><label for="password">${signup?'Create a password':'Password'}</label>${signup?'':'<button type="button" class="auth-forgot" data-auth-help>Forgot password?</button>'}</div><div class="auth-input-wrap"><span class="auth-field-icon">${icon('lock')}</span><input class="form-control" id="password" name="password" type="password" autocomplete="${signup?'new-password':'current-password'}" value="Password123!" placeholder="${signup?'At least 8 characters':'Enter your password'}" minlength="${signup?8:1}" required ${signup?'aria-describedby="password-guidance"':''}><button type="button" class="show-password auth-reveal" aria-label="Show password" aria-pressed="false">Show</button></div>${signup?'<div class="auth-password-guidance" id="password-guidance"><span class="password-meter" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span id="password-guidance-text">Use at least 8 characters</span></div>':''}</div>
        ${signup?`<div class="auth-field"><label for="confirm-password">Confirm password</label><div class="auth-input-wrap"><span class="auth-field-icon">${icon('lock')}</span><input class="form-control" id="confirm-password" type="password" autocomplete="new-password" placeholder="Re-enter your password" minlength="8" required aria-describedby="auth-error"></div></div>`:''}
        <p id="firebase-auth-status" class="auth-service-status" role="status" hidden></p><button type="button" class="text-link auth-retry" data-auth-retry hidden>Retry connection</button><p id="auth-error" class="auth-error" role="alert"></p>
        <button class="btn btn-primary auth-submit" type="submit"><span>${signup?'Create account':'Sign in'}</span>${icon('arrow')}</button>
        ${signup?'':'<button class="btn btn-outline auth-admin-shortcut" type="button" data-admin-login>Sign in as admin</button>'}
        <div class="auth-demo-note"><span class="auth-note-icon">${icon('lock')}</span><p><strong>Your workspace, protected.</strong> ${signup?'New accounts need administrator approval before accessing the workspace.':'Access is limited to authorized members of your organization.'}</p></div>
      </form>`;
    document.querySelectorAll('#auth-form input').forEach(input=>{
      const message=document.createElement('p');message.className='auth-field-error';message.id=input.id+'-error';message.setAttribute('aria-live','polite');input.closest('.auth-field').append(message);
      input.setAttribute('aria-describedby',[input.getAttribute('aria-describedby'),message.id].filter(Boolean).join(' '));
    });
  }
};
document.addEventListener('input',event=>{
  if(!event.target.closest('#auth-form'))return;
  const error=document.querySelector('#auth-error');if(error)error.textContent='';const fieldError=document.getElementById(event.target.id+'-error');if(fieldError)fieldError.textContent='';event.target.removeAttribute('aria-invalid');
  if(event.target.id==='password'&&document.querySelector('#password-guidance')){
    const value=event.target.value;
    const score=value.length<8?value.length?1:0:Math.min(4,2+Number(/[A-Z]/.test(value)&&/[a-z]/.test(value))+Number(/\d/.test(value)&&/[^a-zA-Z0-9]/.test(value)));
    document.querySelectorAll('.password-meter i').forEach((bar,index)=>{bar.classList.toggle('filled',index<score);bar.dataset.level=score;});
    document.querySelector('#password-guidance-text').textContent=value.length<8?'Use at least 8 characters':score===4?'Strong password':score===3?'Good — add a number or symbol':'Ready — mix letters, numbers and symbols';
  }
});

// Field-specific validation runs before the Firebase submit handler.
document.addEventListener('submit',event=>{
  if(event.target.id!=='auth-form')return;
  const fields=[...event.target.querySelectorAll('input')];let firstInvalid=null;
  fields.forEach(input=>{
    let message='';const value=input.value.trim();
    if(!value)message=input.id==='email'?'Enter your work email.':input.id==='full-name'?'Enter your full name.':input.id==='confirm-password'?'Confirm your password.':'Enter your password.';
    else if(input.id==='email'&&input.validity.typeMismatch)message='Enter a valid email address, such as you@company.com.';
    else if(input.id==='password'&&event.target.dataset.mode==='signup'&&input.value.length<8)message='Use at least 8 characters.';
    else if(input.id==='confirm-password'&&input.value!==document.querySelector('#password').value)message='Passwords do not match.';
    const target=document.getElementById(input.id+'-error');if(target)target.textContent=message;
    input.setAttribute('aria-invalid',String(Boolean(message)));if(message&&!firstInvalid)firstInvalid=input;
  });
  if(firstInvalid){event.preventDefault();event.stopImmediatePropagation();document.querySelector('#auth-error').textContent=firstInvalid.id==='confirm-password'?'Passwords do not match. Check the confirmation below.':'Check the highlighted fields.';firstInvalid.focus();}
},true);
