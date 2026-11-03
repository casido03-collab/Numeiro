"""The pre-existing /app bind mount must contain the exact tested health patch."""
import hashlib
import json
import os
import sys

manifest = json.load(open('/usr/local/share/numeiro-runtime-hashes.json'))
for relative, expected in manifest.items():
    with open('/app/' + relative, 'rb') as source:
        if hashlib.sha256(source.read()).hexdigest() != expected:
            sys.exit('NUMEIRO_RUNTIME_SOURCE_MISMATCH')
os.execvp(sys.argv[1], sys.argv[1:])
