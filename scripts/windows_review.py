"""First-party Windows portable review packaging. No model, signing or publication."""
import hashlib,json,os,re,shutil,subprocess,sys,tempfile,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRODUCTS={'EvidenceFlow','EvidenceCouncil','EvidenceAcademy','EvidenceLab','EvidenceBot'}
ENGINE='Godot_v4.7.2-stable_win64.exe.zip'
TEMPLATES='Godot_v4.7.2-stable_export_templates.tpz'
PINS={ENGINE:'83decd58fdf67b9d657958a1ae6bf1929c20785315a81effe245874cdc57acb709bf868e00778a96984338c1b29dafdb453c6847747694621c6ecf5da2259993',TEMPLATES:'ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079'}
GODOT_COMMIT='ed1daf0bf001b61586d9930840f2f1394092c079'
def digest_bytes(data):return hashlib.sha256(data).hexdigest()
def digest(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def archive_payload(payload,target,product,source):
 payload=Path(payload);target=Path(target)
 if product not in PRODUCTS or not re.fullmatch('[a-f0-9]{40}',source):raise ValueError('Exact product/source required')
 if target.exists():raise FileExistsError(target)
 dll='genesis_save.dll'
 allowed={product+'.exe',dll,'LICENSE.txt','THIRD-PARTY-NOTICES.txt','REVIEW-BUILD.txt'}
 files=sorted(p for p in payload.rglob('*') if p.is_file() or p.is_symlink())
 if any(p.is_symlink() for p in files) or {p.relative_to(payload).as_posix() for p in files}!=allowed:raise ValueError('Unexpected or missing payload files: '+repr(sorted(p.relative_to(payload).as_posix() for p in files)))
 rows=[{'path':p.relative_to(payload).as_posix(),'size':p.stat().st_size,'sha256':digest(p)} for p in files]
 manifest={'product':product,'version':'0.1.0-dev','platform':'windows-x64','sourceCommit':source,'publicationAuthorized':False,'bundledInference':False,'files':rows}
 with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in files:z.write(p,product+'/'+p.relative_to(payload).as_posix())
  z.writestr(product+'/build-manifest.json',json.dumps(manifest,indent=2)+'\n')
 return {'name':target.name,'size':target.stat().st_size,'sha256':digest(target),'manifest':manifest}
def verify_smoke_file(profile):
 files=list(Path(profile).rglob('package-smoke.json'))
 if len(files)!=1 or files[0].is_symlink() or json.loads(files[0].read_text(encoding='utf-8'))!={'package_smoke':True}:raise ValueError('No independently readable native persistence smoke output')
def download(name,folder):
 target=folder/name
 with urllib.request.urlopen('https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/'+name,timeout=180) as response,target.open('xb') as f:shutil.copyfileobj(response,f)
 with target.open('rb') as f:
  if hashlib.file_digest(f,'sha512').hexdigest()!=PINS[name]:raise ValueError('Pinned Godot checksum mismatch')
 return target
def run(command,env=None,marker=None,cwd=None,timeout=180):
 try:r=subprocess.run([str(x) for x in command],cwd=cwd or ROOT,env=env,text=True,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
 except subprocess.TimeoutExpired as error:
  output=error.stdout or b''
  print(output.decode('utf-8',errors='replace') if isinstance(output,bytes) else output,flush=True)
  raise RuntimeError('Native process timed out; captured diagnostics above') from None
 print(r.stdout)
 if r.returncode or 'SCRIPT ERROR' in r.stdout or 'ERROR:' in r.stdout or (marker and marker not in r.stdout):raise RuntimeError('Native export/smoke failed')
 return r.stdout
def main():
 if os.name!='nt':raise RuntimeError('Actual Windows required')
 product=ROOT.name
 if product not in PRODUCTS:raise ValueError('Unexpected product')
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if os.environ.get('GITHUB_SHA')!=source:raise ValueError('Workflow source mismatch')
 subprocess.run(['git','diff','--exit-code','HEAD','--'],cwd=ROOT,check=True,capture_output=True)
 tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0')
 out=ROOT/'build/windows-review';out.mkdir(parents=True,exist_ok=False)
 from build_save_adapter import build_adapter
 from windows_version import write_version,read_version
 with tempfile.TemporaryDirectory(prefix='evidence-windows-review-') as temp:
  temp=Path(temp);payload=temp/'payload';payload.mkdir()
  source_root=temp/'source'
  for name in filter(None,tracked):
   source_file=ROOT/name
   if source_file.is_symlink():raise ValueError('Tracked source symlink unsupported')
   destination=source_root/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source_file,destination)
  project=source_root if product=='EvidenceFlow' else source_root/'native'
  build_adapter(source_root/'native')
  with zipfile.ZipFile(download(ENGINE,temp)) as z:
   names=['Godot_v4.7.2-stable_win64.exe','Godot_v4.7.2-stable_win64_console.exe']
   for name in names:(temp/name).write_bytes(z.read(name))
  engine=temp/names[1]
  with zipfile.ZipFile(download(TEMPLATES,temp)) as z:(temp/'windows_release.exe').write_bytes(z.read('templates/windows_release_x86_64.exe'))
  template=temp/'windows_release.exe';write_version(template,'0.1.0')
  env=os.environ.copy();env['APPDATA']=str(temp/'profile');env['LOCALAPPDATA']=str(temp/'local-profile')
  (temp/'profile').mkdir();(temp/'local-profile').mkdir()
  run([engine,'--headless','--path',project,'--editor','--import','--quit'],env)
  # Override only this builder-owned preset; source content is checked again by storage.
  preset=project/'export_presets.cfg'
  original=preset.read_bytes() if preset.exists() else None
  preset.write_text('[preset.0]\nname="Windows Review"\nplatform="Windows Desktop"\nrunnable=true\nexport_filter="all_resources"\ninclude_filter=""\nexclude_filter="tests/*,docs/*,durability/*,native/durability/*,*.so,*.c,*.h,*.json,*.jsonl,*.db,*.sqlite*,*.key,*.pem,*.p12,*.pfx,*.keystore,*.jks"\n[preset.0.options]\ncustom_template/release='+json.dumps(str(template).replace('\\','/'))+'\nbinary_format/embed_pck=true\nbinary_format/architecture="x86_64"\ncodesign/enable=false\napplication/modify_resources=false\n',encoding='utf-8')
  try:run([engine,'--headless','--path',project,'--export-release','Windows Review',payload/(product+'.exe')],env)
  finally:
   if original is None:preset.unlink()
   else:preset.write_bytes(original)
  if read_version(payload/(product+'.exe'))!=(0,1,0,0):raise ValueError('Exported PE identity mismatch')
  shutil.copyfile(ROOT/'LICENSE',payload/'LICENSE.txt')
  url='https://raw.githubusercontent.com/godotengine/godot/'+GODOT_COMMIT+'/COPYRIGHT.txt'
  with urllib.request.urlopen(url,timeout=60) as response:(payload/'THIRD-PARTY-NOTICES.txt').write_bytes(response.read())
  (payload/'REVIEW-BUILD.txt').write_text(product+' 0.1.0-dev — WINDOWS REVIEW BUILD\nUnsigned, not a production release. Extract the complete folder, then run '+product+'.exe. No Python or Godot installation required.\nNo AI model or inference server is bundled. Local AI features require your separately configured loopback server; template/manual/DSP features remain available. No cloud fallback.\nAndroid, device acceptance, signing, product completeness and public publication remain open. Bot live Google acceptance UNRUN; Lab neural speech/cloning unimplemented.\nSource: '+source+'\n',encoding='utf-8')
  target=out/(product+'-Windows-x64-review.zip');report=archive_payload(payload,target,product,source)
  # Smoke the exact downloaded-shaped package, not source-tree libraries.
  extracted=temp/'extracted'
  with zipfile.ZipFile(target) as z:z.extractall(extracted)
  exe=extracted/product/(product+'.exe')
  smoke=run([exe,'--headless','--script','res://package_smoke.gd'],env,'PACKAGED_NATIVE_SAVE_AND_UI_PASS',extracted/product,timeout=40)
  verify_smoke_file(temp/'profile')
  run([exe,'--headless','--quit-after','5'],env,'Godot Engine',extracted/product)
  (out/'windows-smoke.log').write_text(smoke,encoding='utf-8')
  report.update(sourceCommit=source,packagedNativeSmoke=True,peVersion='0.1.0.0',godotSourceCommit=GODOT_COMMIT,publicationAuthorized=False)
  (out/'package-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
  print('WINDOWS_REVIEW_PACKAGE_PASS_JSON:'+json.dumps(report))
if __name__=='__main__':main()
