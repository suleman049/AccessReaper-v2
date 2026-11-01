with open(r'D:\AccessReaper-v2\frontend\users-page.js', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add peopleFilter to UsersPage definition
if "peopleFilter:" not in code:
    code = code.replace(
        '  activeTab: "users", // "users" or "people"\n',
        '  activeTab: "users", // "users" or "people"\n  peopleFilter: "all", // "all", "active", "contractor", "former"\n'
    )
    print("Added peopleFilter property")

# 2. Update renderPeopleTab filtering
old_filter_block = """    const q = this.peopleSearch.toLowerCase().trim();
    const filtered = (this.people || []).filter(p => {
      const matchText = `${p.name} ${p.email} ${p.team} ${p.job_role} ${p.github_login || ""}`.toLowerCase();
      return !q || matchText.includes(q);
    });"""

new_filter_block = """    const q = this.peopleSearch.toLowerCase().trim();
    const filter = this.peopleFilter || 'all';
    const filtered = (this.people || []).filter(p => {
      if (filter === 'active' && p.employment_status !== 'active') return false;
      if (filter === 'contractor' && p.employment_status !== 'contractor' && !(p.job_role || '').toLowerCase().includes('contractor') && p.team !== 'External') return false;
      if (filter === 'former' && p.employment_status !== 'former') return false;
      const matchText = `${p.name} ${p.email} ${p.team} ${p.job_role} ${p.github_login || ""}`.toLowerCase();
      return !q || matchText.includes(q);
    });"""

old_filter_norm = old_filter_block.replace('\r\n', '\n')
code_norm = code.replace('\r\n', '\n')

if old_filter_norm in code_norm:
    code_norm = code_norm.replace(old_filter_norm, new_filter_block)
    print("Updated renderPeopleTab filtering logic")
else:
    print("ERROR: old_filter_block not found in users-page.js")

# 3. Add Filter Pills HTML to renderPeopleTab
old_tools_card = """      <div class="card users-tools-card mb-3">
        <div class="d-flex align-items-center gap-2">
          <button type="button" class="btn btn-primary btn-sm" id="btn-add-person">
            + Add Person
          </button>
          <button type="button" class="btn btn-outline btn-sm" id="btn-people-import-csv">
            📁 Import CSV
          </button>
        </div>"""

new_tools_card = """      <div class="card users-tools-card mb-3">
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <button type="button" class="btn btn-primary btn-sm" id="btn-add-person">
            + Add Person
          </button>
          <button type="button" class="btn btn-outline btn-sm" id="btn-people-import-csv">
            📁 Import CSV
          </button>
          <div class="ms-md-3 d-flex align-items-center gap-1 flex-wrap">
            <button type="button" class="btn btn-sm ${filter === 'all' ? 'btn-primary' : 'btn-outline'}" data-people-filter="all" style="border-radius:16px;font-size:12px;font-weight:600;">
              All (${(this.people||[]).length})
            </button>
            <button type="button" class="btn btn-sm ${filter === 'active' ? 'btn-primary' : 'btn-outline'}" data-people-filter="active" style="border-radius:16px;font-size:12px;font-weight:600;">
              Active Employees (${(this.people||[]).filter(p => p.employment_status === 'active').length})
            </button>
            <button type="button" class="btn btn-sm ${filter === 'contractor' ? 'btn-primary' : 'btn-outline'}" data-people-filter="contractor" style="border-radius:16px;font-size:12px;font-weight:600;">
              Contractors (${(this.people||[]).filter(p => p.employment_status === 'contractor' || p.team === 'External' || (p.job_role || '').toLowerCase().includes('contractor')).length})
            </button>
            <button type="button" class="btn btn-sm ${filter === 'former' ? 'btn-primary' : 'btn-outline'}" data-people-filter="former" style="border-radius:16px;font-size:12px;font-weight:600;${filter === 'former' ? 'background:#ef4444;border-color:#ef4444;' : ''}">
              Offboarded (${(this.people||[]).filter(p => p.employment_status === 'former').length})
            </button>
          </div>
        </div>"""

old_tools_norm = old_tools_card.replace('\r\n', '\n')
if old_tools_norm in code_norm:
    code_norm = code_norm.replace(old_tools_norm, new_tools_card)
    print("Added People filter pills to users-tools-card")
else:
    print("ERROR: old_tools_card not found in users-page.js")

# 4. Attach click listener for data-people-filter
attach_marker = """    // Search input
    const peopleSearch = container.querySelector("#people-search");"""

people_filter_attach = """    // People filter pills
    container.querySelectorAll("[data-people-filter]").forEach(btn => {
      btn.addEventListener("click", () => {
        this.peopleFilter = btn.dataset.peopleFilter;
        if (typeof render === "function") render();
      });
    });

    // Search input
    const peopleSearch = container.querySelector("#people-search");"""

attach_marker_norm = attach_marker.replace('\r\n', '\n')
if attach_marker_norm in code_norm:
    code_norm = code_norm.replace(attach_marker_norm, people_filter_attach)
    print("Attached click listeners for data-people-filter")
else:
    print("Warning: attach_marker not found, checking search input")

with open(r'D:\AccessReaper-v2\frontend\users-page.js', 'w', encoding='utf-8') as f:
    f.write(code_norm)

print("Updated users-page.js successfully!")
