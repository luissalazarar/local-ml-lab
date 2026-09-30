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
    throw new Error(body?.error?.message ?? body?.detail ?? `Error ${res.status}`)
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
export type ColumnProfile = {column_id:string,display_name:string,inferred_semantic_type:string,null_count:number,distinct_count:number,possible_id:boolean,quality_issue_codes:string[]}
export type Profile = {row_count:number,column_count:number,duplicate_count:number,columns:ColumnProfile[],sampled:boolean}
export type Run = {id:string,display_name:string,goal:string,problem_type:string,status:string,result_available:boolean,created_at:string,latest_job_id?:string,reliability?:string}
export type Result = {run_id:string,goal:string,problem_type:string,dataset_summary:{row_count:number,column_count:number},selection_decision?:{model_id:string},evaluation_metrics:Array<{metric_id:string,name:string,value:number|null,unit:string,n_used:number,reason_code?:string}>,candidates:Array<{model_id:string,display_name:string,status:string,primary_value?:number}>,baseline_comparison?:{observed_predictive_utility:string},reliability:{primary_level:string,reasons:string[],is_probability:boolean},drivers:Array<{source_column_id:string,importance_mean:number}>,limitations:string[],predictions:Array<Record<string,unknown>>}

