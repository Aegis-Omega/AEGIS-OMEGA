import io, json, sys, tempfile, unittest, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from agents.corpus_intake_v2 import inspect_archive, kind, safe_member, format_name, quantumdna_preflight, build_catalog
class CorpusIntakeV2Tests(unittest.TestCase):
 def fixture(self, entries):
  d=tempfile.TemporaryDirectory()
  p=Path(d.name)/'fixture.zip'
  with zipfile.ZipFile(p,'w') as z:
   for name,content in entries:z.writestr(name,content)
  self.addCleanup(d.cleanup)
  return p
 def test_nested_dataset_not_ignored(self):
  p=self.fixture([('data/a.csv','x\n1')]);r=inspect_archive(p)
  self.assertEqual(r[0]['kind'],'DATASET_CANDIDATE_NOT_EVALUATED')
 def test_untrusted_not_executed(self):
  p=self.fixture([('evil/execute.py','print(1)')]);r=inspect_archive(p)
  self.assertEqual(r[0]['kind'],'CODE_NOT_DATASET')
 def test_zip_slip_quarantine(self):
  p=self.fixture([('../escape.csv','1')]);r=inspect_archive(p)
  self.assertFalse(r[0]['safe_to_consider'])
 def test_windows_traversal_quarantine(self):
  p=self.fixture([('..\\escape.csv','1')]);r=inspect_archive(p)
  self.assertFalse(r[0]['safe_to_consider'])
 def test_duplicate_no_promotion(self):
  p=self.fixture([('data/a.csv','1')]);d=Path(tempfile.mkdtemp());r=build_catalog([p],d)
  self.assertIn('NOT_EVALUATED',r['evolution_status'])
 def test_not_scientific_proof(self):
  p=self.fixture([('formal/Lemma.lean','theorem t : True := by trivial')]);r=inspect_archive(p)
  self.assertEqual(r[0]['kind'],'FORMAL_SOURCE_NOT_PROOF')
 def test_dep_excluded(self):
  self.assertEqual(kind('project/node_modules/pkg/data.json'),'DEPENDENCY_OR_GENERATED')
 def test_formats_aliases(self):
  self.assertEqual(format_name('sample.vcf.gz'),'.vcf.gz')
  self.assertEqual(format_name('volume.nii.gz'),'.nii.gz')
 def test_unknown_visible(self):
  self.assertEqual(kind('new/research.foo'),'UNKNOWN_RETAIN_FOR_REVIEW')
 def test_nested_npz_class(self):
  self.assertEqual(kind('results/a.npz'),'DATASET_CANDIDATE_NOT_EVALUATED')
 def test_gamma_zero_classical_nan_is_declared_unavailable(self):
  prefix='AEGIS_QuantumDNA_v1/results/GAG_gamma_0'
  csv_data='time_fs,P_0,P_1,P_2,P_3,P_4,P_5,coherence_l1,classical_P_0,classical_P_1,classical_P_2,classical_P_3,classical_P_4,classical_P_5\n0,1,0,0,0,0,0,0,nan,nan,nan,nan,nan,nan\n1,0.9,0.1,0,0,0,0,0.1,nan,nan,nan,nan,nan,nan\n'
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:z.writestr('time_fs.npy',b'fixture')
  p=self.fixture([(prefix+'.csv',csv_data),(prefix+'_states.npz',buf.getvalue())])
  x=quantumdna_preflight(p)
  self.assertEqual(x['rows_checked'],2)
  self.assertEqual(x['defects'],[])
  self.assertEqual(x['availability_warnings'][0]['unavailable_rows'],2)
 def test_nonzero_gamma_nan_is_rejected(self):
  prefix='AEGIS_QuantumDNA_v1/results/GAG_gamma_0.1'
  csv_data='time_fs,P_0,P_1,P_2,P_3,P_4,P_5,coherence_l1,classical_P_0,classical_P_1,classical_P_2,classical_P_3,classical_P_4,classical_P_5\n0,1,0,0,0,0,0,0,nan,nan,nan,nan,nan,nan\n'
  p=self.fixture([(prefix+'.csv',csv_data)])
  x=quantumdna_preflight(p)
  self.assertIn('INVALID_CLASSICAL_REFERENCE',[e['reason'] for e in x['defects']])
 def test_invalid_time_order_rejected(self):
  prefix='AEGIS_QuantumDNA_v1/results/GAG_gamma_0.1'
  header='time_fs,P_0,P_1,P_2,P_3,P_4,P_5,coherence_l1,classical_P_0,classical_P_1,classical_P_2,classical_P_3,classical_P_4,classical_P_5\n'
  row='0,1,0,0,0,0,0,0,1,0,0,0,0,0\n'
  p=self.fixture([(prefix+'.csv',header+row+row)])
  x=quantumdna_preflight(p)
  self.assertIn('TIME_NOT_INCREASING',[e['reason'] for e in x['defects']])
 def test_real_quantumdna_if_present(self):
  src=ROOT/'source_archives'/'AEGIS_QuantumDNA_v1.zip'
  if not src.exists():self.skipTest('QuantumDNA fixture unavailable')
  q=quantumdna_preflight(src)
  self.assertEqual(q['csv_count'],39)
  self.assertEqual(q['npz_count'],38)
  self.assertEqual(q['paired_trajectories'],38)
  self.assertEqual(q['scientific_admission'],'NOT_EVALUATED')
  self.assertGreater(q['rows_checked'],70000)
  self.assertEqual(len(q['defects']),0)
  self.assertEqual(len(q['availability_warnings']),4)
if __name__=='__main__':unittest.main()