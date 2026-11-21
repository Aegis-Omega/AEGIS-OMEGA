# check q(h)=int_0^1 (E-C(s))/s ds  ==  sum_n H_n * E_n  +  int_0^1 V h^2,  V=(1/2)log(1/(x(1-x))), E_n = energy of Legendre component n
import mpmath as mp, random
mp.mp.dps=30
random.seed(1)
N=6; c=[mp.mpf(random.uniform(-1,1)) for _ in range(N+1)]
P=lambda n,x: mp.legendre(n,2*x-1)
h=lambda x: sum(c[n]*P(n,x) for n in range(N+1))
C=lambda s: mp.quad(lambda x:h(x+s)*h(x),[0,1-s])
E=mp.quad(lambda x:h(x)**2,[0,1])
q=mp.quad(lambda s:(E-C(s))/s,[0,mp.mpf(1)/2,1])
H=lambda n: sum(mp.mpf(1)/k for k in range(1,n+1))
En=[c[n]**2/(2*n+1) for n in range(N+1)]
rhs=sum(H(n)*En[n] for n in range(N+1))+mp.quad(lambda x:mp.log(1/(x*(1-x)))/2*h(x)**2,[0,mp.mpf(1)/2,1])
print("q   =",mp.nstr(q,20)); print("rhs =",mp.nstr(rhs,20)); print("diff=",mp.nstr(q-rhs,5))
