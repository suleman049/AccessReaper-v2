path = r"D:\AccessReaper-v2\frontend\app.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update render() to sync state.auditSegment with URL
target1 = "if(location.hash.includes('?')){const q=new URLSearchParams(location.hash.slice(location.hash.indexOf('?')+1));if(page==='audit'&&q.has('segment'))state.auditSegment=q.get('segment');}"
replacement1 = "if(page==='audit'){if(location.hash.includes('?')){const q=new URLSearchParams(location.hash.slice(location.hash.indexOf('?')+1));state.auditSegment=q.get('segment')||'all';}else{state.auditSegment='all';}}"

# 2. Update click listener for data-audit-segment
target2 = "if(b.matches('[data-audit-segment]')){state.auditSegment=b.dataset.auditSegment;state.auditPage=1;render();}"
replacement2 = "if(b.matches('[data-audit-segment]')){const seg=b.dataset.auditSegment;state.auditSegment=seg;state.auditPage=1;const targetHash=seg==='all'?'#audit':`#audit?segment=${encodeURIComponent(seg)}`;if(location.hash!==targetHash){location.hash=targetHash;return;}render();}"

# 3. Update clear-filters
target3 = "if(b.id==='clear-filters'){Object.assign(state,{auditSegment:'all',auditQuery:'',auditRisk:'All risks',auditAccess:'All access levels',auditSource:'All sources',auditUser:'All users',auditRepo:'All resources',auditAction:'All actions',auditPage:1});render();}"
replacement3 = "if(b.id==='clear-filters'){Object.assign(state,{auditSegment:'all',auditQuery:'',auditRisk:'All risks',auditAccess:'All access levels',auditSource:'All sources',auditUser:'All users',auditRepo:'All resources',auditAction:'All actions',auditPage:1});if(location.hash!=='#audit'){location.hash='#audit';return;}render();}"

assert target1 in content, "target1 not found"
assert target2 in content, "target2 not found"
assert target3 in content, "target3 not found"

content = content.replace(target1, replacement1)
content = content.replace(target2, replacement2)
content = content.replace(target3, replacement3)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: Patched app.js for segment routing and button synchronization")
