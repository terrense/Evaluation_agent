"""Seven tasks x five constructed variants. No model calls; not prevalence estimates."""
import argparse,asyncio,copy,json,pathlib,sys,types
def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 root=pathlib.Path(a.repo).resolve();out=pathlib.Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
 sys.path.insert(0,str(root/'experiments/openjudge/hospital'))
 for n in ['openjudge','openjudge.graders','openjudge.graders.schema']:sys.modules[n]=types.ModuleType(n)
 class GraderScore:
  def __init__(self,**kw):self.__dict__.update(kw)
 sys.modules['openjudge.graders.schema'].GraderScore=GraderScore
 from samples import SAMPLES
 from tools import query_hospital_location
 from graders_rule import RULE_GRADERS
 from posture_grader import aggregate,rescore
 tasks={'H007':'呼吸内科','H056':'眼科','H057':'口腔科','H058':'骨科','H059':'皮肤科','H060':'急诊科','H061':'体检中心'}
 expected={s['task_id']:s['expected'] for s in SAMPLES};records=[]
 async def score(t,e):return {k:(await f(trajectory=t,expected=e)).score for k,f in RULE_GRADERS.items()}
 for tid,dept in tasks.items():
  obs=query_hospital_location(dept);call={'type':'tool_call','tool':'query_hospital_location','args':{'department':dept},'result':obs};final={'type':'final_answer','text':dept+'位于'+obs['location']+'。'}
  other='儿科';wrong={'type':'tool_call','tool':'query_hospital_location','args':{'department':other},'result':query_hospital_location(other)}
  variants=[('reference',True,[call,final]),('duplicate_read',True,[call,copy.deepcopy(call),final]),('wrong_final_value',False,[call,{'type':'final_answer','text':dept+'位于门诊楼 99 层 Z 区。'}]),('missing_final',False,[call]),('wrong_entity',False,[wrong,{'type':'final_answer','text':dept+'位于'+wrong['result']['location']+'。'}])]
  for kind,label,tr in variants:
   d=asyncio.run(score(tr,expected[tid]));calls=[x['tool'] for x in tr if x['type']=='tool_call'];v=aggregate(d);vd=aggregate(rescore(d,'must',expected[tid]['correct_tools'],calls,'D'))
   records.append({'task_id':tid,'kind':kind,'oracle_valid':label,'trajectory':tr,'scores':d,'legacy_score':v,'legacy_pass':v>=.75,'relaxed_D_score':vd,'relaxed_D_pass':vd>=.75})
 summary={}
 for kind in ['reference','duplicate_read','wrong_final_value','missing_final','wrong_entity']:
  rr=[r for r in records if r['kind']==kind];summary[kind]={'n':len(rr),'expected_valid':rr[0]['oracle_valid'],'mean_legacy':sum(r['legacy_score'] for r in rr)/len(rr),'legacy_accepted':sum(r['legacy_pass'] for r in rr),'mean_D':sum(r['relaxed_D_score'] for r in rr)/len(rr),'D_accepted':sum(r['relaxed_D_pass'] for r in rr)}
 result={'scope':'Closed-world constructed location probes; no model calls; not a prevalence estimate','summary':summary,'records':records};(out/'constructed_diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
