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
    if (['failed','cancelled','interrupted'].includes(job.status)) throw new Error(systemError(job.error_code ?? `Trabajo ${job.status}`))
    await new Promise(r=>setTimeout(r,1000))
  }
  throw new Error('El trabajo superó el tiempo de espera')
}

export type Job = {id:string,status:string,progress:{stage?:string,message?:string,completed_units?:number,total_units?:number|null},error_code?:string}
export type LiveMetric = {metric_id:string;name:string;value:number|null;unit:string;n_used:number;reason_code?:string|null}
export type LivePrediction = {row_id?:string;record_id?:string;target_period?:string;origin_period?:string;actual?:unknown;predicted?:unknown;error?:unknown;horizon?:number;unit_id?:string}
export type LiveDiagnostics = {median_absolute_error?:number;p90_absolute_error?:number;error_histogram?:{counts:number[];edges:number[];zero_reference:number};error_by_horizon?:Array<{horizon:number;n_predictions:number;mae:number}>;class_labels?:string[];class_support?:Array<{label:string;count:number}>;confusion_matrix?:number[][];per_class?:Array<{label:string;support:number;precision:number|null;recall:number|null;f1:number|null}>}
export type LivePreview = {candidate_id:string;unit_id:string;evaluation_role:string;partial_metrics:LiveMetric[];unit_metrics:LiveMetric[];predictions:LivePrediction[];training_end?:string;training_history?:Array<{target_period:string;actual:number}>;diagnostics?:LiveDiagnostics;sha256?:string;count_preview?:number;count_complete?:number;preview_sha256?:string}
export type LiveCandidate = {candidate_id:string;model_id?:string;display_name?:string;status:string;primary_metric_id?:string|null;primary_value?:number|null;completed_unit_count?:number;planned_unit_count?:number;reason_code?:string;complexity_rank?:number;partial_metrics?:LiveMetric[]}
export type SelectionDecision = {selected_candidate_id:string;provisional_selected_candidate_id?:string;best_observed_candidate_id:string;baseline_candidate_id:string;reason?:string;reason_code?:string;policy_version?:string;minimum_practical_gain?:number;won_units?:number;paired_units?:number;candidate_decisions?:Array<{candidate_id:string;joint_improvement:number|null;paired_units:number;won_units:number;required_wins:number;median_paired_improvement:number|null;passes_gate:boolean;reason_code:string}>;metric_trajectories?:Record<string,Array<{unit_number:number;unit_id:string;candidate_value:number|null;baseline_value:number|null}>>;confirmation_status?:string}
export type Confirmation = {status:string;reason_code?:string;split_count?:number;won_pairs?:number;required_wins?:number;paired_improvements?:number[];baseline?:{candidate_id:string;primary_value:number};provisional_selected?:{candidate_id:string;primary_value:number}}
export type LiveRun = {
  event_version:string;run_id:string;job_id:string;attempt_id:string;status:string;
  started_at:string;heartbeat_at:string|null;revision:number;result_available:boolean;
  plan_summary?:{problem_type?:string;primary_metric?:string;metric_direction?:string;candidate_count?:number;eligible_candidate_count?:number;evaluation_unit_count?:number;validation_strategy?:string;population_count?:number;reserved_test?:boolean;baseline_candidate_id?:string;baseline_candidate_ids?:string[];target_column_id?:string;target_display_name?:string;units?:string};
  counters:{completed_candidates:number;eligible_candidates:number;completed_evaluations:number;planned_evaluations:number|null};
  candidates:LiveCandidate[];ranking:LiveCandidate[];active_candidate_id?:string|null;active_unit_id?:string|null;
  active_preview?:LivePreview|null;preview_index?:Record<string,Record<string,Omit<LivePreview,'predictions'>>>;primary_selection_decision?:SelectionDecision|null;
  selection_decision?:SelectionDecision|null;confirmation?:Confirmation|null;
  final_test?:{selected?:{candidate_id:string;primary_value:number};baseline?:{candidate_id:string;primary_value:number};selection_improvement_repeated?:boolean}|null;last_events:Array<{seq:number;timestamp:string;event_type:string;stage:string;candidate_id?:string;unit_id?:string;message_code:string}>;
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
export async function getLivePreview(runId:string,candidateId:string,unitId?:string):Promise<LivePreview>{
  const query=unitId?`?unit_id=${encodeURIComponent(unitId)}`:''
  return api<LivePreview>(`/runs/${runId}/live-preview/${candidateId}${query}`)
}
export type ReplayEvent={seq:number;event_type:string;stage:string;message_code:string;created_at:string;payload:Record<string,unknown>}
export async function getRunReplay(runId:string):Promise<{terminal:boolean;items:ReplayEvent[]}>{return api(`/runs/${runId}/replay?limit=200`)}
export type ColumnProfile = {column_id:string,display_name:string,source_name?:string,position?:number,inferred_semantic_type:string,null_count:number,distinct_count:number,possible_id:boolean,configured_role?:'variable'|'identifier'|'ignore',examples?:unknown[],quality_issue_codes:string[]}
export type ProfileVisualizations = {sample_method:'deterministic_stride';sample_count:number;source_row_count:number;numeric_columns:Array<{column_id:string;display_name:string}>;correlation:{method:'pearson';column_ids:string[];display_names:string[];values:Array<Array<number|null>>};boxplots:Array<{column_id:string;display_name:string;minimum:number;q1:number;median:number;q3:number;maximum:number;outlier_count:number;n:number}>;scatterplots:Array<{x_column_id:string;x_display_name:string;y_column_id:string;y_display_name:string;correlation:number;points:Array<[number,number]>}>;excluded_numeric_count:number}
export type Profile = {row_count:number,column_count:number,duplicate_count:number,columns:ColumnProfile[],sampled:boolean;visualizations?:ProfileVisualizations}
export type Run = {id:string,display_name:string,goal:string,problem_type:string,status:string,result_available:boolean,created_at:string,latest_job_id?:string,reliability?:string,dataset_version_id?:string,dataset_version_kind?:'original'|'prepared',dataset_original_name?:string;selected_model_name?:string;baseline_model_name?:string;result_summary?:string;preparation_summary?:{transformations?:unknown[],rows_quarantined?:number}}
export type Prediction = {row_id?:string,record_id?:string,target_period?:string,origin_period?:string,unit_id?:string,evaluation_role:string,actual?:unknown,predicted?:unknown,error?:unknown,unit?:string}
export type ScenarioControl = {column_id:string;display_name:string;kind:'numeric'|'categorical';editable:boolean;default:number|string;minimum?:number;maximum?:number;step?:number;options?:string[];options_truncated?:boolean;importance_mean?:number|null}
export type ScenarioMetadata = {available:boolean;reason_code?:string;model_id?:string;model_name?:string;model_family?:string;training_depth?:'quick'|'recommended';target_column_id?:string;target_name?:string;problem_type?:'regression'|'classification';fit_scope?:string;fit_row_count?:number;source_row_count?:number;sample_method?:string;controls?:ScenarioControl[];class_labels?:string[];warnings?:string[]}
export type ScenarioResponse = {prediction:number|string;class_label?:string;probability?:number;driver_id:string;driver_name:string;curve_unit:string;model_family?:string;training_depth?:'quick'|'recommended';curve_shape?:'approximately_linear'|'nonlinear'|'flat'|'categorical';sensitivity_direction?:'increasing'|'decreasing'|'mixed'|'flat'|'categorical';curve:Array<{input:number|string;output:number}>;warnings:string[]}
export type Result = {run_id:string,goal:string,problem_type:string,analytical_outcome?:string,primary_metric_id:string|null,dataset_summary:{row_count:number,column_count:number},data_quality:{columns:Array<{column_id:string,display_name:string}>},data_preparation?:{dataset_version_id?:string;transformations?:Array<{transformation?:string}>;rows_input?:number;rows_analyzed?:number;rows_quarantined?:number;target_missing_rows?:number},validation_plan:{strategy?:string,population_scope?:string,evidence_mode?:string,limitations?:string[];reserved_test_periods?:string[];holdout_row_ids?:string[];holdout_reason?:string},selection_decision?:SelectionDecision&{model_id:string},confirmation?:Confirmation,evaluation_metrics:Array<{metric_id:string,name:string,value:number|null,unit:string,n_used:number,evaluation_role?:string,reason_code?:string}>,candidates:Array<{candidate_id?:string;model_id:string,display_name:string,status:string,primary_value?:number|null;reason_code?:string;completed_unit_count?:number;planned_unit_count?:number;parameters?:Record<string,unknown>}>,baseline_comparison?:{baseline_model_id?:string|null;best_observed_model_id?:string;selected_model_id?:string;observed_predictive_utility:string},final_test?:{selected?:{candidate_id:string;primary_value:number};baseline?:{candidate_id:string;primary_value:number};selection_improvement_repeated?:boolean}|null,reliability:{primary_level:string,reasons:string[],is_probability:boolean},drivers:Array<{source_column_id:string,importance_mean:number,importance_std?:number|null,evaluation_role?:string,warnings?:string[]}>,scenario_explorer?:ScenarioMetadata,diagnostics:LiveDiagnostics&{warnings?:string[];forecast_horizon_stability?:{warning_code?:string|null}},forecast?:{selected_candidate_id:string;horizon:number;horizon_diagnostics?:Array<{horizon:number;n_predictions:number;selected_mae:number;selected_rmse:number;baseline_mae:number;baseline_rmse:number;mae_difference:number;relative_improvement:number|null;outcome:string}>;horizon_stability?:{horizons_evaluated:number;horizons_better_than_baseline:number;horizons_similar:number;horizons_worse:number;best_relative_improvement:number|null;worst_relative_degradation:number;warning_code?:string|null}},limitations:string[],predictions:Prediction[]}
