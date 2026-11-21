# Numerical probe (float64, class (d)): Weil form on dyadic comb classes at fixed total log-width w.
import numpy as np, math, sys
w=float(eval(sys.argv[1])) if len(sys.argv)>1 else 1/32
n=int(sys.argv[2]) if len(sys.argv)>2 else 48
NMAX=int(sys.argv[3]) if len(sys.argv)>3 else 14
d=math.log(2); delta=w/n
kappa=math.log(4*math.pi)+0.5772156649015329
coth_tail=math.log(1/math.tanh(w/2))        # int_w^inf du/sinh u
gx,gw=np.polynomial.legendre.leggauss(40); th=(gx+1)/2; tw=gw/2
def U(m):                                   # shift matrix: (a^T U_m a)*delta = C(m*delta) for step h
    M=np.zeros((n,n))
    if 0<=m<n: M[np.arange(n-m),np.arange(m,n)]=1
    return M
def Ushift(u):                              # piecewise-linear in u, exact for step functions
    s=abs(u)/delta; m=int(math.floor(s)); t=s-m
    M=(1-t)*U(m)+t*U(m+1)
    return M if u>=0 else M.T
# diagonal block: -B(g,g) = (coth_tail-kappa)E + int_0^w (E - e^{u/2}C(u))/sinh u du
Qd=np.zeros((n,n)); I=np.eye(n)
for m in range(n):
    u=(m+th)*delta
    if m==0: Qd+=I*np.sum(tw*delta*(1-np.exp(u/2)*(1-th))/np.sinh(u))
    else:
        Qd+=I*np.sum(tw*delta/np.sinh(u))
        P=np.sum(tw*delta*np.exp(u/2)*(1-th)/np.sinh(u)); Um=U(m); Qd-=P*(Um+Um.T)/2
    R=np.sum(tw*delta*np.exp(u/2)*th/np.sinh(u)); Um=U(m+1); Qd-=R*(Um+Um.T)/2
Dblk=(coth_tail-kappa)*I+Qd                 # in units where energy = a^T a (delta cancels)
# moment constraints per block: int h e^{+-s/2} ds = 0
s0=np.arange(n)*delta; s1=s0+delta
c1=2*(np.exp(s1/2)-np.exp(s0/2)); c2=-2*(np.exp(-s1/2)-np.exp(-s0/2))
Cm=np.vstack([c1,c2]); _,_,Vt=np.linalg.svd(Cm); Z=Vt[2:].T          # n x (n-2) basis of constraint space
Z1=np.linalg.svd(np.vstack([c1]))[2][1:].T
print(f"w={w:.6f} n={n}  cothTail-kappa={coth_tail-kappa:.5f}")
for name,B in (("no moments",I),("two moments",Z)):
    ev=np.linalg.eigvalsh(B.T@Qd@B); print(f"  inner gain J_min ({name}) = {ev[0]:.5f};  D_min = {coth_tail-kappa+ev[0]:.5f}")
# prime powers
X=int(2**(NMAX+1)*math.exp(w))+10
sieve=np.ones(X+1,bool); sieve[:2]=False
for p in range(2,int(X**.5)+1):
    if sieve[p]: sieve[p*p::p]=False
Lam={}
for p in np.nonzero(sieve)[0]:
    q=int(p)
    while q<=X: Lam[q]=math.log(p); q*=int(p)
def Kar(u): return math.exp(-u/2)/(1-math.exp(-2*u))
G=[]; rows=[]
gx2,gw2=np.polynomial.legendre.leggauss(12)
for k in range(1,NMAX+1):
    lo=math.exp(k*d-w); hi=math.exp(k*d+w)
    hits=[(q,Lam[q]) for q in range(int(math.ceil(lo)),int(math.floor(hi))+1) if q in Lam]
    Gk=np.zeros((n,n)); mass=0; other=0
    for q,l in hits:
        Gk+=l/math.sqrt(q)*Ushift(math.log(q)-k*d); mass+=l/math.sqrt(q)
        if q!=2**k: other+=l/math.sqrt(q)
    A=np.zeros((n,n))                        # arch: int K(kd - v) U(v) dv over v in [-w,w], piecewise in cells
    for m in range(-n,n):
        v=(m+(gx2+1)/2)*delta
        for vi,wi in zip(v,gw2/2*delta): A+=wi*Kar(k*d-vi)*Ushift(vi)
    G.append(Gk+A)
    nrm=np.linalg.norm(Z.T@Gk@Z,2); nrmA=np.linalg.norm(Z.T@A@Z,2)
    rows.append((k,len(hits),mass,other,nrm,nrmA))
print(" k  #pp  mass=sum L/sqrt(n)  non-2^k mass  ||prime block|| on moment-zero  ||arch block||")
for r in rows: print(" %2d %4d  %10.5f  %10.5f  %10.5f  %.3e"%r)
Dmin=np.linalg.eigvalsh(Z.T@Dblk@Z)[0]
print(" N  lam_min(comb class)   abs budget D_min-2*sum mass   norm budget D_min-2*sum ||G_k||   pure-2 budget")
for N in range(1,NMAX+1):
    m=n-2; T=np.zeros(((N+1)*m,(N+1)*m)); Dz=Z.T@Dblk@Z
    for i in range(N+1):
        T[i*m:(i+1)*m,i*m:(i+1)*m]=Dz
        for j in range(i+1,N+1):
            B=-(Z.T@G[j-i-1]@Z); T[i*m:(i+1)*m,j*m:(j+1)*m]=B; T[j*m:(j+1)*m,i*m:(i+1)*m]=B.T
    lam=np.linalg.eigvalsh(T)[0]
    ab=Dmin-2*sum(r[2] for r in rows[:N]); nb=Dmin-2*sum(np.linalg.norm(Z.T@G[k]@Z,2) for k in range(N))
    p2=Dmin-2*sum(d*2**(-k/2) for k in range(1,N+1))
    print(" %2d  %12.6f  %12.5f  %12.5f  %10.5f"%(N,lam,ab,nb,p2))
