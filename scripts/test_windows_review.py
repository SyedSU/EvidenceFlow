import importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('windows_review',Path(__file__).with_name('windows_review.py'))
m=importlib.util.module_from_spec(spec)
class PackageGuards(unittest.TestCase):
 def setUp(self):
  spec.loader.exec_module(m);self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.payload=self.root/'payload';self.payload.mkdir()
  for name in ['EvidenceFlow.exe','native/genesis_save.dll','LICENSE.txt','THIRD-PARTY-NOTICES.txt','REVIEW-BUILD.txt']:
   p=self.payload/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture package bytes')
 def test_smoke_requires_actual_native_written_json(self):
  profile=self.root/'profile';profile.mkdir()
  with self.assertRaises(ValueError):m.verify_smoke_file(profile)
  (profile/'package-smoke.json').write_text('{"package_smoke":false}')
  with self.assertRaises(ValueError):m.verify_smoke_file(profile)
  (profile/'package-smoke.json').write_text('{"package_smoke":true}')
  m.verify_smoke_file(profile)
 def test_manifest_binds_every_real_byte(self):
  target=self.root/'out.zip';result=m.archive_payload(self.payload,target,'EvidenceFlow','a'*40)
  with zipfile.ZipFile(target) as z:
   manifest=json.loads(z.read('EvidenceFlow/build-manifest.json'))
   self.assertEqual(manifest['sourceCommit'],'a'*40);self.assertFalse(manifest['publicationAuthorized'])
   for row in manifest['files']:self.assertEqual(m.digest_bytes(z.read('EvidenceFlow/'+row['path'])),row['sha256'])
  self.assertEqual(result['sha256'],m.digest_bytes(target.read_bytes()))
 def test_missing_native_library_rejected(self):
  (self.payload/'native/genesis_save.dll').unlink()
  with self.assertRaises(ValueError):m.archive_payload(self.payload,self.root/'out.zip','EvidenceFlow','a'*40)
 def test_unexpected_user_data_rejected(self):
  (self.payload/'credentials.json').write_text('not a credential')
  with self.assertRaises(ValueError):m.archive_payload(self.payload,self.root/'out.zip','EvidenceFlow','a'*40)
 def test_existing_archive_preserved(self):
  target=self.root/'out.zip';target.write_bytes(b'preserve')
  with self.assertRaises(FileExistsError):m.archive_payload(self.payload,target,'EvidenceFlow','a'*40)
  self.assertEqual(target.read_bytes(),b'preserve')
 def test_unbound_source_rejected(self):
  with self.assertRaises(ValueError):m.archive_payload(self.payload,self.root/'out.zip','EvidenceFlow','main')
if __name__=='__main__':unittest.main()
