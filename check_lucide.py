import urllib.request, re

r = urllib.request.urlopen('https://unpkg.com/lucide@0.563.0/dist/umd/lucide.min.js')
data = r.read().decode('utf-8')

# Find all PascalCase icon exports
# In UMD, they're typically assigned like: a.IconName = [...]
# Let's find them by looking at the export pattern
# The pattern should be: a.SomeName=
exports = re.findall(r'a\.([A-Z][a-zA-Z0-9]+)\s*=', data)
print(f"Found {len(exports)} PascalCase exports")

# Show first 20
for e in exports[:20]:
    print(f"  {e}")

# Check specific ones we need
needed = {
    'play-circle': ['PlayCircle', 'CirclePlay'],
    'function': ['Function', 'FunctionSquare'],
    'variable': ['Variable'],
    'edit': ['Edit', 'Pencil', 'PencilLine', 'SquarePen'],
    'edit-3': ['Edit3', 'PenLine'],
    'x-circle': ['XCircle', 'CircleX'],
    'plus-circle': ['PlusCircle', 'CirclePlus'],
    'check-circle': ['CheckCircle', 'CircleCheck'],
    'help-circle': ['HelpCircle', 'CircleHelp'],
    'arrow-right-circle': ['ArrowRightCircle', 'CircleArrowRight'],
    'arrow-up-circle': ['ArrowUpCircle', 'CircleArrowUp'],
    'external-link': ['ExternalLink', 'SquareArrowOutUpRight'],
    'file-text': ['FileText', 'FileType'],
    'file-plus': ['FilePlus', 'FilePlus2'],
    'shield-check': ['ShieldCheck'],
    'check-square': ['CheckSquare', 'SquareCheck', 'SquareCheckBig'],
    'terminal': ['Terminal', 'TerminalSquare', 'SquareTerminal'],
    'save': ['Save'],
    'refresh-cw': ['RefreshCw', 'RefreshCcw'],
    'rotate-ccw': ['RotateCcw'],
    'trash-2': ['Trash2', 'Trash'],
    'fast-forward': ['FastForward'],
    'clock': ['Clock', 'Clock1', 'Clock2', 'Clock3', 'Clock4'],
    'zap': ['Zap'],
    'repeat': ['Repeat', 'Repeat1', 'Repeat2'],
    'layers': ['Layers', 'Layers2', 'Layers3'],
    'globe': ['Globe', 'Globe2'],
    'git-branch': ['GitBranch', 'GitBranchPlus'],
    'git-merge': ['GitMerge'],
    'alert-triangle': ['AlertTriangle', 'TriangleAlert'],
    'play': ['Play'],
    'code': ['Code', 'Code2', 'CodeXml'],
    'lock': ['Lock', 'LockKeyhole'],
    'search': ['Search'],
    'download': ['Download'],
    'eye': ['Eye'],
    'pause': ['Pause'],
}

print("\n=== Needed icon availability ===")
exports_set = set(exports)
for kebab, candidates in needed.items():
    found_candidates = [c for c in candidates if c in exports_set]
    if found_candidates:
        print(f"  {kebab}: FOUND as {found_candidates}")
    else:
        print(f"  {kebab}: ✗ NONE of {candidates} found")

# Now check how createIcons converts data-lucide to lookup key
# Find the 'su' function (the name converter)
idx = data.index('su(M)')
print(f"\n=== Around su(M) conversion at {idx} ===")
# Go back to find su definition
context = data[max(0,idx-500):idx+100]
print(context[-300:])
