import re

with open('quiz_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace curly quotes with straight quotes
content = content.replace('\u201c', '"')  # left double quotation mark
content = content.replace('\u201d', '"')  # right double quotation mark
content = content.replace('\u2018', "'")  # left single quotation mark
content = content.replace('\u2019', "'")  # right single quotation mark

with open('quiz_system.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done fixing quotes')
