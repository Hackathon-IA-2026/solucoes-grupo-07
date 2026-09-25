import os
import subprocess

env = os.environ.copy()
for key in ('CURTAMAP_DATA_DIR', 'CURTAMAP_MODEL_DIR'):
    env.pop(key, None)
print('Validação isolada de Settings: uv run pytest; sem CURTAMAP_DATA_DIR/MODEL_DIR somente neste subprocesso.', flush=True)
raise SystemExit(subprocess.call(['uv', 'run', 'pytest'], env=env))
