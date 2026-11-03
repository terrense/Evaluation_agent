"""Offline audit of a pinned public checkout; no model calls or source edits.
GraderScore is replaced only to exercise pure rule functions. This is NOT an
OpenJudge integration test. Output numbers describe cached endpoint runs.
"""
import argparse,asyncio,collections,csv,hashlib,importlib,json,pathlib,subprocess,sys,types
import numpy as np
from scipy.stats import pearsonr,spearmanr

PIN='1422f412f25fd55a282e4551739a24e7deb3649f'
def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 root=pathlib.Path(a.repo).resolve();out=pathlib.Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
 commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
 if commit!=PIN:raise ValueError('Use pinned commit '+PIN)
 if subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True).strip():raise ValueError('Use a clean checkout')
 sys.path.insert(0,str(root/'experiments/openjudge/hospital'))
 for n in ['openjudge','openjudge.graders','openjudge.graders.schema']:sys.modules[n]=types.ModuleType(n)
 class GraderScore:
  def __init__(self,**kw):self.__dict__.update(kw)
 sys.modules['openjudge.graders.schema'].GraderScore=GraderScore
 from samples import SAMPLES
 from tool_requirement import TOOL_REQUIREMENT
 from graders_rule import RULE_GRADERS
 from posture_grader import aggregate,rescore,classify_posture,PROCESS_DIMS
 sample={s['task_id']:s for s in SAMPLES};base=root/'reports/openjudge/multimodel'
 rows=[];paired=[];mismatch=[];abnormal=[];abl={v:{} for v in ['baseline','A','B','C','D','actual_drop']}
 async def score(t,e):return {k:(await f(trajectory=t,expected=e)).score for k,f in RULE_GRADERS.items()}
 for d in sorted(base.glob('*__t0.0')):
  name=d.name.removesuffix('__t0.0');traces=[json.loads(l) for l in (d/'real_traces.jsonl').read_text().splitlines() if l.strip()]
  rule=json.loads((d/'rule_scores.json').read_text());judges=[json.loads(l) for l in (d/'llm_scores.jsonl').read_text().splitlines() if l.strip()];byj={j['task_id']:j for j in judges}
  vals=[];v0=[];js=[];jc=[];post=collections.Counter();pass_by=collections.defaultdict(list);variant={v:[] for v in abl}
  for t in traces:
   tid=t['task_id'];trial=t['trial'];e=sample[tid]['expected'];r=rule[tid][str(trial)]
   recomputed=asyncio.run(score(t['trajectory'],e))
   if r!=recomputed:mismatch.append({'model':name,'task':tid,'trial':trial,'old':r,'new':recomputed})
   calls=[s['tool'] for s in t['trajectory'] if s.get('type')=='tool_call'];posture=classify_posture(calls,e['correct_tools']);post[posture]+=1
   val=aggregate(r);vals.append(val);pass_by[tid].append(val>=.75)
   for v in ['baseline','A','B','C','D']:variant[v].append(aggregate(rescore(r,TOOL_REQUIREMENT[tid],e['correct_tools'],calls,v)))
   variant['actual_drop'].append(aggregate({k:v for k,v in r.items() if k not in PROCESS_DIMS}))
   if '未在 max_turns' in t['final'] or '运行异常' in t['final']:abnormal.append({'model':name,'task':tid,'trial':trial,'kind':'max_turns' if '未在 max_turns' in t['final'] else 'runtime','completion':r['task_completion'],'aggregate':val})
   if trial==0:
    j=byj[tid];v0.append(val);js.append(j['score']);jc.append(aggregate(j['dims']))
    paired.append({'model':name,'task_id':tid,'bucket':TOOL_REQUIREMENT[tid],'rule':val,'llm_reported':j['score'],'llm_common':aggregate(j['dims']),'posture':posture})
  for v in abl:abl[v][name]=float(np.mean(variant[v]))
  counts=[sum(x) for x in pass_by.values()]
  rows.append({'model':name,'n_traces':len(traces),'n_tasks':len(pass_by),'n_judges':len(judges),'rule_all':float(np.mean(vals)),'rule_trial0':float(np.mean(v0)),'judge_reported':float(np.mean(js)),'judge_common':float(np.mean(jc)),'over_rate':post['over']/len(traces),'plugin_pass_power3':float(np.mean([(c/3)**3 for c in counts])),'unbiased_all3':sum(c==3 for c in counts)/len(counts)})
 def corr(rr,rfield='rule_all',jfield='judge_reported'):
  return {'pearson_over_gap':float(pearsonr([r['over_rate'] for r in rr],[r[rfield]-r[jfield] for r in rr]).statistic),'spearman':float(spearmanr([r[rfield] for r in rr],[r[jfield] for r in rr]).statistic)}
 unit={}
 for modname in ['test_grader','test_date_normalize']:
  m=importlib.import_module(modname)
  for k in dir(m):
   if k.startswith('test_') and callable(getattr(m,k)):
    try:getattr(m,k)();unit[f'{modname}.{k}']='pass'
    except Exception as ex:unit[f'{modname}.{k}']=f'{type(ex).__name__}: {ex}'
 counterexamples=[]
 for name,text in [('runtime_marked_complete','(运行异常：TimeoutError)'),('max_turns_marked_complete','(未在 max_turns 内给出最终回答)')]:
  tr=[{'type':'final_answer','text':text}];counterexamples.append({'case':name,'task_id':'H001','trajectory':tr,'scores':asyncio.run(score(tr,sample['H001']['expected']))})
 no_call=[{'type':'final_answer','text':'请补充您希望查询的具体日期。'}]
 g1=asyncio.run(score(no_call,dict(sample['H001']['expected'],grounded=True)));g0=asyncio.run(score(no_call,dict(sample['H001']['expected'],grounded=False)))
 counterexamples.append({'case':'fixture_label_dependence','same_trace_grounded_true':g1['groundedness'],'same_trace_grounded_false':g0['groundedness']})
 result={'repo_commit':commit,'data_hash':hashlib.sha256((root/'experiments/openjudge/hospital/samples.py').read_bytes()).hexdigest(),'n_models':len(rows),'n_tasks':len(sample),'n_unique_input_strings':len({s.get('input',s.get('query','')) for s in SAMPLES}),'bucket_counts':dict(collections.Counter(TOOL_REQUIREMENT.values())),'total_traces':sum(r['n_traces'] for r in rows),'total_judges':sum(r['n_judges'] for r in rows),'recomputed_score_mismatches':len(mismatch),'correlations_original':corr(rows),'correlations_paired':corr(rows,'rule_trial0'),'correlations_paired_common':corr(rows,'rule_trial0','judge_common'),'correlations_without_m3':corr([r for r in rows if r['model']!='minimax-m3']),'leave_one_model_out':{r['model']:corr([z for z in rows if z['model']!=r['model']]) for r in rows},'ablation_summary':{v:{'m3':x['minimax-m3'],'others':float(np.mean([y for k,y in x.items() if k!='minimax-m3'])),'gap':float(np.mean([y for k,y in x.items() if k!='minimax-m3']))-x['minimax-m3']} for v,x in abl.items()},'models':rows,'existing_unit_checks_with_shim':unit,'abnormal_traces':abnormal,'constructed_counterexamples':counterexamples,'score_mismatch_examples':mismatch[:20]}
 for fn,obj in [('audit_results.json',result),('paired_trial0.json',paired)]: (out/fn).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 with (out/'model_summary.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(json.dumps({k:v for k,v in result.items() if k not in ['models','leave_one_model_out','score_mismatch_examples','existing_unit_checks_with_shim','abnormal_traces']},ensure_ascii=False,indent=2))
 print('Unit checks:',collections.Counter(unit.values()));print('Abnormal:',len(abnormal),'completion=1:',sum(t['completion']==1 for t in abnormal))
if __name__=='__main__':main()
