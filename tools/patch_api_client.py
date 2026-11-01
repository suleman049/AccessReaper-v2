with open(r"D:\AccessReaper-v2\frontend\api-client.js", "r", encoding="utf-8") as f:
    text = f.read()

target = """  async updateAutomationConfig(config) {
    return await this.request("/api/automation/config", {
      method: "PUT",
      body: config,
    });
  },"""

replacement = """  async updateAutomationConfig(config) {
    return await this.request("/api/automation/config", {
      method: "PUT",
      body: config,
    });
  },

  // --- Auto-Pilot Mode ---
  async getAutoPilot() {
    return await this.request("/api/automation/autopilot");
  },

  async updateAutoPilot(enabled) {
    return await this.request("/api/automation/autopilot", {
      method: "PUT",
      body: { enabled },
    });
  },

  async enforceAutoPilot() {
    return await this.request("/api/automation/autopilot/enforce", {
      method: "POST",
    });
  },"""

assert target in text, "target not found in api-client.js"
text = text.replace(target, replacement)
with open(r"D:\AccessReaper-v2\frontend\api-client.js", "w", encoding="utf-8") as f:
    f.write(text)
print("SUCCESS: patched api-client.js")
