#!/usr/bin/env python3
from pathlib import Path

path = Path('sovereign-omega-v2/src/scale-os/control-plane.ts')
text = path.read_text(encoding='utf-8')
old = """    case 'REQUEST_CREATED':
    case 'VERIFICATION_RECORDED':
      throw new Error(`unreachable transition for ${eventType}`)
"""
if text.count(old) != 1:
    raise SystemExit('expected one unreachable transition block')
path.write_text(text.replace(old, ''), encoding='utf-8')
print('removed compiler-unreachable transition labels')
