with open('D:/AccessReaper-v2/frontend/governance.js', 'r', encoding='utf-8') as f:
    text = f.read()

target = "${f.aiStatus==='success'?((f.aiModel&&f.aiModel.toLowerCase().includes('gemini'))?'Gemini \u2726':(f.aiModel&&f.aiModel.toLowerCase().includes('openai')&&!f.aiModel.toLowerCase().includes('groq'))?'OpenAI \u2726':'Groq \u2726'):'Template \u00b7 Preview'}"
replacement = "${f.aiStatus==='success'?((f.aiModel&&f.aiModel.toLowerCase().includes('gemini'))?'Gemini \u2726':'Groq \u2726'):'Template \u00b7 Preview'}"

assert target in text, "target string not found in governance.js"
updated = text.replace(target, replacement)
with open('D:/AccessReaper-v2/frontend/governance.js', 'w', encoding='utf-8') as f:
    f.write(updated)
print("Updated governance.js successfully.")
