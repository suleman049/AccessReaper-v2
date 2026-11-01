with open(r"D:\AccessReaper-v2\frontend\index.html", "r", encoding="utf-8") as f:
    text = f.read()

target = """      <select class="form-control" id="req-duration-select">

        <option value="0" selected>Permanent Access</option>

        <option value="24">24 Hours (JIT Temporary Access)</option>"""

replacement = """      <select class="form-control" id="req-duration-select">

        <option value="0" selected>Permanent Access</option>

        <option value="0.0167">1 Minute (Live Demo)</option>

        <option value="0.0333">2 Minutes (Live Demo)</option>

        <option value="24">24 Hours (JIT Temporary Access)</option>"""

assert target in text, "target not found"
text = text.replace(target, replacement)
with open(r"D:\AccessReaper-v2\frontend\index.html", "w", encoding="utf-8") as f:
    f.write(text)
print("SUCCESS: updated req-duration-select in index.html")
