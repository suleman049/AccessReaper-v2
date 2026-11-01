with open(r"D:\AccessReaper-v2\frontend\app.js", "r", encoding="utf-8") as f:
    text = f.read()

count = text.count("clear-filters")
print("Occurrences of clear-filters:", count)
idx = 0
for i in range(count):
    idx = text.find("clear-filters", idx)
    print(f"Occurrence {i+1} at index {idx}:", repr(text[idx-30:idx+40]))
    idx += len("clear-filters")
