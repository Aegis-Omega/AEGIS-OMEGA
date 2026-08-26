import numpy as np, scipy.linalg as la
SIG=0.1
class Kappa:
    def __init__(self,M):
        self.M=M; self.x0=M.x0; self.Li=M.Li; self.n=M.n
    def vecs(self,t):
        M=self.M; U=M.U; W=M.W; e=np.exp(SIG*U); ei=1.0/e
        c=np.cos(t*U); s=np.sin(t*U)
        ap=M.PH@(W*e*c); bp=M.PH@(W*e*s); am=M.PH@(W*ei*c); bm=M.PH@(W*ei*s)
        Li=self.Li
        return Li@ap,Li@bp,Li@am,Li@bm         # alpha+, beta+, alpha-, beta-
    def at(self,t,vecs=None):
        x0=self.x0
        a_p,b_p,a_m,b_m = vecs if vecs is not None else self.vecs(t)
        # Q~_C x0 , Q~_D x0  bez formiranja n x n
        tp = b_p*(b_p@x0) - a_p*(a_p@x0)
        tm = b_m*(b_m@x0) - a_m*(a_m@x0)
        gC=0.5*(tp+tm); gD=0.5*(tp-tm)
        Qg=np.linalg.qr(np.column_stack([x0,gC,gD]))[0]
        P=lambda Z: Z-Qg@(Qg.T@Z)
        Ap=P(np.column_stack([b_p,a_m]))/np.sqrt(2)
        Am=P(np.column_stack([a_p,b_m]))/np.sqrt(2)
        sA=la.norm(Ap,2)
        T,_,_,_=la.lstsq(Am,Ap)
        eta=la.norm(Ap-Am@T,2)/max(sA,1e-300)
        return dict(kappa=la.norm(T,2)-1.0, eta=eta, rkAm=np.linalg.matrix_rank(Am,tol=1e-10*max(la.norm(Am,2),1e-300)),
                    Ap=Ap,Am=Am,gC=gC,gD=gD,Qg=Qg)
def signature_blocker(M,t,tau=1e-10):
    QC,QD=M.QCD(t,SIG); x0=M.x0
    G=np.column_stack([x0,QC@x0,QD@x0])
    K=la.null_space(np.linalg.qr(G)[0].T,rcond=1e-13)
    e=la.eigvalsh(K.T@QD@K); sc=max(1.0,abs(e).max())
    return (1 if e[-1]/sc<=tau else 0), e[-1]/sc
