path = r"D:\AccessReaper-v2\frontend\app.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = "if(b.id==='clear-filters'){Object.assign(state,{auditSegment:'all'"
replacement = """if(b.id==='toggle-advanced-filters'){state.showFilters=!state.showFilters;render();return;}
 if(b.id==='chip-filter-medium'){state.auditRisk=state.auditRisk==='Medium'?'All risks':'Medium';state.auditSegment='all';state.auditPage=1;render();return;}
 if(b.id==='clear-filters'){Object.assign(state,{auditSegment:'all'"""

if target in content:
    content = content.replace(target, replacement)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: Inserted toggle-advanced-filters into click listener")
else:
    print("TARGET NOT FOUND")
