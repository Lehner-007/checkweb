from pathlib import Path
import os,hashlib,subprocess,shutil,gzip,json
root=Path(__file__).resolve().parent.parent
import tempfile
build_parent=root/'dist'
if not build_parent.is_dir() or build_parent.is_symlink(): raise SystemExit('Beauftragter Ausgabeordner dist fehlt oder ist verlinkt.')
work=Path(tempfile.mkdtemp(prefix='checkweb-deb-',dir=build_parent))
stage=work/'paket';stage.mkdir()
version=(root/'VERSION').read_text().strip()
import re
if not re.fullmatch(r'\d+\.\d+\.\d+', version): raise SystemExit('Ungültige VERSION')
app=stage/'usr/share/checkweb';app.mkdir(parents=True)
files=[root/'checkweb.py',root/'VERSION',*sorted((root/'modules').glob('*.py')),*[root/'assets'/n for n in ['checkweb.png','report_watermark.png']],*[root/'lang'/f'{c}.json' for c in ['de','en']],*[root/'help'/c/'index.html' for c in ['de','en']]]
manifest={}
for src in files:
 assert src.is_file() and not src.is_symlink()
 rel=src.relative_to(root);dst=app/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);manifest[str(rel)]=hashlib.sha256(src.read_bytes()).hexdigest()
doc=stage/'usr/share/doc/checkweb';doc.mkdir(parents=True)
shutil.copyfile(root/'LICENSE',doc/'copyright')
for name in ['README.md','CHANGELOG.md']:
 (doc/(name+'.gz')).write_bytes(gzip.compress((root/name).read_bytes(),mtime=0))
binpath=stage/'usr/bin/checkweb';binpath.parent.mkdir(parents=True)
binpath.write_text('#!/bin/sh\nunset CHECKWEB_DEV\nexec /usr/bin/python3 -B /usr/share/checkweb/checkweb.py "$@"\n')
apps=stage/'usr/share/applications';apps.mkdir(parents=True)
(apps/'checkweb.desktop').write_text('''[Desktop Entry]
Type=Application
Name=Checkweb
GenericName=Website checker
GenericName[de]=Webseitenprüfung
Comment=Check local and online websites
Comment[de]=Lokale und Online-Webseiten prüfen
Exec=checkweb
Icon=/usr/share/checkweb/assets/checkweb.png
Terminal=false
Categories=Development;WebDevelopment;
Keywords=HTML;CSS;Web;Website;
StartupNotify=true
''')
icon=stage/'usr/share/icons/hicolor/256x256/apps/checkweb.png';icon.parent.mkdir(parents=True)
from PIL import Image
with Image.open(root/'assets/checkweb.png') as im:
 im.resize((256,256),Image.Resampling.LANCZOS).save(icon)
for p in stage.rglob('*'):p.chmod(0o755 if p.is_dir() else 0o644)
binpath.chmod(0o755)
cleanup=stage/'usr/bin/checkweb-cleanup'
shutil.copyfile(root/'packaging/desktop_lifecycle.py',cleanup)
cleanup.chmod(0o755)
control=stage/'DEBIAN';control.mkdir()
size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
(control/'control').write_text(f'''Package: checkweb
Version: {version}
Section: web
Priority: optional
Architecture: all
Maintainer: Josef
Installed-Size: {(size+1023)//1024}
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.8), python3-bs4, python3-requests, python3-html5lib, util-linux
Recommends: python3-tinycss2, python3-lxml, python3-pil, php-cli, nodejs
Description: Local and online website diagnostics with GTK 4
 Checks websites and creates HTML or JSON reports.
 Includes German and English user interfaces and offline help.
''')
(control/'md5sums').write_text(''.join(f'{hashlib.md5(p.read_bytes()).hexdigest()}  {p.relative_to(stage)}\n' for p in sorted(stage.rglob('*')) if p.is_file() and control not in p.parents))
for p in control.iterdir():p.chmod(0o644)
for hook in ('postinst','prerm','postrm'):
 dst=control/hook
 source=(root/'packaging/desktop_lifecycle.py').read_text()
 if hook=='postinst': source=source.replace("action not in ('configure', 'remove', 'purge')", "action != 'configure'")
 elif hook=='prerm': source=source.replace("action not in ('configure', 'remove', 'purge')", "action not in ('remove', 'purge')")
 else: source=source.replace("action not in ('configure', 'remove', 'purge')", "action != 'purge'")
 dst.write_text(source);dst.chmod(0o755)
(work/'manifest.json').write_text(json.dumps(manifest,indent=2))
output=root/'dist'/f'checkweb_{version}_all.deb'
output.parent.mkdir(exist_ok=True)
if output.exists():
 backup=root/'dist'/f'checkweb_{version}_all-vor-reparatur.deb'
 if not backup.exists(): shutil.copy2(output,backup)
subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(output)],check=True)
subprocess.run(['dpkg-deb','--info',str(output)],check=True,stdout=subprocess.DEVNULL)
shutil.rmtree(work)
print(output)
