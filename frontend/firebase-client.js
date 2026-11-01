// Real authentication and own-profile access only. Audit data stays local and simulated.
const FirebaseIdentity = {
  phase: 'loading', user: null, profile: null, error: '', auth: null, db: null,
  sdk: null, initializing: null, profileLoad: null, authStop: null, profileStop: null,
  epoch: 0, signupName: '',
  get authorized() { return this.phase === 'authorized' && this.user && this.profile?.role === 'admin' && this.profile?.status === 'active' && ['acme', 'payhive-eng'].includes(this.profile?.organizationId); },
  notify() { document.dispatchEvent(new Event('identity-changed')); },
  message(error) {
    const messages = {
      'auth/invalid-credential': 'Email or password is incorrect.',
      'auth/wrong-password': 'Email or password is incorrect.',
      'auth/user-not-found': 'Email or password is incorrect.',
      'auth/email-already-in-use': 'An account already exists for this email. Sign in or reset your password.',
      'auth/invalid-email': 'Enter a valid email address.',
      'auth/weak-password': 'Choose a stronger password with at least 8 characters.',
      'auth/password-does-not-meet-requirements': 'Your password does not meet the account password policy.',
      'auth/too-many-requests': 'Too many attempts. Wait a few minutes and try again.',
      'auth/network-request-failed': 'Could not connect. Check your internet connection and try again.',
      'auth/configuration-not-found': 'Enable Authentication and Email/Password in this Firebase project.',
      'failed-precondition': 'Create the default Firestore database and publish the project rules.',
      'auth/operation-not-allowed': 'Email/password sign-in must be enabled in Firebase Authentication.',
      'auth/unauthorized-domain': 'This website address must be added to Firebase Authentication authorized domains.',
      'auth/invalid-api-key': 'Firebase configuration could not be accepted. Contact the project administrator.',
      'auth/user-disabled': 'This account is disabled. Contact your administrator.',
      'permission-denied': 'Profile access was denied. The project administrator must publish the Firestore rules.',
      'unavailable': 'The profile service is unavailable. Check the connection and Firestore setup.',
      'deadline-exceeded': 'Your workspace access check took too long. Retry or contact your administrator.',
      'auth/web-storage-unsupported': 'This browser cannot keep a sign-in session. Allow site storage and try again.'
    };
    return messages[error?.code] || 'Could not finish signing in. Check the connection and Firebase project setup, then retry.';
  },
  async initialize() {
    if (this.initializing) return this.initializing;
    this.phase = 'loading'; this.error = ''; this.notify();
    this.initializing = (async () => {
      try {
        if (!['http:', 'https:'].includes(location.protocol)) throw { code: 'local-file' };
        const imports = Promise.all([
          import('https://www.gstatic.com/firebasejs/13.0.0/firebase-app.js'),
          import('https://www.gstatic.com/firebasejs/13.0.0/firebase-auth.js'),
          import('https://www.gstatic.com/firebasejs/13.0.0/firebase-firestore.js')
        ]);
        let timeout;
        const modules = await Promise.race([imports, new Promise((_, reject) => { timeout = setTimeout(() => reject({code:'unavailable'}), 20000); })]).finally(() => clearTimeout(timeout));
        const [appSdk, authSdk, storeSdk] = modules;
        this.sdk = { ...authSdk, ...storeSdk };
        const app = appSdk.getApps().length ? appSdk.getApp() : appSdk.initializeApp(window.ACCESSREAPER_FIREBASE_CONFIG);
        this.auth = authSdk.getAuth(app); this.db = storeSdk.getFirestore(app,window.ACCESSREAPER_FIRESTORE_DATABASE);
        await authSdk.setPersistence(this.auth, authSdk.browserSessionPersistence);
        this.authStop?.(); this.profileStop?.();
        this.authStop = authSdk.onAuthStateChanged(this.auth, user => this.acceptUser(user), error => { this.phase='error'; this.error=this.message(error); this.notify(); });
      } catch (error) {
        this.phase = 'error';
        this.error = error?.code === 'local-file' ? 'Open this website through localhost or an HTTPS hosting address. Live sign-in cannot run from a file opened directly.' : this.message(error);
        this.notify();
      }
    })().finally(() => { this.initializing = null; });
    return this.initializing;
  },
  async profileRequest(request) {
    let timeout;
    try { return await Promise.race([request,new Promise((_,reject)=>{timeout=setTimeout(()=>reject({code:'deadline-exceeded'}),12000);})]); }
    finally { clearTimeout(timeout); }
  },
  async loadProfile(user) {
    if (this.profileLoad?.uid === user.uid) return this.profileLoad.promise;
    const promise = (async () => {
      const ref = this.sdk.doc(this.db, 'users', user.uid);
      let snapshot = await this.profileRequest(this.sdk.getDocFromServer(ref));
      if (!snapshot.exists()) {
        const name = (this.signupName || user.displayName || user.email?.split('@')[0] || 'Team member').slice(0,80);
        try {
          await this.profileRequest(this.sdk.setDoc(ref, { uid:user.uid, name, email:user.email, organizationId:'payhive-eng', role:'pending', status:'pending', createdAt:this.sdk.serverTimestamp() }));
        } catch (error) {
          // Another tab may have created the document. Never overwrite its role.
          if(error?.code!=='permission-denied'&&error?.code!=='already-exists')throw error;
          const existing = await this.profileRequest(this.sdk.getDocFromServer(ref));
          if (!existing.exists()) throw error;
        }
        snapshot = await this.profileRequest(this.sdk.getDocFromServer(ref));
      }
      if (!snapshot.exists()) throw {code:'unavailable'};
      return snapshot.data();
    })().finally(() => { if (this.profileLoad?.uid === user.uid) this.profileLoad = null; });
    this.profileLoad = {uid:user.uid,promise};
    return promise;
  },
  applyProfile(profile) {
    this.profile = profile;
    this.phase = profile?.uid === this.user?.uid && profile?.role === 'admin' && profile?.status === 'active' && ['acme', 'payhive-eng'].includes(profile?.organizationId) ? 'authorized' : 'pending';
    this.error = ''; this.notify();
  },
  async acceptUser(user) {
    const epoch = ++this.epoch;
    this.profileStop?.(); this.profileStop=null; this.user=user; this.profile=null;
    if (!user) { this.phase='signed-out'; this.error=''; this.notify(); return; }
    this.phase='checking-profile'; this.error=''; this.notify();
    try {
      const profile = await this.loadProfile(user);
      if (epoch !== this.epoch) return;
      this.applyProfile(profile);
      const ref = this.sdk.doc(this.db,'users',user.uid);
      this.profileStop = this.sdk.onSnapshot(ref,{includeMetadataChanges:true},snapshot=>{
        if (epoch !== this.epoch || snapshot.metadata.fromCache) return;
        if (!snapshot.exists()) { this.profile=null;this.phase='pending';this.notify();return; }
        this.applyProfile(snapshot.data());
      },error=>{ if(epoch!==this.epoch)return;this.profile=null;this.phase='error';this.error=this.message(error);this.notify(); });
    } catch(error) {
      if(epoch!==this.epoch)return;
      this.phase='error';this.error=this.message(error);this.notify();
    }
  },
  async signIn(email,password) { if(!this.auth)throw {code:'unavailable'};await this.sdk.signInWithEmailAndPassword(this.auth,email,password); },
  async signUp(name,email,password) {
    if(!this.auth)throw {code:'unavailable'};
    this.signupName=name;
    try { const credential=await this.sdk.createUserWithEmailAndPassword(this.auth,email,password);await this.sdk.updateProfile(credential.user,{displayName:name}); }
    finally { this.signupName=''; }
  },
  async resetPassword(email) { if(!this.auth)throw {code:'unavailable'};await this.sdk.sendPasswordResetEmail(this.auth,email); },
  async signOut() { if(!this.auth)return;await this.sdk.signOut(this.auth); },
  async refresh() { if(this.auth?.currentUser)await this.acceptUser(this.auth.currentUser);else await this.initialize(); }
};

window.FirebaseIdentity = FirebaseIdentity;
