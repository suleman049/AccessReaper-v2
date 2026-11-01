with open('D:/AccessReaper-v2/frontend/workspace-design.js', 'r', encoding='utf-8') as f:
    text = f.read()

target = '<span class="connection-state">Account profiles connected</span></div><p class="settings-footnote">'
replacement = '<span class="connection-state">Account profiles connected</span></div><div class="settings-service ai-explanations-service"><span class="service-icon">${uiIcon(\'audit\')}</span><div><strong>AI explanations</strong><small>Order: <span id="ai-provider-order">Groq \u2192 Gemini</span> \u00b7 Tokens today: <span id="ai-token-usage">0 / 200,000</span></small></div><span class="connection-state" id="ai-configured-status">Groq: Yes \u00b7 Gemini: No</span></div><p class="settings-footnote">'

assert target in text, "target not found in workspace-design.js"
updated = text.replace(target, replacement, 1)

with open('D:/AccessReaper-v2/frontend/workspace-design.js', 'w', encoding='utf-8') as f:
    f.write(updated)
print("Updated workspace-design.js successfully.")
