# (1) exact check of  int_{-1}^{1} (P_n(x)-P_n(y))/|x-y| dy = 2 H_n P_n(x),  n<=8  (sympy, exact rational polynomials)
# (2) float check of the scale-free form  q(h)=int_0^1 (E-C(s))/s ds = sum_n H_n |h_n|^2 + int V h^2,  V=(1/2)log(1/(x(1-x)))
import sympy as sp, numpy as np, math
x,y=sp.symbols('x y',real=True)
ok=True
for n in range(0,9):
    P=sp.legendre(n,x); Q=sp.cancel((P-P.subs(x,y))/(x-y))          # polynomial in x,y
    left=sp.integrate(Q,(y,-1,x)); right=sp.integrate(-Q,(y,x,1))    # |x-y| = x-y for y<x, y-x for y>x
    res=sp.expand(left+right-2*sp.harmonic(n)*P)
    ok&=(res==0); print("n=%d residual=%s"%(n,res))
print("LEGENDRE_IDENTITY_EXACT_n<=8:", ok)
for n in (64,128,256,512):
    I=np.eye(n); Q=np.zeros((n,n))
    def U(m):
        M=np.zeros((n,n)); 
        if m<n: M[np.arange(n-m),np.arange(m,n)]=.5; M=M+M.T
        return M
    for m in range(n):
        a=math.log((m+1)/m) if m>0 else 0.0; b=1-m*a if m>0 else 1.0
        Um=U(m) if m>0 else I; Un=U(m+1) if m+1<n else 0*I
        Q+=a*(I-Um)-b*(Un-Um)
    s=(np.arange(n)+.5)/n; C=np.vstack([np.ones(n),s]); Z=np.linalg.svd(C)[2][2:].T
    Z1=np.linalg.svd(C[:1])[2][1:].T
    print("n=%4d  J_min: none %.5f  one moment %.5f  two moments %.5f"%(n,np.linalg.eigvalsh(Q)[0],np.linalg.eigvalsh(Z1.T@Q@Z1)[0],np.linalg.eigvalsh(Z.T@Q@Z)[0]))
print("claimed lower bounds: none log2=%.5f ; two moments 3/2+log2=%.5f"%(math.log(2),1.5+math.log(2)))
