import argparse,json,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--analysis',required=True);p.add_argument('--out',required=True);a=p.parse_args()
data=pathlib.Path(a.analysis);out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
r=json.loads((data/'audit_results.json').read_text());rows=r['models'];diag=json.loads((data/'constructed_diagnostics.json').read_text())['summary']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':220})
def save(fig,n):
 fig.savefig(out/(n+'.png'),bbox_inches='tight');fig.savefig(out/(n+'.pdf'),bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4))
for x in rows:ax.scatter(100*x['over_rate'],x['rule_all']-x['judge_reported'],color='#be4b43' if x['model']=='minimax-m3' else '#2a6584',s=60 if x['model']=='minimax-m3' else 30,zorder=3)
for name,dx,dy in [('minimax-m3',-5,8),('qwen-max',8,10),('glm-5.3-prime',3,-10),('qwen3-32b',8,-13)]:
 x=next(v for v in rows if v['model']==name);ax.annotate(name,(100*x['over_rate'],x['rule_all']-x['judge_reported']),xytext=(dx,dy),textcoords='offset points',fontsize=8)
ax.axhline(0,color='#777',lw=.8);ax.grid(alpha=.15);ax.set(xlabel='Calls longer than reference (%)',ylabel='Legacy rule mean minus judge mean',title='Association is sensitive to one configuration')
ax.text(.98,.96,'All 21: r = -0.788\nWithout MiniMax-M3: r = -0.281',transform=ax.transAxes,ha='right',va='top',fontsize=10);save(fig,'fig01_association')
fig,ax=plt.subplots(figsize=(7,3.7));names=['Legacy','A set to one','A removed','B bucket','C subset','D relaxed'];keys=['baseline','A','actual_drop','B','C','D'];vals=[r['ablation_summary'][k]['gap'] for k in keys]
bars=ax.bar(range(6),vals,color=['#4b5662','#2a6584','#be4b43','#7e93a2','#617f92','#2a6584'],width=.66)
ax.set_xticks(range(6),names,rotation=16,ha='right');ax.set_ylim(0,.18);ax.set(ylabel='Other configuration mean minus M3',title='Ablation arithmetic changes the reported gap')
for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+.004,f'{v:.3f}',ha='center',fontsize=9)
ax.grid(axis='y',alpha=.15);save(fig,'fig02_ablation')
fig,ax=plt.subplots(figsize=(7,3.7));names=['Reference','Duplicate read','Wrong answer','No final answer','Wrong entity'];variants=['reference','duplicate_read','wrong_final_value','missing_final','wrong_entity'];x=np.arange(5)
ax.bar(x-.18,[diag[v]['mean_legacy'] for v in variants],.34,color='#2a6584',label='Legacy');ax.bar(x+.18,[diag[v]['mean_D'] for v in variants],.34,color='#a7bac7',label='Relaxed D');ax.axhline(.75,ls='--',color='#be4b43',lw=1,label='Pass threshold')
ax.set_xticks(x,names,rotation=12);ax.set_ylim(0,1.2);ax.set(ylabel='Mean score',title='Constructed checks expose both penalty directions')
for i in range(5):ax.text(i,1.07,'valid' if i<2 else 'invalid',ha='center',fontsize=9,color='#286548' if i<2 else '#ad3f3c')
ax.legend(loc='lower left',ncol=3,fontsize=8);save(fig,'fig03_constructed')
fig,ax=plt.subplots(figsize=(7,4.5));ax.set_xlim(0,10);ax.set_ylim(0,6);ax.axis('off')
boxes=[(.3,4.6,3,.85,'Task contract\nGoals and evidence'),(6.7,4.6,3,.85,'Trusted runtime\nState and events'),(3.35,3.05,3.3,.9,'Replay and certify\nIndependent checks'),(.3,1.6,3,.85,'Valid alternatives\nPreserve obligations'),(6.7,1.6,3,.85,'Minimal violations\nBreak one obligation'),(3.35,.1,3.3,.85,'Evaluate repair\nRejects and accepts')]
for xx,yy,w,h,t in boxes:
 ax.add_patch(FancyBboxPatch((xx,yy),w,h,boxstyle='round,pad=0.08',edgecolor='#80909d',facecolor='#f0f4f7'));ax.text(xx+w/2,yy+h/2,t,ha='center',va='center',fontsize=9)
for p1,p2 in [((1.8,4.6),(4.3,3.95)),((8.2,4.6),(5.7,3.95)),((4.1,3.05),(1.8,2.45)),((5.9,3.05),(8.2,2.45)),((1.8,1.6),(4.2,.95)),((8.2,1.6),(5.8,.95))]:ax.add_patch(FancyArrowPatch(p1,p2,arrowstyle='-|>',mutation_scale=12,color='#48616f',lw=1.2))
save(fig,'fig04_protocol');print('Created four PNG and vector PDF figures')
