# Firebase setup — AccessReaper

## Abhi kya connected hai?

- Real Firebase email/password login, signup, password-reset email aur sign out.
- `users/{uid}` se own profile aur workspace-role authorization.
- Naya account `role: pending`, `status: pending` hota hai. User khud Admin nahi ban sakta.
- Sirf `role: admin`, `status: active`, `organizationId: acme` profile ko dashboard access milta hai.
- Role update/revocation ko profile listener receive karta hai; access unavailable hone par dashboard hide hota hai.
- Audit findings, recommendations, approvals aur reports abhi local DRY_RUN data hain. GitHub/Firestore application permissions change nahi hotin.

## 1. Email/password enable karein

Firebase Console mein **accessreaper** project select karein:

**Authentication → Sign-in method → Email/Password → Enable → Save**.

**Authentication → Settings → Authorized domains** mein `localhost` add karein (sirf naam; `http://` ya port nahi). Agar `127.0.0.1` address use karte hain to woh domain bhi add karein. Hosting ke waqt apna actual domain add karna hoga.

## 2. Firestore banayein aur rules publish karein

1. Database ab provision ho chuki hai: **accessreaper-profiles**, Mumbai (**asia-south1**), Enterprise native mode. Nayi database banane ki zaroorat nahi. Console mein isi named database ko select karein.
2. Firestore web access aur real-time updates enabled hain. MongoDB-compatible access disabled hai. Real-time own-document listener role changes/revocation ke liye required hai; koi collection query/pipeline use nahi hoti.
3. Repository ki `firestore.rules` file Notepad/editor mein kholein aur poora text copy karein.
4. Console mein **Firestore Database → Rules** par woh rules paste karke **Publish** karein.

Ye rules users ko sirf apna profile read karne aur pending profile create karne dete hain. Client se role/status update, profile delete aur user listing allowed nahi. Baqi collections deny hain, kyunki audit backend abhi connected nahi. Agar project mein pehle se doosre apps/collections hain, unke required rules ke saath carefully merge karein.

Email/Password provider aur profile database rules deployment configure ki gayi hai. Website https://accessreaper.web.app par host hoti hai.

## 3. Website kholein

1. Repository mein **Start-AccessReaper.cmd** double-click karein.
2. Server wali window open rehne dein.
3. Browser mein **http://localhost:4173/#login** kholein.

Node.js required hai; is computer par available hai. Koi npm package install karna zaroori nahi. Internet Firebase SDK aur live authentication ke liye required hai. Direct double-click se `file:///...` page kholna live authentication ke liye supported nahi.

Alternative terminal command: `node serve.cjs`.

## 4. Pehla Admin activate karein

1. Website par **Sign up** se apna account banayein.
2. Account banne ke baad **Workspace access pending** dikhega. Ye expected hai.
3. Firebase Console → **Authentication → Users** mein apne email ka **User UID** copy karein.
4. **Firestore Database → accessreaper-profiles → Data → users → woh UID** kholein.
5. Usi existing document mein ye fields update karein:

```text
role: admin          (string)
status: active       (string)
organizationId: acme (string; already present)
```

`uid`, `name`, `email`, `createdAt` ko delete na karein. Email ko document ID na banayein; Firebase UID use hoti hai.

6. Website mein **Check access again** click karein. Profile listener bhi server change receive karta hai.

Agar `users/{uid}` document nahi bana, pehle Firestore rules/accessreaper-profiles database check karein, phir **Check access again** click karein. Role kabhi browser/localStorage se assign nahi hota.

## 5. Session aur credentials

Session same browser tab mein reload par restore hota hai; tab close hone par browser-session sign-in end hota hai. Sign out Settings mein hai. Firebase credentials manage karta hai; app password/token ko audit records mein save ya screen par display nahi karti. Web `firebase-config.js` public app identifiers ke liye hai; service-account/private keys usmein nahi honi chahiye. Analytics initialize nahi kiya gaya.

## Important boundaries

Client route checks sirf screen access control hain. Actual Firestore protection published Security Rules provide karti hain. Future FastAPI endpoints ko Firebase ID tokens aur organization/role server-side verify karna hoga. Current repository mein live audit endpoints nahi hain.

Local sample audit data browser mein shared demo dataset hai; real confidential organization data is store mein import na karein. Sample reset Firebase users ya cloud profiles delete nahi karta.

## Troubleshooting

- **Email/password must be enabled:** Authentication provider enable karein.
- **Profile access denied:** `firestore.rules` publish karein.
- **Profile service unavailable:** internet aur accessreaper-profiles database check karein.
- **Workspace access pending:** apne UID document par Admin/active fields confirm karein.
- **Direct file error:** `Start-AccessReaper.cmd` aur localhost URL use karein.
- **Port already in use:** purani server window close karein; phir launch karein.

Live signup, login, logout, reload session, pending profile, invalid credentials, duplicate signup aur self-promotion restrictions test kiye gaye. Password-reset UI stub ke saath test hui; actual email delivery aur kisi real user ki Admin activation test nahi ki gayi.

Official references:
- https://firebase.google.com/docs/auth/web/password-auth
- https://firebase.google.com/docs/auth/web/manage-users
- https://firebase.google.com/docs/firestore/security/rules-conditions
- https://firebase.google.com/docs/web/alt-setup
