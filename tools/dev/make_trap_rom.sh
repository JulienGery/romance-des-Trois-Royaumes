#!/bin/sh
# work/rom/game_trap.cxi = the ORIGINAL game with every candidate cavity filled with an undefined-instruction trap (no hooks): play it in
# `zakuro game_trap.cxi --interpreter 2> /tmp/zakuro.log`; any line "undefined instruction 0xE7F000F0" means a cavity function is really used
# (then: cavity_update.py /tmp/zakuro.log)
cd "$(dirname "$0")/../.."
python3 - <<'PY'
import json, subprocess
c = json.load(open('data/cavities.json'))
r = subprocess.run(['python3', 'tools/dev/cavity_probe.py'] + [f'{a:x}-{b:x}' for a, b in c], capture_output=True, text=True)
print((r.stdout or r.stderr)[-100:])
PY
mv work/rom/game_p.cxi work/rom/game_trap.cxi && echo "OK -> work/rom/game_trap.cxi"
