#!/usr/bin/env python3
"""Disk-backed compositor fixture. Never talks to a real compositor."""
import json
import os
from pathlib import Path
import re
import sys

file = Path(os.environ['KEYBOARD_TEST_DEVICES'])
devices = json.loads(file.read_text())
args = sys.argv[1:]
if args and args[0] == '-j': args.pop(0)
command = args[0]
if command == 'devices':
    print(json.dumps({'keyboards': devices}))
elif command == 'configerrors':
    print('')
elif command == 'getoption':
    print(json.dumps({'str': '[[EMPTY]]'}))
elif command == 'eval':
    fields = dict(re.findall(r'(\w+)="([^"\\]*)"', args[1]))
    if set(fields) != {'name', 'kb_layout', 'kb_variant', 'kb_options'}:
        raise SystemExit('Unexpected fixture mutation')
    device = next(d for d in devices if d['name'] == fields['name'])
    for key in ('layout', 'variant', 'options'): device[key] = fields['kb_' + key]
    file.write_text(json.dumps(devices))
    print('ok')
elif command == 'switchxkblayout':
    next(d for d in devices if d['name'] == args[1])['active_layout_index'] = int(args[2])
    file.write_text(json.dumps(devices))
    print('ok')
elif command == 'reload':
    print('ok')
else:
    raise SystemExit('Unexpected fixture request')
