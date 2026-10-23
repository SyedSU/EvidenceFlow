"""Owner-only build storage must never become a public or replaceable release."""
import importlib.util,json,tempfile,unittest
from pathlib import Path

class ReviewStorageTests(unittest.TestCase):
 def module(self):
  path=Path(__file__).with_name('store_review_build.py')
  self.assertTrue(path.is_file(),'Review storage guard is required')
  spec=importlib.util.spec_from_file_location('storage',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 def env(self):return {'GITHUB_REPOSITORY':'SyedSU/EvidenceFlow','GITHUB_REF':'refs/heads/main','GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'2','GITHUB_EVENT_NAME':'push'}
 def fixture(self,root):
  folder=root/'build/windows-review';folder.mkdir(parents=True)
  for filename in ['EvidenceFlow-Windows-x64-review.zip','package-report.json','windows-smoke.log']:(folder/filename).write_bytes(b'fixture output')
 def test_plan_hashes_exact_files_and_unique_run_attempt(self):
  module=self.module()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);plan=module.plan(root,self.env())
   self.assertEqual(plan['tag'],'review-evidenceflow-'+ 'a'*40+'-123-2')
   self.assertEqual(len(plan['files']),3)
   self.assertTrue(all(len(row['sha256'])==64 for row in plan['files']))
   self.assertFalse(plan['publicationAuthorized'])
 def test_rejects_nonmain_or_untrusted_run_identity(self):
  module=self.module()
  for key,value in [('GITHUB_REF','refs/pull/1/merge'),('GITHUB_REPOSITORY','Other/EvidenceFlow'),('GITHUB_SHA','main'),('GITHUB_RUN_ID','../1'),('GITHUB_RUN_ATTEMPT','0'),('GITHUB_EVENT_NAME','pull_request_target')]:
   env=self.env();env[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):module.plan(Path('/unused'),env)
 def test_incomplete_or_symlinked_outputs_are_rejected(self):
  module=self.module()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with self.assertRaises(ValueError):module.plan(root,self.env())
   self.fixture(root);path=root/'build/windows-review/package-report.json';path.unlink()
   outside=root/'outside.zip';outside.write_bytes(b'other');
   try:path.symlink_to(outside)
   except OSError:self.skipTest('Host cannot create symlink fixture')
   with self.assertRaises(ValueError):module.plan(root,self.env())
 def test_private_exact_repository_is_required(self):
  module=self.module()
  for metadata in [{'full_name':'SyedSU/EvidenceFlow','private':False},{'full_name':'Other/repo','private':True}]:
   with self.assertRaises(ValueError):module.validate_repository(metadata,'SyedSU/EvidenceFlow')
  module.validate_repository({'full_name':'SyedSU/EvidenceFlow','private':True},'SyedSU/EvidenceFlow')
 def test_server_assets_must_match_exact_hash_size_and_draft(self):
  module=self.module();files=[{'name':'file.zip','size':3,'sha256':'a'*64}]
  release={'draft':True,'prerelease':True,'target_commitish':'b'*40,'assets':[{'name':'file.zip','size':3,'digest':'sha256:'+'a'*64}]}
  module.verify_release(release,files,'b'*40)
  for changes in [{'draft':False},{'prerelease':False},{'target_commitish':'main'},{'assets':[]},{'assets':[{'name':'file.zip','size':3,'digest':None}]}]:
   with self.subTest(changes=changes),self.assertRaises(ValueError):module.verify_release(dict(release,**changes),files,'b'*40)

 def test_api_errors_keep_safe_server_diagnostics(self):
  module=self.module()
  from unittest.mock import patch
  import subprocess
  failure=subprocess.CalledProcessError(1,['gh','api','repos/allowed'],stderr='HTTP 403: limited; token=fixture-secret')
  with patch.object(module.subprocess,'run',side_effect=failure),patch.dict(module.os.environ,{'GH_TOKEN':'fixture-secret'}):
   with self.assertRaises(RuntimeError) as caught:module.api('repos/allowed')
  self.assertIn('HTTP 403',str(caught.exception))
  self.assertNotIn('fixture-secret',str(caught.exception))

if __name__=='__main__':unittest.main()
