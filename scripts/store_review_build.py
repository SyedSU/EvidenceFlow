"""Store tested build bytes in a private draft for repository writers. Never publish/sign.

Requires the runner's scoped GH_TOKEN only during this step. No external Python
dependencies, deletion, release editing, asset overwrite or production endpoints.
"""
import hashlib,json,os,re,subprocess
from pathlib import Path

PRODUCTS={'SyedSU/EvidenceFlow': 'evidenceflow', 'SyedSU/EvidenceCouncil': 'evidencecouncil', 'SyedSU/EvidenceAcademy': 'evidenceacademy', 'SyedSU/EvidenceLab': 'evidencelab', 'SyedSU/EvidenceBot': 'evidencebot'}


def plan(root,environment):
 repo=environment.get('GITHUB_REPOSITORY');sha=environment.get('GITHUB_SHA','')
 run=environment.get('GITHUB_RUN_ID','');attempt=environment.get('GITHUB_RUN_ATTEMPT','')
 if repo not in PRODUCTS or environment.get('GITHUB_REF')!='refs/heads/main' or environment.get('GITHUB_EVENT_NAME') not in ('push','workflow_dispatch'):
  raise ValueError('Only first-party main builds can store review drafts')
 if not re.fullmatch('[a-f0-9]{40}',sha) or not re.fullmatch('[1-9][0-9]*',run) or not re.fullmatch('[1-9][0-9]*',attempt):
  raise ValueError('Immutable source/run/attempt identity required')
 root=Path(root).resolve();product=PRODUCTS[repo]
 patterns=['build/windows-review/EvidenceFlow-Windows-x64-review.zip','build/windows-review/package-report.json','build/windows-review/windows-smoke.log']
 files=[]
 for pattern in patterns:
  matches=list(root.glob(pattern))
  if len(matches)!=1:raise ValueError('Missing or ambiguous output: '+pattern)
  files.extend(matches)
 if product=='hub':files.extend(sorted(root.glob('artifacts/windows-*.png')))
 records=[]
 for path in files:
  if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root) or not 0<path.stat().st_size<2*1024**3:
   raise ValueError('Expected bounded regular build output')
  with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
  records.append({'name':path.name,'path':path.relative_to(root).as_posix(),'size':path.stat().st_size,'sha256':digest})
 if len({row['name'] for row in records})!=len(records):raise ValueError('Duplicate asset filenames')
 return {'repository':repo,'product':product,'sourceCommit':sha,'runId':run,'attempt':attempt,
         'tag':f'review-{product}-{sha}-{run}-{attempt}','publicationAuthorized':False,'files':records}


def validate_repository(metadata,repo):
 if metadata.get('full_name')!=repo or metadata.get('private') is not True:
  raise ValueError('Review storage requires the exact private repository')


def verify_release(release,files,sha):
 if release.get('draft') is not True or release.get('prerelease') is not True or release.get('target_commitish')!=sha:
  raise ValueError('Review release changed visibility/type/source identity')
 assets=release.get('assets',[])
 if len(assets)!=len(files) or len({row['name'] for row in assets})!=len(files):raise ValueError('Release asset inventory mismatch')
 by_name={row['name']:row for row in assets}
 for row in files:
  asset=by_name.get(row['name'],{})
  if asset.get('size')!=row['size'] or asset.get('digest')!='sha256:'+row['sha256']:
   raise ValueError('Server asset size/digest mismatch: '+row['name'])


def api(endpoint,payload=None):
 args=['gh','api',endpoint]
 if payload is not None:args+=['--method','POST','--input','-']
 try:
  result=subprocess.run(args,input=json.dumps(payload) if payload is not None else None,text=True,encoding='utf-8',capture_output=True,check=True)
 except subprocess.CalledProcessError as error:
  diagnostic=error.stderr or 'No server diagnostic returned'
  for key in ('GH_TOKEN','GITHUB_TOKEN'):
   token=os.environ.get(key,'')
   if token:diagnostic=diagnostic.replace(token,'[redacted]')
  raise RuntimeError('GitHub API failed: '+json.dumps(diagnostic[:2000],ensure_ascii=True)) from None
 return json.loads(result.stdout)


def main():
 root=Path(__file__).resolve().parents[1];record=plan(root,os.environ)
 sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
 if sha!=record['sourceCommit']:raise ValueError('Checkout differs from workflow source')
 subprocess.run(['git','diff','--exit-code','HEAD','--'],cwd=root,check=True,capture_output=True)
 repo=record['repository'];validate_repository(api('repos/'+repo),repo)
 folder=root/'build/windows-review'
 receipt=folder/'review-build.json';receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
 with receipt.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
 uploads=record['files']+[{'name':receipt.name,'path':receipt.relative_to(root).as_posix(),'size':receipt.stat().st_size,'sha256':digest}]
 notes=('PRIVATE REVIEW BUILD — NOT A PRODUCTION RELEASE\n\n'
        'Unsigned development packages retained for independent inspection. Windows CI passed; '
        'production signing, device acceptance, Android parity and public download approval remain open. '
        'Do not promote this draft or treat checksums as publisher authentication.\n\n'
        f"Source: {sha}\nRun: https://github.com/{repo}/actions/runs/{record['runId']}\n"
        'Assets are unique to this source/run/attempt and are never overwritten.\n')
 release=api('repos/'+repo+'/releases',{'tag_name':record['tag'],'target_commitish':sha,'name':f"Review {record['product']} — run {record['runId']}.{record['attempt']}",'body':notes,'draft':True,'prerelease':True,'make_latest':'false'})
 if release.get('draft') is not True or release.get('prerelease') is not True or release.get('target_commitish')!=sha or release.get('tag_name')!=record['tag'] or release.get('assets'):
  raise ValueError('Unexpected newly created draft identity')
 subprocess.run(['gh','release','upload',record['tag'],*[str(root/row['path']) for row in uploads],'--repo',repo],check=True)
 # Independently ask REST for the complete uploaded inventory and server hashes.
 verified=api('repos/'+repo+'/releases/'+str(release['id']))
 verify_release(verified,uploads,sha)
 validate_repository(api('repos/'+repo),repo)
 print('PRIVATE_REVIEW_DRAFT_STORED:',verified['html_url'])
 print('SERVER_ASSET_SHA256_VERIFIED:',len(uploads),'assets; independent package inspection still required')
 summary=os.environ.get('GITHUB_STEP_SUMMARY')
 if summary:
  with open(summary,'a',encoding='utf-8') as output:
   output.write(f"## Private review build stored\n\n{verified['html_url']}\n\nSource `{sha}`. Server size/SHA256 verified for {len(uploads)} assets. Draft/private only; production publication remains blocked.\n")

if __name__=='__main__':main()
