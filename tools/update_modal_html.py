path = r"D:\AccessReaper-v2\frontend\index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = """  <div class="modal fade" id="request-modal" tabindex="-1" aria-hidden="true"><div class="modal-dialog modal-dialog-centered"><div class="modal-content review-modal-content" style="padding:24px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;"><h3 style="margin:0;font-size:18px;font-weight:700;">Submit Access Request</h3><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div><p style="font-size:13px;color:var(--muted);margin-bottom:20px;">Request access to a GitHub repository in <strong>payhive-eng</strong>. Once approved by an administrator, permissions will be granted live on GitHub and the user notified via email.</p><form id="access-request-form"><div class="mb-3"><label class="form-label" style="font-size:13px;font-weight:600;">Employee / User</label><select class="form-control" id="req-user-select" required></select></div><div class="mb-3"><label class="form-label" style="font-size:13px;font-weight:600;">Target GitHub Repository</label><select class="form-control" id="req-repo-select" required></select></div><div class="mb-3"><label class="form-label" style="font-size:13px;font-weight:600;">Requested Permission Level</label><select class="form-control" id="req-access-select" required><option value="Write" selected>Write (Contributor / Developer)</option><option value="Read">Read (Auditor / Viewer)</option><option value="Admin">Admin (Lead / Architect)</option></select></div><div class="mb-3"><label class="form-label" style="font-size:13px;font-weight:600;">Access Duration (Just-In-Time JIT)</label><select class="form-control" id="req-duration-select"><option value="0" selected>Permanent Access</option><option value="24">⏱️ 24 Hours (JIT Temporary Access)</option><option value="72">⏱️ 3 Days (JIT Temporary Access)</option><option value="168">⏱️ 7 Days (JIT Temporary Access)</option></select><small style="font-size:11px;color:var(--muted);display:block;margin-top:4px;">JIT access is automatically revoked from GitHub when duration expires.</small></div><div class="mb-3"><label class="form-label" style="font-size:13px;font-weight:600;">Business Justification</label><textarea class="form-control" id="req-reason-input" rows="3" placeholder="Explain why repository permissions are needed..." required></textarea></div><div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;"><button type="button" class="btn btn-outline" data-bs-dismiss="modal">Cancel</button><button type="submit" class="btn btn-primary" id="req-submit-btn">Submit Request</button></div></form></div></div></div>"""

replacement = """  <div class="modal fade" id="request-modal" tabindex="-1" aria-hidden="true"><div class="modal-dialog modal-dialog-centered"><div class="modal-content review-modal-content" style="padding:24px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;"><h3 style="margin:0;font-size:18px;font-weight:700;">Employee Access Request</h3><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div><p style="font-size:13px;color:var(--muted);margin-bottom:16px;">Request repository permissions for existing team members or onboard a new hire. Approving provisions them directly on GitHub with real-time audit logging.</p><form id="access-request-form">
    <div style="display:flex;background:var(--bg-subtle, #f1f5f9);padding:4px;border-radius:8px;margin-bottom:16px;gap:4px;">
      <button type="button" class="btn btn-sm req-tab-btn active" id="tab-existing-user" style="flex:1;border-radius:6px;font-weight:600;font-size:12px;background:#ff4d1f;color:#fff;">Existing Team Member</button>
      <button type="button" class="btn btn-sm req-tab-btn" id="tab-new-user" style="flex:1;border-radius:6px;font-weight:600;font-size:12px;background:transparent;color:var(--text, #334155);">⚡ New Employee / GitHub User</button>
    </div>
    <div id="section-existing-user" class="mb-3">
      <label class="form-label" style="font-size:13px;font-weight:600;">Select Employee</label>
      <select class="form-control" id="req-user-select"></select>
    </div>
    <div id="section-new-user" class="mb-3" style="display:none;">
      <div class="mb-2">
        <label class="form-label" style="font-size:13px;font-weight:600;">GitHub Handle <span class="text-danger">*</span></label>
        <input type="text" class="form-control" id="req-github-input" placeholder="e.g. suleman049 or @octocat" />
        <small style="font-size:11px;color:var(--muted);display:block;margin-top:2px;">Target account on GitHub where collaborator permissions will be granted upon admin approval.</small>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-6">
          <label class="form-label" style="font-size:12px;font-weight:600;">Full Name</label>
          <input type="text" class="form-control form-control-sm" id="req-new-name-input" placeholder="e.g. John Doe" />
        </div>
        <div class="col-6">
          <label class="form-label" style="font-size:12px;font-weight:600;">Work Email</label>
          <input type="email" class="form-control form-control-sm" id="req-new-email-input" placeholder="e.g. jdoe@payhive.internal" />
        </div>
      </div>
      <div id="req-detected-wrapper" style="display:none;margin-top:6px;">
        <label class="form-label" style="font-size:11px;font-weight:600;color:var(--muted);">Or select an unmapped collaborator found in your GitHub organization:</label>
        <select class="form-control form-control-sm" id="req-detected-select">
          <option value="">-- Choose detected GitHub collaborator --</option>
        </select>
      </div>
    </div>
    <div class="mb-3">
      <label class="form-label" style="font-size:13px;font-weight:600;">Target GitHub Repository</label>
      <select class="form-control" id="req-repo-select" required></select>
    </div>
    <div class="mb-3">
      <label class="form-label" style="font-size:13px;font-weight:600;">Requested Permission Level</label>
      <select class="form-control" id="req-access-select" required>
        <option value="Write" selected>Write (Contributor / Developer)</option>
        <option value="Read">Read (Auditor / Viewer)</option>
        <option value="Admin">Admin (Lead / Architect)</option>
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label" style="font-size:13px;font-weight:600;">Access Duration (Just-In-Time JIT)</label>
      <select class="form-control" id="req-duration-select">
        <option value="0" selected>Permanent Access</option>
        <option value="24">⏱️ 24 Hours (JIT Temporary Access)</option>
        <option value="72">⏱️ 3 Days (JIT Temporary Access)</option>
        <option value="168">⏱️ 7 Days (JIT Temporary Access)</option>
      </select>
      <small style="font-size:11px;color:var(--muted);display:block;margin-top:4px;">JIT access is automatically revoked from GitHub when duration expires.</small>
    </div>
    <div class="mb-3">
      <label class="form-label" style="font-size:13px;font-weight:600;">Business Justification</label>
      <textarea class="form-control" id="req-reason-input" rows="3" placeholder="Explain why repository permissions are needed..." required></textarea>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
      <button type="button" class="btn btn-outline" data-bs-dismiss="modal">Cancel</button>
      <button type="submit" class="btn btn-primary" id="req-submit-btn">Submit Request</button>
    </div>
  </form></div></div></div>"""

norm_content = content.replace("\r\n", "\n")
norm_target = target.replace("\r\n", "\n")
norm_replacement = replacement.replace("\r\n", "\n")

if norm_target in norm_content:
    new_content = norm_content.replace(norm_target, norm_replacement).replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("SUCCESS: Updated index.html with new employee access request modal!")
else:
    print("ERROR: Target not found in index.html")
