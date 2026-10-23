"""Download the reviewed developer engine, then run isolated native source gates.
No model fixture is genuine inference; no binaries/signing/publication are emitted.
"""
import hashlib,os,subprocess,sys,tempfile,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='4.7.2-stable'
SHA256='cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4'
def main():
 if not sys.platform.startswith('linux'):raise RuntimeError('This developer CI harness is Linux-only')
 with tempfile.TemporaryDirectory(prefix='native-source-ci-') as temp:
  folder=Path(temp);name='Godot_v'+VERSION+'_linux.x86_64'
  request=urllib.request.Request('https://github.com/godotengine/godot-builds/releases/download/'+VERSION+'/'+name+'.zip',headers={'User-Agent':'Evidence-native-source-check/1'})
  with urllib.request.urlopen(request,timeout=120) as response,(folder/'engine.zip').open('wb') as output:
   import shutil
   shutil.copyfileobj(response,output)
  archive=folder/'engine.zip'
  if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise RuntimeError('Reviewed engine checksum mismatch')
  with zipfile.ZipFile(archive) as zipped:
   if zipped.namelist()!=[name]:raise RuntimeError('Unexpected engine archive members')
   engine=folder/name;engine.write_bytes(zipped.read(name));engine.chmod(0o700)
  env=os.environ.copy();env['GODOT']=str(engine)
  commands={
   'EvidenceFlow':[[sys.executable,'scripts/build_save_adapter.py'],[sys.executable,'scripts/test.py','--godot',str(engine)]],
   'EvidenceCouncil':[[sys.executable,'scripts/verify.py',str(engine)]],
   'EvidenceAcademy':[[sys.executable,'scripts/verify.py','--godot',str(engine)]],
   'EvidenceLab':[[sys.executable,'scripts/check.py','--godot',str(engine)]],
   'EvidenceBot':[['sh','scripts/run_tests.sh']]
  }
  for command in commands[ROOT.name]:subprocess.run(command,cwd=ROOT,env=env,check=True,timeout=240)
  print('NATIVE_SOURCE_CI_PASS: '+ROOT.name+'; real model/device/production acceptance remains unrun')
if __name__=='__main__':main()
