"""Read-only transport/package acceptance for a pinned private review build.

Download into a fresh workspace, validate bytes before extraction/execution, then
exercise those downloaded Windows packages. No signing/publication/lock promotion.
"""
import hashlib,json,os,re,stat,subprocess,tempfile,unicodedata,zipfile,sys
from pathlib import Path


def sha256(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def safe_name(name):
 if not isinstance(name,str) or not name or len(name)>240 or unicodedata.normalize('NFC',name)!=name or '\\' in name or name.startswith('/'):
  raise ValueError('Unsafe archive path')
 for part in name.split('/'):
  if part in ('','.','..') or part[-1:] in (' ','.') or any(ord(c)<32 or c in ':<>"|?*' for c in part) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?',part,re.I):
   raise ValueError('Unsafe Windows archive path')
 return name


def zip_inventory(path):
 result=[];seen=set();total=0
 with zipfile.ZipFile(path) as archive:
  if not 0<len(archive.infolist())<=2000:raise ValueError('Archive member count exceeds bound')
  for info in archive.infolist():
   name=safe_name(info.orig_filename)
   if name!=info.filename:raise ValueError('Archive path normalization is refused')
   key=name.casefold();mode=stat.S_IFMT(info.external_attr>>16)
   if key in seen or info.external_attr&0x400 or info.is_dir() or mode not in (0,stat.S_IFREG) or info.flag_bits&1 or info.compress_type not in (0,8) or info.file_size>1024**3:
    raise ValueError('Unsafe or duplicate archive entry')
   seen.add(key);total+=info.file_size
   if total>2*1024**3:raise ValueError('Unpacked archive exceeds bound')
   with archive.open(info) as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
   result.append({'path':name,'size':info.file_size,'sha256':digest})
 return sorted(result,key=lambda row:row['path'])


def verify_downloads(root,assets):
 root=Path(root)
 if {path.name for path in root.iterdir()}!={row['name'] for row in assets}:raise ValueError('Downloaded asset inventory differs')
 for row in assets:
  name=safe_name(row['name']);path=root/name
  if '/' in name or path.is_symlink() or not path.is_file() or path.stat().st_size!=row['size'] or 'sha256:'+sha256(path)!=row['sha256']:
   raise ValueError('Downloaded asset size/SHA256 mismatch: '+name)


def verify_receipt(receipt,lock):
 if receipt.get('repository')!=lock['repository'] or receipt.get('sourceCommit')!=lock['sourceCommit'] or str(receipt.get('runId'))!=str(lock['runId']) or receipt.get('publicationAuthorized') is not False:
  raise ValueError('Downloaded receipt source identity differs')
 expected={row['name']:(row['size'],row['sha256']) for row in lock['assets'] if row['name']!='review-build.json'}
 actual={row['name']:(row['size'],'sha256:'+row['sha256']) for row in receipt.get('files',[])}
 if actual!=expected or len(actual)!=len(receipt.get('files',[])):raise ValueError('Receipt inventory differs from pinned assets')


def verify_payload(path,lock):
 inventory=zip_inventory(path);product=lock['product'];prefix=product+'/'
 with zipfile.ZipFile(path) as archive:
  info=archive.getinfo(prefix+'build-manifest.json')
  if info.file_size>32768:raise ValueError('Manifest exceeds bound')
  manifest=json.loads(archive.read(info))
 if (manifest.get('sourceCommit')!=lock['sourceCommit'] or manifest.get('product')!=product or manifest.get('version')!='0.1.0-dev' or manifest.get('platform')!='windows-x64' or manifest.get('publicationAuthorized') is not False or manifest.get('bundledInference') is not False):raise ValueError('Embedded manifest identity differs')
 allowed={product+'.exe','genesis_save.dll','LICENSE.txt','THIRD-PARTY-NOTICES.txt','REVIEW-BUILD.txt'}
 rows=manifest.get('files',[])
 if len(rows)!=5 or {r['path'] for r in rows}!=allowed:raise ValueError('Unexpected manifest inventory')
 actual={r['path']:(r['size'],r['sha256']) for r in inventory}
 expected={prefix+r['path']:(r['size'],r['sha256']) for r in rows}
 manifest_row=next(r for r in inventory if r['path']==prefix+'build-manifest.json')
 expected[manifest_row['path']]=(manifest_row['size'],manifest_row['sha256'])
 if actual!=expected:raise ValueError('Embedded manifest/actual archive bytes differ')
 return inventory


def main():
 root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
 from store_review_build import api,validate_repository,verify_release
 from windows_review import verify_smoke_file
 from windows_version import read_version
 lock=json.loads((root/'review/inspection-lock.json').read_text(encoding='utf-8'))
 if os.name!='nt' or os.environ.get('GITHUB_REPOSITORY')!=lock['repository'] or os.environ.get('GITHUB_REF')!='refs/heads/main':raise ValueError('Pinned first-party main Windows inspection required')
 validate_repository(api('repos/'+lock['repository']),lock['repository'])
 original=api('repos/'+lock['repository']+'/actions/runs/'+str(lock['runId']))
 if original.get('head_sha')!=lock['sourceCommit'] or original.get('conclusion')!='success':raise ValueError('Original source/run did not pass')
 release=api('repos/'+lock['repository']+'/releases/'+str(lock['release']['id']))
 if release.get('tag_name')!=lock['release']['tag']:raise ValueError('Pinned release tag differs')
 verify_release(release,[dict(a,sha256=a['sha256'].removeprefix('sha256:')) for a in lock['assets']],lock['sourceCommit'])
 with tempfile.TemporaryDirectory(prefix='portable-redownload-') as temp:
  temp=Path(temp);downloads=temp/'downloads';downloads.mkdir()
  subprocess.run(['gh','release','download',lock['release']['tag'],'--repo',lock['repository'],'--dir',str(downloads)],check=True)
  verify_downloads(downloads,lock['assets']);verify_receipt(json.loads((downloads/'review-build.json').read_text(encoding='utf-8')),lock)
  archive=downloads/(lock['product']+'-Windows-x64-review.zip');inventory=verify_payload(archive,lock)
  unpacked=temp/'unpacked'
  with zipfile.ZipFile(archive) as zipped:zipped.extractall(unpacked)
  folder=unpacked/lock['product'];exe=folder/(lock['product']+'.exe')
  if read_version(exe)!=(0,1,0,0):raise ValueError('Downloaded PE version differs')
  env=os.environ.copy()
  for key in ('GH_TOKEN','GITHUB_TOKEN'):env.pop(key,None)
  env['APPDATA']=str(temp/'profile');env['LOCALAPPDATA']=str(temp/'local-profile')
  (temp/'profile').mkdir();(temp/'local-profile').mkdir()
  result=subprocess.run([str(exe),'--headless','--','--package-smoke'],cwd=folder,env=env,text=True,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
  print(result.stdout)
  if result.returncode or 'PACKAGED_NATIVE_SAVE_AND_UI_PASS' not in result.stdout or 'ERROR:' in result.stdout:raise RuntimeError('Downloaded native/UI smoke failed')
  verify_smoke_file(temp/'profile')
  proof={'repository':lock['repository'],'sourceCommit':lock['sourceCommit'],'originalRunId':lock['runId'],'inspectionRunId':os.environ['GITHUB_RUN_ID'],'releaseId':lock['release']['id'],'assetsVerified':len(lock['assets']),'zipFiles':len(inventory),'manifestByteParity':True,'downloadedNativeSaveReadAndUi':True,'headlessUiInitialization':True,'renderedUiAcceptance':'UNRUN','downloadedPeVersion':'0.1.0.0','archiveSha256':sha256(archive),'publicationAuthorized':False,'androidAcceptance':'UNRUN','productionSigningAcceptance':'UNRUN','physicalTargetAcceptance':'UNRUN','bundledInference':False}
  print('PORTABLE_REDOWNLOAD_INSPECTION_JSON:'+json.dumps(proof,sort_keys=True))
if __name__=='__main__':main()
