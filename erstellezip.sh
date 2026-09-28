#!/usr/bin/env bash
# Erstellt das freigegebene Basispaket ohne private Entwicklungsdaten.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 - "$SCRIPT_DIR" <<'PY'
from pathlib import Path
import re,sys,zipfile,os,tempfile
root=Path(sys.argv[1])
version=(root/'VERSION').read_text(encoding='utf-8').strip()
if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise SystemExit('Ungültige VERSION')
files=[root/name for name in ('checkweb.py','VERSION','README.md','CHANGELOG.md','LICENSE')]
files+=sorted((root/'modules').glob('*.py'))
files+=[root/'assets'/name for name in ('checkweb.png','report_watermark.png')]
for code in ('de','en'):
 files.append(root/'lang'/f'{code}.json')
 files.append(root/'help'/code/'index.html')
for path in files:
 if not path.is_file() or path.is_symlink():raise SystemExit(f'Fehlende oder verlinkte Paketdatei: {path}')
dist=root/'dist';dist.mkdir(exist_ok=True)
output=dist/f'checkweb-{version}.zip'
fd,tmp=tempfile.mkstemp(prefix='.checkweb-',suffix='.zip',dir=dist);os.close(fd)
try:
 with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
  for path in files:archive.write(path,Path(f'checkweb-{version}')/path.relative_to(root))
 with zipfile.ZipFile(tmp) as archive:
  if archive.testzip():raise SystemExit('ZIP-Prüfung fehlgeschlagen')
  expected={str(Path(f'checkweb-{version}')/path.relative_to(root)) for path in files}
  if set(archive.namelist())!=expected:raise SystemExit('Unerwarteter ZIP-Inhalt')
 os.chmod(tmp,0o644);os.replace(tmp,output)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
print(f'{output}: {len(files)} geprüfte Dateien; nur DE/EN, keine privaten Einstellungen oder Entwicklungsdateien.')
PY
