const counter=(value:unknown)=>typeof value==='number'&&Number.isInteger(value)&&value>=0;
const sample=(value:any)=>value?.source==='SIMULATION'&&value.is_simulation===true&&value.approved===false;
const strings=(value:unknown)=>Array.isArray(value)&&value.every(item=>typeof item==='string');
const clock=(value:unknown)=>{
  const literal=String(value??'').replace('T',' ');
  return /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d{1,6})?$/.test(literal)?(literal.includes('.')?literal:literal+'.').padEnd(26,'0'):null;
};
export function validSimulationScenarios(value:any) {
  return sample(value)&&Array.isArray(value.scenarios)&&value.scenarios.length>0&&
    new Set(value.scenarios.map((item:any)=>item?.scenario_id)).size===value.scenarios.length&&value.scenarios.every((item:any)=>
      item&&typeof item.scenario_id==='string'&&/^[a-zA-Z0-9_-]{1,80}$/.test(item.scenario_id)&&typeof item.label==='string'&&typeof item.description==='string'&&
      ['NORMAL','WARNING','ABNORMAL','UNVERIFIED'].includes(item.expected_operation_state));
}
export function validSimulationResult(value:any,scenario:string,day:string,time:string) {
  if(!sample(value)||value.production_completed!==false||value.scenario_id!==scenario||value.as_of_day!==day||value.as_of_time!==time||
    clock(value.cutoff_native)!==clock(day+' '+time)||typeof value.label!=='string'||!/^[a-f0-9]{64}$/.test(value.result_sha256||'')||
    !Array.isArray(value.rows)||!value.rows.every((row:any)=>row&&clock(row.observed_time_raw))||!value.operation)return false;
  const p=value.quality_pipeline;
  if(!p||!p.rule||!p.ai||!p.fusion||!p.workflow)return false;
  for(const stage of [p.rule,p.ai])if(!['EVALUATED','NOT_EVALUATED'].includes(stage.status)||!counter(stage.evaluated_count)||!counter(stage.anomaly_count))return false;
  const modes=p.ai.modes;
  if(!modes||typeof modes!=='object'||Array.isArray(modes)||!Object.keys(modes).length||!Object.entries(modes).every(([name,counts]:[string,any])=>/^[A-Z_]+$/.test(name)&&counter(counts?.evaluated_count)&&counter(counts?.anomaly_count)))return false;
  if(!counter(p.rule.not_evaluated_count)||!['ANALYSIS_ONLY','EVALUATED','NOT_EVALUATED'].includes(p.fusion.status)||
    typeof p.fusion.recommendation!=='string'||!strings(p.fusion.missing_categories)||
    p.fusion.recommendation_score!==null&&(typeof p.fusion.recommendation_score!=='number'||!Number.isFinite(p.fusion.recommendation_score)))return false;
  if(p.workflow.status!=='COMPLETED'||p.workflow.production_writes!==0||!strings(p.workflow.transitions)||
    !['pending_stopped','unapproved_resume_blocked','reviewer_required','rejected_resume_blocked','resumed_once'].every(key=>typeof p.workflow[key]==='boolean'))return false;
  return Array.isArray(value.assertions)&&value.assertions.length>0&&new Set(value.assertions.map((a:any)=>a?.name)).size===value.assertions.length&&
    value.assertions.every((a:any)=>a&&typeof a.name==='string'&&typeof a.passed==='boolean'&&typeof a.detail==='string');
}

/** The synthetic fixture may contain future traps; plot only its selected native cutoff. */
export function simulationChartRows(value:any) {
  const end=clock(value.cutoff_native);
  return (value.rows||[]).map((row:any,index:number)=>({...row,filename:'SIMULATION/'+value.scenario_id,file_row_number:index}))
    .filter((row:any)=>{const observed=clock(row.observed_time_raw);return end&&observed&&observed<=end;})
    .sort((a:any,b:any)=>String(b.observed_time_raw).replace('T',' ').localeCompare(String(a.observed_time_raw).replace('T',' '))||b.file_row_number-a.file_row_number);
}
