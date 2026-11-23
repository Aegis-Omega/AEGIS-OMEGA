# Perron budget: H = D*I - B with |B_ij| <= c_|i-j|  =>  H >= (D - rho(C)) I.  c_k = log2*2^{-k/2} + a_k.
import numpy as np, math
from mpmath import mp, quad, sinh, log, pi, euler, exp, mpf
mp.dps=20
w=mpf(1)/32
coth=quad(lambda u:1/sinh(u),[w,1,10,mp.inf]); kap=log(4*pi)+euler
Dlean=float(coth-kap-(w/2)*exp(w/2))
gain0=float(exp(-w)*log(2)-quad(lambda u:(exp(u/2)-1)/sinh(u),[0,w]))   # no-moment gain lower bound (see report)
print("cothTail(1/32)-kappa =",float(coth-kap)," Lean diagonal (V27) =",Dlean," proposed no-moment diag >=",Dlean+gain0+float((w/2)*exp(w/2)))
Dprop=float(coth-kap)+gain0
def rho(N,arch):
    C=np.zeros((N+1,N+1))
    for i in range(N+1):
        for j in range(N+1):
            k=abs(i-j)
            if k: C[i,j]=math.log(2)*2**(-k/2)+arch(k)
    return max(np.linalg.eigvalsh(C))
for name,arch in (("arch 1/100 (V31)",lambda k:0.01),("arch (30/649)2^{-5k/2} (in flight)",lambda k:30/649*2**(-2.5*k))):
    print(name)
    for N in range(1,7):
        r=rho(N,arch); print("  blocks=%d  rho=%.4f  margin Lean D=%.4f  margin proposed D=%.4f"%(N+1,r,Dlean-r,Dprop-r))
