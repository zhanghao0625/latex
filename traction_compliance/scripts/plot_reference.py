"""Generate analytical illustrations. No trained-policy measurements are used."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42})
f = np.linspace(-50, 50, 4001)
vx = np.where(np.abs(f) > 17.5, np.clip((f + 17.5*np.sign(f))/20, -0.5, 1.2), 0)
vy = np.where(np.abs(f) > 17.5, np.clip((f + 17.5*np.sign(f))/20, -0.5, 0.5), 0)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.0), layout='constrained')
for ax, value, label, lower, upper in [(axes[0],vx,'Forward reference',-.5,1.2),(axes[1],vy,'Lateral reference',-.5,.5)]:
    ax.plot(f,value,color='#155e75',lw=2)
    ax.scatter([-17.5,17.5],[0,0],color='#155e75',zorder=5,s=26)
    ax.scatter([-17.5,17.5],[lower,upper],facecolors='white',edgecolors='#155e75',zorder=5,s=26)
    ax.axvline(-17.5,color='.7',ls=':',lw=1)
    ax.axvline(17.5,color='.7',ls=':',lw=1)
    ax.set(xlabel='Force component (N)',ylabel='Velocity correction (m/s)',title=label,xlim=(-50,50))
    ax.grid(alpha=.15)
fig.savefig(root/'figures/reference_map.pdf')
plt.close(fig)

dt=.02
t=np.arange(0,6+dt/2,dt)
force=np.where((t>=1)&(t<3),20.,0.)
mass,damping=10.,20.
reference=np.zeros_like(t)
a=np.exp(-damping*dt/mass)
for k in range(len(t)-1):
    reference[k+1]=a*reference[k]+(1-a)*force[k]/damping
current=np.where(force>17.5,1.2,0.)
fig,ax=plt.subplots(figsize=(10,3),layout='constrained')
ax.step(t,current,where='post',lw=2,color='#b45309',label='Current algebraic reference')
ax.plot(t,reference,lw=2,color='#155e75',label='Proposed mass-damping reference')
ax.set(xlabel='Time (s)',ylabel='Velocity correction (m/s)',xlim=(0,6))
ax.legend(frameon=False,loc='upper right')
ax.grid(alpha=.15)
fig.savefig(root/'figures/reference_dynamics.pdf')
plt.close(fig)
print('Generated two analytical figures.')
