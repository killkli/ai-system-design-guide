#!/usr/bin/env python3
import subprocess
import os

os.chdir('/Users/johnchen/ai-system-design-guide')

files = [
    '08-memory-and-state/05-semantic-caching.md',
    '08-memory-and-state/05-zep-and-temporal-graphs.md',
    '08-memory-and-state/06-state-management-patterns.md',
    '07-agentic-systems/05-agent-memory-and-state.md',
]

for f in files:
    subprocess.run(['git', 'add', f], check=True)
    commit_msg = f'[zh-TW] 翻譯：{f}'
    subprocess.run(['git', 'commit', '-m', commit_msg], check=True)

result = subprocess.run(['git', 'log', '--oneline', '-4'], capture_output=True, text=True)
print(result.stdout)
