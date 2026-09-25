import json
import os
import sys
from pathlib import Path
assert os.environ['CURTAMAP_EXPERIMENT_DIR'].endswith('experimentos')
assert sys.argv[2] == 'argumento com espaços'
Path(sys.argv[1]).write_text(json.dumps({'ok': True, 'argument': sys.argv[2]}), encoding='utf-8')
