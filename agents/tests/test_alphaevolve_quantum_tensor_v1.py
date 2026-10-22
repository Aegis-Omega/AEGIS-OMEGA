import tempfile,unittest
from pathlib import Path
import numpy as np
from agents.alphaevolve_quantum_tensor_v1 import evolve_tensor

class QuantumEvolution(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.p=Path(self.t.name)/'quantum.npz'
  time=np.arange(180,dtype=float)
  rho=np.zeros((180,2,2),dtype=np.complex128)
  x=(1+np.sin(time*.08))/2
  rho[:,0,0]=x;rho[:,1,1]=1-x
  np.savez(self.p,time_fs=time,rho_qdna=rho,rho_independent=rho,H_eV=np.eye(2))
 def test_physical_evolution_observed(self):
  x=evolve_tensor(self.p,stride=8)
  self.assertEqual(x['state'],'QUANTUM_TENSOR_INTERPOLATION_EVOLUTION')
  self.assertEqual(x['scientific_admission'],'DENIED')
  self.assertEqual(len(x['arrays']),2)
  self.assertTrue(x['arrays'][0]['invariants']['sampled_state_physically_valid'])
 def test_hawke_style_reference_37x37_supported(self):
  time=np.arange(120,dtype=float)
  rho=np.zeros((120,37,37),dtype=np.complex128)
  rho[:,0,0]=1.
  np.savez(self.p,time_fs=time,rho_qdna=rho,rho_independent=rho,
           H_rad_ps=np.eye(37,dtype=np.complex128))
  x=evolve_tensor(self.p,stride=8)
  self.assertEqual(x['state'],'QUANTUM_TENSOR_INTERPOLATION_EVOLUTION')

 def test_corrupted_trace_veto(self):
  with np.load(self.p) as z:
   rho=z['rho_qdna'].copy();time=z['time_fs'];H=z['H_eV']
  rho[:]=rho*2
  np.savez(self.p,time_fs=time,rho_qdna=rho,rho_independent=rho,H_eV=H)
  self.assertEqual(evolve_tensor(self.p,stride=8)['state'],'PHYSICAL_INVARIANT_VETO')
 def test_pickle_refused_and_bad_stride(self):
  with self.assertRaisesRegex(ValueError,'STRIDE_BOUNDS'):evolve_tensor(self.p,stride=2)
  self.p.write_bytes(b'not npz')
  with self.assertRaises(Exception):evolve_tensor(self.p,stride=8)

if __name__=='__main__':unittest.main()
