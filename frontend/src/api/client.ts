import { systemError } from '../presentation/labels'

let csrf = ''

export async function bootstrap() {
  const res = await fetch('/api/v1/session', {credentials:'same-origin'})
  if (!res.ok) throw new Error('No se pudo iniciar la sesión local')
  const data = await res.json(); csrf = data.csrf_token
  return data
}

export async function api<T>(path:string, options:RequestInit = {}):Promise<T> {
  const method = options.method ?? 'GET'
  const headers = new Headers(options.headers)
  if (!['GET','HEAD','OPTIONS'].includes(method) && csrf) headers.set('X-CSRF-Token', csrf)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json')
  const res = await fetch(`/api/v1${path}`, {...options, headers, credentials:'same-origin'})
  if (!res.ok) {
    const body = await res.json().catch(()=>null)
    const detail = body?.error?.message ?? body?.detail
    throw new Error(systemError(typeof detail === 'string' ? detail : detail?.message ?? `Error ${res.status}`))
  }
  return res.json()
}

export async function waitJob(jobId:string, onUpdate?:(j:Job)=>void):Promise<Job> {
  for (let i=0;i<300;i++) {
    const job = await api<Job>(`/jobs/${jobId}`); onUpdate?.(job)
    if (['succeeded','succeeded_with_warnings'].includes(job.status)) return job
    if (['failed','cancelled','interrupted'].includes(job.status)) throw new Error(job.error_code ?? `Trabajo ${job.status}`)
    await new Promise(r=>setTimeout(r,1000))
  }
  throw new Error('El trabajo superó el tiempo de espera')
}

export type Job = {id:string,status:string,progress:{stage?:string,message?:string,completed_units?:number,total_units?:number|null},error_code?:string}
export type LiveMetric = {metric_id:string;name:string;value:number|null;unit:string;n_used:number;reason_code?:string|null}
export type LivePrediction = {row_id?:string;record_id?:string;target_period?:string;origin_period?:string;actual?:unknown;predicted?:unknown;error?:unknown;horizon?:number;unit_id?:string}
export type LiveCandidate = {candidate_id:string;model_id?:string;display_name?:string;status:string;primary_metric_id?:string|null;primary_value?:number|null;completed_unit_count?:number;planned_unit_count?:number;reason_code?:string;complexity_rank?:number}
export type LiveRun = {
  event_version:string;run_id:string;job_id:string;attempt_id:string;status:string;
  started_at:string;heartbeat_at:string|null;revision:number;result_available:boolean;
  plan_summary?:{problem_type?:string;primary_metric?:string;metric_direction?:string;candidate_count?:number;eligible_candidate_count?:number;evaluation_unit_count?:number;validation_strategy?:string;population_count?:number;reserved_test?:boolean};
  counters:{completed_candidates:number;eligible_candidates:number;completed_evaluations:number;planned_evaluations:number|null};
  candidates:LiveCandidate[];ranking:LiveCandidate[];active_candidate_id?:string|null;active_unit_id?:string|null;
  active_preview?:{candidate_id:string;unit_id:string;evaluation_role:string;partial_metrics:LiveMetric[];unit_metrics:LiveMetric[];predictions:LivePrediction[];training_end?:string}|null;
  selection_decision?:{selected_candidate_id:string;best_observed_candidate_id:string;baseline_candidate_id:string;reason?:string;reason_code?:string}|null;
  final_test?:unknown;last_events:Array<{seq:number;timestamp:string;event_type:string;stage:string;candidate_id?:string;unit_id?:string;message_code:string}>;
}

const liveEtags = new Map<string,string>()
export async function getLiveRun(runId:string):Promise<LiveRun|null> {
  const headers = new Headers()
  const etag = liveEtags.get(runId)
  if (etag) headers.set('If-None-Match', etag)
  const res = await fetch(`/api/v1/runs/${runId}/live`, {headers, credentials:'same-origin'})
  if (res.status === 304) return null
  if (!res.ok) throw new Error(`Error ${res.status}`)
  const next = res.headers.get('ETag')
  if (next) liveEtags.set(runId, next)
  return res.json()
}
export type ColumnProfile = {column_id:string,display_name:string,source_name?:string,position?:number,inferred_semantic_type:string,null_count:number,distinct_count:number,possible_id:boolean,configured_role?:'variable'|'identifier'|'ignore',examples?:unknown[],quality_issue_codes:string[]}
export type Profile = {row_count:number,column_count:number,duplicate_count:number,columns:ColumnProfile[],sampled:boolean}
export type Run = {id:string,display_name:string,goal:string,problem_type:string,status:string,result_available:boolean,created_at:string,latest_job_id?:string,reliability?:string,dataset_version_id?:string,dataset_version_kind?:'original'|'prepared',preparation_summary?:{transformations?:unknown[],rows_quarantined?:number}}
export type Prediction = {row_id?:string,record_id?:string,target_period?:string,origin_period?:string,unit_id?:string,evaluation_role:string,actual?:unknown,predicted?:unknown,error?:unknown,unit?:string}
export type Result = {run_id:string,goal:string,problem_type:string,analytical_outcome?:string,primary_metric_id:string|null,dataset_summary:{row_count:number,column_count:number},data_quality:{columns:Array<{column_id:string,display_name:string}>},data_preparation?:{dataset_version_id?:string;transformations?:Array<{transformation?:string}>;rows_input?:number;rows_analyzed?:number;rows_quarantined?:number;target_missing_rows?:number},validation_plan:{strategy?:string,population_scope?:string,evidence_mode?:string,limitations?:string[];reserved_test_periods?:string[]},selection_decision?:{model_id:string;selected_candidate_id?:string;best_observed_candidate_id?:string;baseline_candidate_id?:string;reason?:string;reason_code?:string;policy_version?:string},evaluation_metrics:Array<{metric_id:string,name:string,value:number|null,unit:string,n_used:number,evaluation_role?:string,reason_code?:string}>,candidates:Array<{candidate_id?:string;model_id:string,display_name:string,status:string,primary_value?:number|null;reason_code?:string;completed_unit_count?:number;planned_unit_count?:number}>,baseline_comparison?:{baseline_model_id?:string|null;best_observed_model_id?:string;selected_model_id?:string;observed_predictive_utility:string},final_test?:{selection_improvement_repeated?:boolean}|null,reliability:{primary_level:string,reasons:string[],is_probability:boolean},drivers:Array<{source_column_id:string,importance_mean:number,importance_std?:number|null,evaluation_role?:string,warnings?:string[]}>,diagnostics:{class_labels?:string[],class_support?:Array<{label:string,count:number}>,confusion_matrix?:number[][]},limitations:string[],predictions:Prediction[]}
