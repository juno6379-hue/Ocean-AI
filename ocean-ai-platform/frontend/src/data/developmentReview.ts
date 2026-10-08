/** Network review receipts are display evidence; they never grant actor authority. */
export type TrainingReview={status:string;manifest_sha256:string;manifest_path:string;training_eligible:boolean;
  blockers?:{code:string;detail:string}[];coverage?:unknown;origin_membership_sha256?:string};
export type Stage={stage_id:number;title:string;implementation:string;verification:string;data_readiness:string;
  approval:string;operational_status:string;reasons?:string[];next_required:string[];
  evidence:{path:string|null;sha256:string|null;verified:boolean;error?:string|null}[]};
const hash=(value:unknown):value is string=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
export function trainingReviewMatches(value:unknown,manifest:{path:string;sha256?:string}|undefined){
  if(!value||typeof value!=='object'||!manifest)return false;
  const review=value as TrainingReview;
  return review.status==='READY'&&review.training_eligible===true&&hash(review.manifest_sha256)&&
    hash(review.origin_membership_sha256)&&review.manifest_sha256===manifest.sha256&&review.manifest_path===manifest.path;
}
const axes:Record<string,string[]>={implementation:['IMPLEMENTED','PARTIAL','UNKNOWN'],verification:['VERIFIED','PARTIAL','FAILED','UNKNOWN'],
  data_readiness:['READY','PARTIAL','BLOCKED','UNKNOWN'],approval:['APPROVED','PENDING','NOT_APPLICABLE','UNKNOWN'],
  operational_status:['OPERATING','ANALYSIS_ONLY','BLOCKED','NOT_STARTED','UNKNOWN']};
const strings=(value:unknown):value is string[]=>Array.isArray(value)&&value.every(v=>typeof v==='string');
export function validStageReview(value:unknown):value is {checked_at:string;stages:Stage[]}{
  if(!value||typeof value!=='object')return false;
  const body=value as Record<string,any>;
  return body.schema_version==='development-stage-review-v1'&&body.approved===false&&typeof body.checked_at==='string'&&
    Array.isArray(body.stages)&&body.stages.length===13&&new Set(body.stages.map((s:any)=>s?.stage_id)).size===13&&body.stages.every((stage:any)=>
      stage&&Number.isInteger(stage.stage_id)&&stage.stage_id>=1&&stage.stage_id<=13&&typeof stage.title==='string'&&
      Object.entries(axes).every(([axis,allowed])=>allowed.includes(stage[axis]))&&strings(stage.next_required)&&
      (stage.reasons===undefined||strings(stage.reasons))&&Array.isArray(stage.evidence)&&stage.evidence.every((e:any)=>
        e&&typeof e.verified==='boolean'&&(e.path===null||typeof e.path==='string')&&(e.sha256===null||hash(e.sha256))&&
        (e.error===undefined||e.error===null||typeof e.error==='string')));
}
