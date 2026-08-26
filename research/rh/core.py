import numpy as np, scipy.linalg as la
import mpmath as mp
mp.mp.dps=25
_ZC={}
def zeros_upto(N):
    if N not in _ZC: _ZC[N]=[float(mp.zetazero(k).imag) for k in range(1,N+1)]
    return _ZC[N]
def prime_powers(h):
    P=[];s=np.ones(int(np.exp(min(h,12)))+2,bool); s[:2]=False
    for i in range(2,int(len(s)**.5)+1):
        if s[i]: s[i*i::i]=False
    for p in np.nonzero(s)[0]:
        k=1
        while k*np.log(p)<h: P.append((int(p),k,k*np.log(p))); k+=1
    return sorted(P,key=lambda t:t[2])
def gl_nodes(h,kinks,panel=0.005,ng=24):
    xg,wg=np.polynomial.legendre.leggauss(ng)
    pts=sorted(set([0.0,h]+[k for k in kinks if 0<k<h]))
    X=[];W=[]
    for a,b in zip(pts[:-1],pts[1:]):
        m=max(1,int(np.ceil((b-a)/panel)))
        e=np.linspace(a,b,m+1)
        for lo,hi in zip(e[:-1],e[1:]):
            X.append(0.5*(hi-lo)*xg+0.5*(hi+lo)); W.append(0.5*(hi-lo)*wg)
    return np.concatenate(X),np.concatenate(W)
class Model:
    def __init__(self,h,NF,panel=0.005):
        self.h=h; self.NF=NF; self.pp=prime_powers(h); self.NP=len(self.pp)
        self.n=NF+self.NP
        self.U,self.W=gl_nodes(h,[t[2] for t in self.pp],panel)
        n,U=self.n,self.U
        PH=np.empty((n,U.size)); DP=np.empty((n,U.size))
        for i in range(NF):
            PH[i]=np.sin((i+1)*np.pi*U/h); DP[i]=((i+1)*np.pi/h)*np.cos((i+1)*np.pi*U/h)
        for k,(p,e,lp) in enumerate(self.pp):
            PH[NF+k]=np.where(U<lp,U/lp,(h-U)/(h-lp)); DP[NF+k]=np.where(U<lp,1/lp,-1/(h-lp))
        self.PH=PH; self.DP=DP
        self.Mg=PH@(self.W[:,None]*PH.T); self.Ms=DP@(self.W[:,None]*DP.T)
        lpv=np.array([t[2] for t in self.pp]); wg=np.array([np.log(p)/p**(e/2.) for p,e,_ in self.pp])
        PHp=np.empty((n,self.NP))
        for i in range(NF): PHp[i]=np.sin((i+1)*np.pi*lpv/h)
        for k,(p,e,lp) in enumerate(self.pp): PHp[NF+k]=np.where(lpv<lp,lpv/lp,(h-lpv)/(h-lp))
        self.H0=self.Ms-0.5*(PHp*wg)@PHp.T
        self.L=la.cholesky(self.Mg,lower=True)
        self.Li=la.solve_triangular(self.L,np.eye(n),lower=True)
        Ht=self.Li@self.H0@self.Li.T
        ev,X=la.eigh(Ht); self.lam0=ev[0]; self.x0=X[:,0]; self.X=X; self.ev=ev
        self.v0=la.solve_triangular(self.L.T,self.x0,lower=False)
        self.f0=self.v0@PH                       # ground state kao funkcija na cvorovima
    def ab(self,g,s):
        e=np.exp(s*self.U)
        return self.PH@(self.W*e*np.cos(g*self.U)), self.PH@(self.W*e*np.sin(g*self.U))
    def QCD(self,g,sig=0.1):
        ap,bp=self.ab(g,+sig); am,bm=self.ab(g,-sig)
        Qp=np.outer(bp,bp)-np.outer(ap,ap); Qm=np.outer(bm,bm)-np.outer(am,am)
        qc=0.5*(Qp+Qm); qd=0.5*(Qp-Qm)
        return self.Li@qc@self.Li.T, self.Li@qd@self.Li.T
    def mellin(self,g):
        """A0,B0 na sigma=0 i tacne sigma-derivacije A1,B1 = int f u cos/sin."""
        c=self.W*np.cos(g*self.U); s=self.W*np.sin(g*self.U)
        A0=self.f0@c; B0=self.f0@s
        A1=(self.f0*self.U)@c; B1=(self.f0*self.U)@s
        d=A0*A0+B0*B0
        return dict(A0=A0,B0=B0,A1=A1,B1=B1,
                    Omega=(A0*B1-B0*A1)/d, Lam=(A0*A1+B0*B1)/d,
                    r=np.hypot(A1,B1)/np.hypot(A0,B0))
