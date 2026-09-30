import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, Profile, waitJob } from "../../api/client";
import { excelChecklist, explain } from "../../education/concepts";
import { ConceptHelp } from "../../education/ConceptHelp";
import { DataFlow } from "../../education/DataFlow";

type Goal = "estimate_value" | "classify" | "forecast" | "drivers" | "explore";
type DatasetInfo = { safe_extension: string; metadata_json: { sheet_names?: string[] } };
type ExamplePreset = { id:string; name:string; description:string; filename:string; format:string; goal:Goal; problem_type:string; target:{name:string}|null; date_column:{name:string}|null; included_columns:string[]; primary_metric:string|null; depth:string; forecast_horizon:number|null; aggregation:string|null; parser_options:Record<string,unknown>; what_you_learn:string };
type Preflight = { id:string; config_sha256:string; can_run:boolean; blockers:Array<{code:string;explanation:string;suggestion:string}>; warnings:Array<{code:string;explanation:string;suggestion:string}>; explanation:string; suggestions:string[] };
type ColumnPreparation = {type:'auto'|'numeric'|'date'|'categorical'|'text';role:'variable'|'identifier'|'ignore';trim?:boolean;empty_to_missing?:boolean;date_format?:'DMY'|'MDY'|'YMD'|'UNAMBIGUOUS';excel_date_serials?:boolean;decimal_separator?:'.'|',';thousands_separator?:'.'|','|' ';percent?:boolean;currency?:'PEN'|'USD'|'EUR';invalid?:'block'|'segregate';category_merges?:Record<string,string>};
type RowFilter = {kind:'date_range';column_id:string;start?:string;end?:string}|{kind:'category';column_id:string;mode:'include'|'exclude';values:string[]}|{kind:'numeric_not_null';column_id:string};
type PreparationRecipe = {schema_version:'1.0';columns:Record<string,ColumnPreparation>;expected_columns:Record<string,string>;exact_duplicates:'keep'|'exclude';filters:RowFilter[]};
type PreparationSuggestion = {column_id:string;display_name:string;inferred_semantic_type:string;null_count:number;distinct_count:number;possible_id:boolean;examples:unknown[];alerts:string[];recommended:ColumnPreparation};
type PreparationPreview = {rows_input:number;rows_output:number;rows_quarantined:number;preview:Array<{row_id:string;column_id:string;before:unknown;after:unknown}>;quarantined:Array<{row_id:string;reason:string;column_id?:string;original_value?:unknown}>;transformations:Array<{column_id?:string;transformation:string;affected_count:number;invalid_count:number}>;quality:{original:Record<string,number>;prepared:Record<string,number>}};
type TemporalCheck = {first_date:string|null;last_date:string|null;frequency:string;observed_months:number;missing_months:string[];duplicate_month_rows:number;invalid_or_missing_dates:number;monthly_aggregation_required:boolean};
const goals: Array<{ id: Goal; title: string; desc: string }> = [
  {
    id: "estimate_value",
    title: "Estimar un valor",
    desc: "Para cantidades, costos o duración.",
  },
  {
    id: "classify",
    title: "Predecir una categoría",
    desc: "Para respuestas como sí/no o tipos.",
  },
  {
    id: "forecast",
    title: "Estimar próximas fechas",
    desc: "Para una serie mensual, sin meses faltantes.",
  },
  {
    id: "drivers",
    title: "Entender variables útiles",
    desc: "Reutiliza una evaluación predictiva.",
  },
  {
    id: "explore",
    title: "Explorar mi data",
    desc: "Sin entrenamiento obligatorio.",
  },
];
export function Wizard() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [dataset, setDataset] = useState("");
  const [version, setVersion] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [goal, setGoal] = useState<Goal>("estimate_value");
  const [target, setTarget] = useState("");
  const [dateCol, setDateCol] = useState("");
  const [depth, setDepth] = useState("quick");
  const [included, setIncluded] = useState<string[]>([]);
  const [xlsxInfo, setXlsxInfo] = useState<DatasetInfo | null>(null);
  const [sheetName, setSheetName] = useState("");
  const [headerRow, setHeaderRow] = useState(1);
  const [primaryMetric, setPrimaryMetric] = useState("");
  const [horizon, setHorizon] = useState(3);
  const [aggregation, setAggregation] = useState("");
  const [examples, setExamples] = useState<ExamplePreset[]>([]);
  const [selectedExample, setSelectedExample] = useState<ExamplePreset | null>(null);
  const [preflight, setPreflight] = useState<Preflight | null>(null);
  const [suggestions, setSuggestions] = useState<PreparationSuggestion[]>([]);
  const [recipe, setRecipe] = useState<PreparationRecipe>({schema_version:'1.0',columns:{},expected_columns:{},exact_duplicates:'keep',filters:[]});
  const [preparationPreview, setPreparationPreview] = useState<PreparationPreview | null>(null);
  const [prepared, setPrepared] = useState(false);
  const [temporalCheck, setTemporalCheck] = useState<TemporalCheck | null>(null);
  const [selectedColumnId, setSelectedColumnId] = useState('');
  const [columnSearch, setColumnSearch] = useState('');
  const [columnFilter, setColumnFilter] = useState<'all'|'review'|'identifier'|'ignore'|'ready'>('all');
  const [reviewedColumns, setReviewedColumns] = useState<string[]>([]);
  const [filterDraft, setFilterDraft] = useState({kind:'date_range',column_id:'',start:'',end:'',mode:'include',values:''});
  const [mappingDraft, setMappingDraft] = useState({column_id:'',from:'',to:''});
  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      setStatus("Subiendo archivo…");
      const created = await api<{ dataset_id: string; job_id: string }>(
        "/datasets",
        { method: "POST", body: form },
      );
      setDataset(created.dataset_id);
      await waitJob(created.job_id, (j) =>
        setStatus(j.progress.message ?? "Inspeccionando…"),
      );
      const info = await api<DatasetInfo>(`/datasets/${created.dataset_id}`);
      if (info.safe_extension === ".xlsx") {
        setXlsxInfo(info);
        setSheetName(info.metadata_json.sheet_names?.[0] ?? "");
        setStatus("");
      } else {
        await prepare(created.dataset_id);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const prepare = useCallback(async (id: string, options: Record<string, unknown> = {}, preset?: ExamplePreset) => {
    setStatus("Preparando una versión auditable…");
    const made = await api<{ dataset_version_id: string; job_id: string }>(
      `/datasets/${id}/versions`,
      { method: "POST", body: JSON.stringify(options) },
    );
    setVersion(made.dataset_version_id);
    await waitJob(made.job_id, (j) =>
      setStatus(j.progress.message ?? "Perfilando…"),
    );
    const p = await api<Profile>(
      `/dataset-versions/${made.dataset_version_id}/profile`,
    );
    setProfile(p);
    const detected = await api<{columns:PreparationSuggestion[]}>(`/dataset-versions/${made.dataset_version_id}/preparation-suggestions`);
    setSuggestions(detected.columns);
    setSelectedColumnId(detected.columns[0]?.column_id ?? '');
    setReviewedColumns(detected.columns.filter(column => !column.alerts.length).map(column => column.column_id));
    setRecipe({schema_version:'1.0',columns:Object.fromEntries(detected.columns.map((column) => [column.column_id, {type:'auto',role:column.possible_id ? 'identifier' : 'variable',trim:false,empty_to_missing:false,invalid:'block'}])),expected_columns:Object.fromEntries(detected.columns.map((column) => [column.column_id,column.display_name])),exact_duplicates:'keep',filters:[]});
    setPrepared(false);
    setPreparationPreview(null);
    const byName = (name?: string) => p.columns.find((column) => column.display_name === name)?.column_id ?? "";
    setIncluded(preset ? preset.included_columns.map((name) => byName(name)).filter(Boolean) : p.columns.filter((column) => !column.possible_id).map((column) => column.column_id));
    if (preset) {
      setSelectedExample(preset);
      setGoal(preset.goal);
      setTarget(byName(preset.target?.name));
      setDateCol(byName(preset.date_column?.name));
      setDepth(preset.depth);
      setPrimaryMetric(preset.primary_metric ?? "");
      setHorizon(preset.forecast_horizon ?? 3);
      setAggregation(preset.aggregation ?? "");
    }
    setStep(2);
    setStatus("");
  }, []);
  const loadExample = useCallback(
    async (id: string) => {
      setBusy(true);
      setError("");
      try {
        setStatus("Copiando ejemplo sintético…");
        const created = await api<{ dataset_id: string; job_id: string }>(
          `/datasets/from-example/${id}`,
          { method: "POST" },
        );
        setDataset(created.dataset_id);
        await waitJob(created.job_id, (j) =>
          setStatus(j.progress.message ?? "Inspeccionando…"),
        );
        const preset = examples.find((item) => item.id === id);
        if (!preset) throw new Error("No encontramos la configuración del ejemplo.");
        await prepare(created.dataset_id, preset.parser_options, preset);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [examples, prepare],
  );
  useEffect(() => {
    void api<{items:ExamplePreset[]}>("/examples").then((data) => setExamples(data.items ?? [])).catch((reason:Error) => setError(reason.message));
  }, []);
  useEffect(() => {
    const ex = params.get("example");
    if (ex && !dataset && examples.length) void loadExample(ex);
  }, [dataset, examples.length, loadExample, params]);
  useEffect(() => {
    if (goal !== 'forecast' || !dateCol || !version) { setTemporalCheck(null); return; }
    void api<TemporalCheck>(`/dataset-versions/${version}/temporal-check?date_column_id=${encodeURIComponent(dateCol)}`).then(setTemporalCheck).catch((reason:Error) => setError(reason.message));
  }, [dateCol, goal, version]);
  const available = profile?.columns.filter((c) => (c.configured_role ?? (c.possible_id ? 'identifier' : 'variable')) === 'variable') ?? [];
  const selected = useMemo(
    () => profile?.columns.find((c) => c.column_id === target),
    [profile, target],
  );
  const resolvedProblem =
    goal === "classify"
      ? "classification"
      : goal === "forecast"
        ? "forecasting"
        : goal === "explore"
          ? "exploration"
          : goal === "estimate_value"
            ? "regression"
            : selected?.inferred_semantic_type === "categorical"
            ? "classification"
            : "regression";
  const defaultMetric = resolvedProblem === "classification" ? "balanced_accuracy" : "mae";
  function continueGoal() {
    if (goal !== "explore" && !target) {
      setError("Elige la columna que quieres analizar.");
      return;
    }
    if (goal === "forecast" && !dateCol) {
      setError("Elige la columna de fecha.");
      return;
    }
    if (goal === "estimate_value" && selected?.inferred_semantic_type !== "numeric") {
      setError("Estimar un valor necesita un resultado numérico. Elige una columna numérica o cambia de objetivo.");
      return;
    }
    if (goal === "classify" && selected?.inferred_semantic_type !== "categorical") {
      setError("Predecir una categoría necesita etiquetas. No convertimos automáticamente un número continuo en clases.");
      return;
    }
    setError("");
    setPreflight(null);
    setStep(5);
  }
  function analysisConfig() {
    return {
      schema_version: "1.0",
      dataset_version_id: version,
      goal,
      problem_type: resolvedProblem,
      target_column_id: goal === "explore" ? null : target,
      date_column_id: goal === "forecast" ? dateCol : null,
      included_column_ids: included,
      excluded_column_ids: profile?.columns.filter((c) => (c.configured_role ?? (c.possible_id ? 'identifier' : 'variable')) !== 'variable').map((c) => c.column_id) ?? [],
      depth,
      primary_metric: goal === "explore" ? null : primaryMetric || defaultMetric,
      validation_context: "independent_records",
      seed: 42,
      forecast_options: goal === "forecast" ? { horizon, aggregation } : null,
    };
  }
  async function checkConfiguration() {
    setBusy(true);
    setError("");
    try {
      setStatus("Comprobando que la evaluación sea defendible…");
      const pf = await api<{ preflight_id: string; job_id: string }>(
        "/preflights",
        { method: "POST", body: JSON.stringify({ config: analysisConfig() }) },
      );
      await waitJob(pf.job_id, (j) =>
        setStatus(j.progress.message ?? "Preparando evaluación…"),
      );
      const ready = await api<Preflight>(
        `/preflights/${pf.preflight_id}`,
      );
      setPreflight(ready);
      setStatus("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function run() {
    if (!preflight?.can_run) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<{ run_id: string; job_id: string }>("/runs", {
        method: "POST",
        body: JSON.stringify({
          preflight_id: preflight.id,
          config_sha256: preflight.config_sha256,
        }),
      });
      nav(`/runs/${created.run_id}/progress?job=${created.job_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  function updateColumn(columnId:string, patch:Partial<ColumnPreparation>) {
    setRecipe((current) => ({...current, columns:{...current.columns, [columnId]:{...(current.columns[columnId] ?? {type:'auto',role:'variable'}), ...patch}}}));
    setPreparationPreview(null);
    setReviewedColumns((current) => [...new Set([...current, columnId])]);
  }
  function acceptSuggestion(column:PreparationSuggestion) {
    updateColumn(column.column_id, {...column.recommended, invalid:column.recommended.type === 'date' || column.recommended.type === 'numeric' ? 'segregate' : 'block'});
  }
  async function previewPreparation() {
    setBusy(true); setError(''); setStatus('Construyendo vista previa antes/después…');
    try {
      const preview = await api<PreparationPreview>(`/dataset-versions/${version}/preparation-preview`, {method:'POST', body:JSON.stringify({recipe})});
      setPreparationPreview(preview); setStatus('');
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }
  async function createPreparedVersion() {
    if (!preparationPreview) return;
    setBusy(true); setError(''); setStatus('Creando la versión preparada auditable…');
    try {
      const made = await api<{dataset_version_id:string;job_id:string}>(`/dataset-versions/${version}/preparations`, {method:'POST', body:JSON.stringify({recipe})});
      await waitJob(made.job_id, (job) => setStatus(job.progress.message ?? 'Aplicando preparación…'));
      const preparedProfile = await api<Profile>(`/dataset-versions/${made.dataset_version_id}/profile`);
      setVersion(made.dataset_version_id); setProfile(preparedProfile); setPrepared(true);
      const preparedByName = (name:string) => preparedProfile.columns.find((column) => column.display_name === name)?.column_id;
      setIncluded(selectedExample ? selectedExample.included_columns.map(preparedByName).filter((id):id is string => Boolean(id)) : preparedProfile.columns.filter((column) => (column.configured_role ?? 'variable') === 'variable' && column.inferred_semantic_type !== 'datetime').map((column) => column.column_id));
      setTarget(''); setDateCol(''); setPreflight(null); setStep(4); setStatus('');
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }
  async function importRecipe(event:ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as PreparationRecipe;
      await api('/preparations/validate-recipe', {method:'POST', body:JSON.stringify({recipe:parsed})});
      const known = new Map(profile?.columns.map((column) => [column.column_id,column.display_name]));
      if (Object.keys(parsed.columns).some((id) => !known.has(id)) || Object.entries(parsed.expected_columns ?? {}).some(([id,name]) => known.get(id) !== name)) throw new Error('La receta requiere columnas que no existen o cambiaron de nombre.');
      setRecipe(parsed); setPreparationPreview(null); setError('');
    } catch (reason) { setError((reason as Error).message); }
  }
  function downloadRecipe() {
    const blob = new Blob([JSON.stringify(recipe, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'receta-preparacion.json'; anchor.click(); URL.revokeObjectURL(url);
  }
  function addFilter() {
    if (!filterDraft.column_id) return;
    let next:RowFilter;
    if (filterDraft.kind === 'date_range') {
      if (!filterDraft.start && !filterDraft.end) { setError('Indica al menos una fecha desde o hasta.'); return; }
      next = {kind:'date_range',column_id:filterDraft.column_id,start:filterDraft.start || undefined,end:filterDraft.end || undefined};
    } else if (filterDraft.kind === 'category') {
      const values = filterDraft.values.split(',').map(value => value.trim()).filter(Boolean);
      if (!values.length) { setError('Escribe al menos una categoría.'); return; }
      next = {kind:'category',column_id:filterDraft.column_id,mode:filterDraft.mode as 'include'|'exclude',values};
    } else next = {kind:'numeric_not_null',column_id:filterDraft.column_id};
    setRecipe(current => ({...current,filters:[...current.filters,next]})); setPreparationPreview(null); setError('');
  }
  function addCategoryMapping() {
    const {column_id,from,to} = mappingDraft;
    if (!column_id || !from.trim() || !to.trim()) { setError('Elige una columna y completa el valor actual y el valor nuevo.'); return; }
    updateColumn(column_id,{category_merges:{...(recipe.columns[column_id]?.category_merges ?? {}),[from]:to}});
    setMappingDraft(current => ({...current,from:'',to:''})); setError('');
  }
  const targetOptions = available.filter((column) => goal === "classify" ? column.inferred_semantic_type === "categorical" : goal === "estimate_value" || goal === "forecast" ? column.inferred_semantic_type === "numeric" : true);
  const selectedPreparation = suggestions.find(column => column.column_id === selectedColumnId) ?? suggestions[0];
  const filteredSuggestions = suggestions.filter(column => {
    const config = recipe.columns[column.column_id];
    const matchesSearch = column.display_name.toLocaleLowerCase('es').includes(columnSearch.toLocaleLowerCase('es'));
    const matchesFilter = columnFilter === 'all' || (columnFilter === 'review' && column.alerts.length > 0 && !reviewedColumns.includes(column.column_id)) || (columnFilter === 'identifier' && config?.role === 'identifier') || (columnFilter === 'ignore' && config?.role === 'ignore') || (columnFilter === 'ready' && reviewedColumns.includes(column.column_id));
    return matchesSearch && matchesFilter;
  });
  return (
    <main className="wizardPage">
      <div className="wizardHeader">
        <div>
          <span className="eyebrow">NUEVO ANÁLISIS</span>
          <h1>De archivo a evidencia, paso a paso.</h1>
        </div>
        <ol className="stepper" aria-label="Progreso">
          {["Archivo", "Entender", "Preparar", "Objetivo", "Revisar"].map((x, i) => (
            <li
              className={step === i + 1 ? "active" : step > i + 1 ? "done" : ""}
              key={x}
            >
              <span>{step > i + 1 ? "✓" : i + 1}</span>
              {x}
            </li>
          ))}
        </ol>
      </div>
      {error && (
        <div className="alert error" role="alert">
          <strong>No pudimos continuar</strong>
          <span>{error}</span>
        </div>
      )}
      {busy && (
        <div className="alert info" aria-live="polite">
          <div className="loader small" />
          <span>{status}</span>
        </div>
      )}
      {step === 1 && (
        <section className="panel uploadPanel">
          <h2>Sube tu Excel o archivo de datos</h2>
          <p>
            Excel (.xlsx), CSV o Parquet · máximo 100 MiB. Conservamos el original y
            registramos cómo se interpretó.
          </p>
          <label className="dropzone">
            <input
              type="file"
              accept=".csv,.xlsx,.parquet"
              onChange={upload}
              disabled={busy}
            />
            <span className="uploadIcon">↑</span>
            <strong>Arrastra un archivo o selecciónalo</strong>
            <small>
              No ejecutamos fórmulas, macros ni contenido del archivo.
            </small>
          </label>
          <details className="excelHelp" open>
            <summary>¿Cómo debería estar organizado mi Excel?</summary>
            <ul>{excelChecklist.map((item) => <li key={item}>{item}</li>)}</ul>
            <p>Si tu archivo tiene varias hojas, podrás elegir cuál analizar. Laboratorio ML no interpreta el diseño visual de tu Excel como información. Lo importante es la tabla.</p>
            <p><strong>.xls antiguo no está soportado;</strong> guárdalo como .xlsx desde Excel antes de subirlo.</p>
          </details>
          {xlsxInfo && (
            <div className="parseOptions">
              <h3>Cómo leer este Excel</h3>
              <p>Selecciona la hoja y la fila de encabezados. Fórmulas y macros no se ejecutan.</p>
              <div className="formGrid">
                <label>Hoja<select value={sheetName} onChange={(event) => setSheetName(event.target.value)}>{(xlsxInfo.metadata_json.sheet_names ?? []).map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
                <label>Fila de encabezados<input type="number" min="1" max="100" value={headerRow} onChange={(event) => setHeaderRow(Number(event.target.value))} /></label>
              </div>
              <button className="button primary" disabled={busy || !sheetName} onClick={() => void prepare(dataset, { sheet_name: sheetName, header_row: headerRow - 1 })}>Procesar esta hoja</button>
            </div>
          )}
          <div className="exampleChooser">
            <h3>¿Qué quieres probar?</h3>
            <p>Cada opción abre un Excel normal y prepara una configuración recomendada que podrás revisar y modificar antes de ejecutar.</p>
            <div className="exampleGrid">{examples.map((item) => <button className="exampleCard" key={item.id} onClick={() => void loadExample(item.id)} disabled={busy}><strong>{item.name}</strong><span>{item.description}</span><small>{item.what_you_learn}</small></button>)}</div>
          </div>
        </section>
      )}
      {step === 2 && profile && (
        <section>
          {selectedExample && <div className="alert info"><strong>Configuración recomendada aplicada</strong><span>{selectedExample.name}: {selectedExample.what_you_learn} Revisarás cada elección antes de ejecutar.</span></div>}
          <div className="statRow">
            <div>
              <span>FILAS</span>
              <strong>{profile.row_count.toLocaleString("es-PE")}</strong>
            </div>
            <div>
              <span>COLUMNAS</span>
              <strong>{profile.column_count}</strong>
            </div>
            <div>
              <span>DUPLICADOS</span>
              <strong>{profile.duplicate_count}</strong>
            </div>
            <div>
              <span>CON ALERTAS</span>
              <strong>
                {
                  profile.columns.filter((c) => c.quality_issue_codes.length)
                    .length
                }
              </strong>
            </div>
          </div>
          <div className="panel">
            <div className="panelTitle">
              <div>
                <h2>Así entendimos tus columnas</h2>
                <p>
                  Revisa tipos, faltantes y columnas que parecen
                  identificadores.
                </p>
              </div>
              <button className="button primary" onClick={() => setStep(3)}>
                Preparar datos
              </button>
            </div>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Columna</th>
                    <th>Tipo inferido</th>
                    <th>Faltantes</th>
                    <th>Valores distintos</th>
                    <th>Observación</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.columns.map((c) => (
                    <tr key={c.column_id}>
                      <td>
                        <strong>{c.display_name}</strong>
                      </td>
                      <td>
                        <span className="tag">
                          {c.inferred_semantic_type === "numeric" ? "Numérica" : c.inferred_semantic_type === "datetime" ? "Fecha" : "Categoría"}
                        </span>
                      </td>
                      <td>{c.null_count}</td>
                      <td>{c.distinct_count}</td>
                      <td>
                        {c.possible_id ? (
                          <span className="warningText">
                            Parece identificar registros; la excluiremos por
                            defecto.
                          </span>
                        ) : (
                          c.quality_issue_codes.includes("CONSTANT_OR_EMPTY") ? "No cambia o está vacía; normalmente no ayuda a modelar." : c.quality_issue_codes.includes("MISSING_VALUES") ? "Tiene filas sin valor; la imputación se ajustará solo dentro del entrenamiento." : "Sin alertas principales"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
      {step === 3 && profile && (
        <section>
          <div className="panel preparationIntro">
            <h2>Prepara representaciones, no el modelo</h2>
            <p>Confirma qué contiene cada columna, cómo se usará y qué representación aplicar. Preparar no permite saber si un valor es correcto para tu negocio ni elimina valores extremos automáticamente.</p>
            <DataFlow />
            <div className="alert info"><strong>Los faltantes pueden conservarse</strong><span>No necesariamente tienes que rellenarlos ahora. El pipeline del modelo los trata usando solo los datos de entrenamiento.</span></div>
          </div>
          <div className="panel">
            <div className="panelTitle"><div><h2>Revisa tus columnas</h2><p>{reviewedColumns.length} de {suggestions.length} columnas revisadas. Las columnas sin alertas ya cuentan como listas.</p></div><ConceptHelp concept="column_role" /></div>
            <div className="preparationWorkspace">
              <aside className="columnBrowser" aria-label="Columnas del archivo">
                <label className="searchField">Buscar columna<input value={columnSearch} onChange={event => setColumnSearch(event.target.value)} placeholder="Nombre de columna" /></label>
                <div className="columnFilters" aria-label="Filtrar columnas">{([['all','Todas'],['review','Requieren revisión'],['identifier','Identificadores'],['ignore','Ignoradas'],['ready','Listas']] as const).map(([id,label]) => <button type="button" className={columnFilter === id ? 'active' : ''} key={id} onClick={() => setColumnFilter(id)}>{label}</button>)}</div>
                <div className="columnList">{filteredSuggestions.map(column => {
                  const config = recipe.columns[column.column_id];
                  const statusLabel = column.alerts.length && !reviewedColumns.includes(column.column_id) ? 'Revisar' : config?.role === 'ignore' ? 'Ignorada' : config?.role === 'identifier' ? 'Identificador' : 'Lista';
                  const note = column.alerts.includes('AMBIGUOUS_DATE') ? 'Parece fecha escrita como texto.' : column.alerts.includes('NUMBER_STORED_AS_TEXT') ? 'Parece número guardado como texto.' : column.alerts.includes('MIXED_CURRENCIES') ? 'Mezcla monedas y necesita revisión.' : column.possible_id ? 'Parece reconocer cada registro.' : 'No requiere confirmación obligatoria.';
                  return <button type="button" key={column.column_id} className={selectedPreparation?.column_id === column.column_id ? 'selected' : ''} onClick={() => setSelectedColumnId(column.column_id)}><span><strong>{column.display_name}</strong><small>{column.inferred_semantic_type === 'numeric' ? 'Número detectado' : column.inferred_semantic_type === 'datetime' ? 'Fecha detectada' : 'Categoría detectada'}</small></span><span className={`columnStatus ${statusLabel === 'Revisar' ? 'warning' : ''}`}>{statusLabel}</span><small>{note}</small></button>;
                })}{!filteredSuggestions.length && <p className="empty">No hay columnas en este filtro.</p>}</div>
              </aside>
              {selectedPreparation && (() => {
                const column = selectedPreparation;
                const config = recipe.columns[column.column_id] ?? {type:'auto',role:'variable'};
                const typeCopy:Record<string,string> = {auto:'Usaremos el tipo detectado. Si algo parece ambiguo, te pediremos confirmación.',numeric:'Cantidades sobre las que tiene sentido calcular diferencias, como ventas, edad o duración.',categorical:'Grupos o etiquetas, como Norte/Sur o Sí/No.',date:'Días o momentos en el tiempo.',text:'Contenido que conservaremos, pero que los modelos actuales no usan directamente como variable predictiva.'};
                const roleCopy:Record<string,string> = {variable:'Información que podría ayudar al modelo a encontrar patrones.',identifier:'Sirve para reconocer un registro, como un código de cliente. Normalmente no debe usarse para aprender patrones.',ignore:'Conservaremos la columna en el original, pero esta versión no la usará para modelar.'};
                return <article className="columnEditor" aria-label={`Preparar ${column.display_name}`}>
                  <header><span className="eyebrow">COLUMNA SELECCIONADA</span><h3>{column.display_name}</h3></header>
                  <div className="columnStory"><div><span>Así la encontramos</span><strong>{column.inferred_semantic_type === 'numeric' ? 'Parece un número' : column.inferred_semantic_type === 'datetime' ? 'Parece una fecha' : 'Parece texto o etiquetas'}</strong></div><div><span>Ejemplos</span><strong>{column.examples.map(value => String(value)).join(' · ') || 'Sin ejemplos disponibles'}</strong></div><div><span>Resumen</span><strong>{column.null_count} sin valor · {column.distinct_count} valores distintos</strong></div></div>
                  {column.alerts.length > 0 && <div className="recommendation"><strong>Recomendación de Laboratorio ML</strong><span>{column.recommended.type === 'date' ? 'Fecha' : column.recommended.type === 'numeric' ? 'Números' : column.possible_id ? 'Identificador' : 'Revisar representación'}</span><p>{column.alerts.includes('AMBIGUOUS_DATE') ? 'Los ejemplos tienen una forma compatible con fecha, pero pueden significar fechas distintas según el país.' : column.alerts.includes('NUMBER_STORED_AS_TEXT') ? 'Encontramos separadores compatibles con números escritos como texto.' : column.alerts.includes('MIXED_CURRENCIES') ? 'Esta columna mezcla monedas. No conocemos el tipo de cambio correcto ni la fecha de conversión, así que no las uniremos.' : column.possible_id ? 'Esta columna tiene casi un valor distinto por fila y su nombre parece un identificador.' : 'Encontramos una representación que conviene confirmar.'}</p><button type="button" className="button secondary" onClick={() => acceptSuggestion(column)}>Usar esta recomendación</button></div>}
                  <label className="fieldQuestion">¿Qué contiene esta columna?<select aria-label={`Tipo para ${column.display_name}`} value={config.type} onChange={event => updateColumn(column.column_id,{type:event.target.value as ColumnPreparation['type']})}><option value="auto">Dejar que Laboratorio ML la interprete</option><option value="numeric">Números</option><option value="categorical">Categorías o etiquetas</option><option value="date">Fechas</option><option value="text">Texto libre</option></select><small>{typeCopy[config.type]}</small></label>
                  <label className="fieldQuestion">¿Para qué sirve esta columna?<select aria-label={`Uso para ${column.display_name}`} value={config.role} onChange={event => updateColumn(column.column_id,{role:event.target.value as ColumnPreparation['role']})}><option value="variable">Variable</option><option value="identifier">Identificador</option><option value="ignore">Ignorar</option></select><small>{roleCopy[config.role]} Lo que quieres predecir se elegirá en el siguiente paso.</small></label>
                  <fieldset className="columnActions"><legend>¿Qué haremos?</legend><label><input type="checkbox" checked={Boolean(config.trim)} onChange={event => updateColumn(column.column_id,{trim:event.target.checked})}/> Quitar espacios al inicio o final</label><label><input type="checkbox" checked={Boolean(config.empty_to_missing)} onChange={event => updateColumn(column.column_id,{empty_to_missing:event.target.checked})}/> Reconocer textos vacíos como valores sin dato</label></fieldset>
                  {config.type === 'date' && <div className="optionPanel"><h4>¿Cómo están escritas tus fechas?</h4><label><select aria-label={`Formato de fecha para ${column.display_name}`} value={config.date_format ?? 'UNAMBIGUOUS'} onChange={event => updateColumn(column.column_id,{date_format:event.target.value as ColumnPreparation['date_format']})}><option value="DMY">Día / mes / año — 15/03/2026 (DMY)</option><option value="MDY">Mes / día / año — 03/15/2026 (MDY)</option><option value="YMD">Año / mes / día — 2026/03/15 (YMD)</option><option value="UNAMBIGUOUS">Solo formatos inequívocos</option></select></label><p>01/02/2026 puede significar fechas distintas según el país. Preferimos que tú confirmes.</p><label><input type="checkbox" checked={Boolean(config.excel_date_serials)} onChange={event => updateColumn(column.column_id,{excel_date_serials:event.target.checked})}/> Mis números realmente representan fechas internas de Excel</label><small>Actívalo solo si esos números son fechas de Excel.</small></div>}
                  {config.type === 'numeric' && <div className="optionPanel"><h4>¿Cómo están escritos los números?</h4><div className="numberExamples"><button type="button" onClick={() => updateColumn(column.column_id,{decimal_separator:',',thousands_separator:'.'})}><strong>1.234,50</strong><small>coma decimal · punto de miles</small></button><button type="button" onClick={() => updateColumn(column.column_id,{decimal_separator:'.',thousands_separator:','})}><strong>1,234.50</strong><small>punto decimal · coma de miles</small></button><button type="button" onClick={() => updateColumn(column.column_id,{decimal_separator:'.',thousands_separator:undefined})}><strong>1234.50</strong><small>punto decimal · sin miles</small></button></div><div className="inlineFields"><label>Separador decimal<select value={config.decimal_separator ?? ''} onChange={event => updateColumn(column.column_id,{decimal_separator:(event.target.value || undefined) as '.'|','|undefined})}><option value="">Sin confirmar</option><option value=".">Punto</option><option value=",">Coma</option></select></label><label>Separador de miles<select value={config.thousands_separator ?? ''} onChange={event => updateColumn(column.column_id,{thousands_separator:(event.target.value || undefined) as '.'|','|' '|undefined})}><option value="">Ninguno</option><option value=",">Coma</option><option value=".">Punto</option><option value=" ">Espacio</option></select></label></div><label><input type="checkbox" checked={Boolean(config.percent)} onChange={event => updateColumn(column.column_id,{percent:event.target.checked})}/> Es porcentaje: 15 % se convertirá a 0.15</label><small>La representación cambia, no el significado.</small><label>Moneda<select value={config.currency ?? ''} onChange={event => updateColumn(column.column_id,{currency:(event.target.value || undefined) as 'PEN'|'USD'|'EUR'|undefined})}><option value="">Sin moneda confirmada</option><option value="PEN">Soles (PEN)</option><option value="USD">Dólares (USD)</option><option value="EUR">Euros (EUR)</option></select><small>Seleccionar PEN no convierte monedas; confirma que los valores ya representan soles.</small></label></div>}
                  {(config.type === 'date' || config.type === 'numeric') && <label className="fieldQuestion">¿Qué hacemos con los valores que no podamos interpretar?<select value={config.invalid ?? 'block'} onChange={event => updateColumn(column.column_id,{invalid:event.target.value as 'block'|'segregate'})}><option value="block">Detener y revisar</option><option value="segregate">Apartar esas filas</option></select><small>{config.invalid === 'segregate' ? 'Crearemos la versión sin esas filas y guardaremos cuáles quedaron fuera y por qué.' : 'No crearemos la versión preparada hasta que corrijas la configuración.'}</small></label>}
                  <div className="editorNav"><button type="button" className="button secondary" disabled={suggestions.indexOf(column) === 0} onClick={() => setSelectedColumnId(suggestions[suggestions.indexOf(column)-1].column_id)}>Anterior</button><button type="button" className="button secondary" disabled={suggestions.indexOf(column) === suggestions.length-1} onClick={() => setSelectedColumnId(suggestions[suggestions.indexOf(column)+1].column_id)}>Siguiente</button></div>
                </article>;
              })()}
            </div>
            <fieldset className="duplicateChoice"><legend>Filas idénticas</legend><p>Encontramos {profile.duplicate_count} filas idénticas. Dos filas iguales no siempre son un error: pueden representar dos eventos reales iguales.</p><label><input type="radio" name="duplicates" checked={recipe.exact_duplicates === 'keep'} onChange={() => {setRecipe(current => ({...current,exact_duplicates:'keep'}));setPreparationPreview(null)}}/> <strong>Conservar</strong> — cada fila seguirá contando como una observación.</label><label><input type="radio" name="duplicates" checked={recipe.exact_duplicates === 'exclude'} onChange={() => {setRecipe(current => ({...current,exact_duplicates:'exclude'}));setPreparationPreview(null)}}/> <strong>Apartar copias exactas</strong> — conservaremos la primera aparición y registraremos las demás.</label><small>El archivo original nunca cambia.</small></fieldset>
            <details className="advancedPreparation"><summary>Opciones avanzadas</summary><p>Estas reglas apartan filas o unifican etiquetas de forma explícita. No combinan tablas, no usan coincidencias aproximadas y no ejecutan código.</p><div className="advancedGrid"><section><h3>Filtrar filas</h3><label>Regla<select value={filterDraft.kind} onChange={event => setFilterDraft(current => ({...current,kind:event.target.value}))}><option value="date_range">Filtrar periodo</option><option value="category">Filtrar categorías</option><option value="numeric_not_null">Exigir valor numérico</option></select></label><label>Columna<select value={filterDraft.column_id} onChange={event => setFilterDraft(current => ({...current,column_id:event.target.value}))}><option value="">Selecciona</option>{suggestions.map(column => <option key={column.column_id} value={column.column_id}>{column.display_name}</option>)}</select></label>{filterDraft.kind === 'date_range' && <div className="inlineFields"><label>Desde<input type="date" value={filterDraft.start} onChange={event => setFilterDraft(current => ({...current,start:event.target.value}))}/></label><label>Hasta<input type="date" value={filterDraft.end} onChange={event => setFilterDraft(current => ({...current,end:event.target.value}))}/></label></div>}{filterDraft.kind === 'category' && <><label>Acción<select value={filterDraft.mode} onChange={event => setFilterDraft(current => ({...current,mode:event.target.value}))}><option value="include">Incluir solo</option><option value="exclude">Apartar</option></select></label><label>Valores separados por coma<input value={filterDraft.values} onChange={event => setFilterDraft(current => ({...current,values:event.target.value}))}/></label></>}<button type="button" className="button secondary" onClick={addFilter}>Añadir filtro</button>{recipe.filters.map((filter,index) => <div className="ruleChip" key={`${filter.kind}-${index}`}>{filter.kind === 'date_range' ? 'Periodo confirmado' : filter.kind === 'category' ? `${filter.mode === 'include' ? 'Incluir' : 'Apartar'} categorías` : 'Exigir número'} · {profile.columns.find(column => column.column_id === filter.column_id)?.display_name}<button type="button" aria-label="Quitar filtro" onClick={() => setRecipe(current => ({...current,filters:current.filters.filter((_,itemIndex) => itemIndex !== index)}))}>×</button></div>)}</section><section><h3>Unificar categorías explícitamente</h3><label>Columna<select value={mappingDraft.column_id} onChange={event => setMappingDraft(current => ({...current,column_id:event.target.value}))}><option value="">Selecciona</option>{suggestions.filter(column => ['auto','categorical','text'].includes(recipe.columns[column.column_id]?.type ?? 'auto')).map(column => <option key={column.column_id} value={column.column_id}>{column.display_name}</option>)}</select></label><label>Valor actual<input value={mappingDraft.from} onChange={event => setMappingDraft(current => ({...current,from:event.target.value}))} placeholder="NORTE" /></label><label>Convertir a<input value={mappingDraft.to} onChange={event => setMappingDraft(current => ({...current,to:event.target.value}))} placeholder="Norte" /></label><p className="mappingPreview">Vista previa: {mappingDraft.from || 'valor actual'} → {mappingDraft.to || 'valor unificado'}</p><button type="button" className="button secondary" onClick={addCategoryMapping}>Confirmar unificación</button></section></div><div className="recipeBox"><h3>Reutilizar preparación</h3><p>Una receta guarda tus decisiones de preparación, no tus datos. No contiene modelos ni ejecuta código. Si las columnas no coinciden, te avisaremos antes de aplicarla.</p><div className="miniActions"><button type="button" className="button secondary" onClick={downloadRecipe}>Descargar receta</button><label className="button secondary importRecipe">Importar receta<input type="file" accept="application/json,.json" onChange={event => void importRecipe(event)} /></label></div></div></details>
            <div className="footerActions"><button className="button secondary" onClick={() => setStep(2)}>Atrás</button><button className="button primary" disabled={busy} onClick={() => void previewPreparation()}>Vista previa antes/después</button></div>
          </div>
          {preparationPreview && <div className="panel preparationPreview"><div className="panelTitle"><div><h2>Esto es lo que cambiará</h2><p>Confirma el efecto antes de crear una nueva versión. Tu archivo original no se modifica.</p></div></div><div className="statRow"><div><span>COLUMNAS REINTERPRETADAS</span><strong>{preparationPreview.transformations.length}</strong></div><div><span>FILAS PREPARADAS</span><strong>{preparationPreview.rows_output}</strong></div><div><span>FILAS APARTADAS</span><strong>{preparationPreview.rows_quarantined}</strong></div><div><span>COPIAS EXACTAS APARTADAS</span><strong>{recipe.exact_duplicates === 'exclude' ? profile.duplicate_count : 0}</strong></div></div><h3>Ejemplos: antes → después</h3><div className="tableWrap"><table><thead><tr><th>Columna</th><th>Original</th><th>Se interpretará como</th></tr></thead><tbody>{preparationPreview.preview.map((item,index) => <tr key={`${item.row_id}-${item.column_id}-${index}`}><td>{profile.columns.find(column => column.column_id === item.column_id)?.display_name}</td><td>{String(item.before ?? 'Sin valor')}</td><td>{String(item.after ?? 'Sin valor')}</td></tr>)}</tbody></table></div>{preparationPreview.quarantined.length > 0 && <details><summary>Filas que quedarán fuera de esta versión</summary>{preparationPreview.quarantined.map((item,index) => <p key={`${item.row_id}-${index}`}><strong>{item.row_id}</strong> · {item.reason}</p>)}</details>}<h3>Calidad original y preparada</h3><div className="qualityCompare">{Object.keys(preparationPreview.quality.original).map(key => <div key={key}><span>{qualityLabel(key)}</span><strong>{preparationPreview.quality.original[key]} → {preparationPreview.quality.prepared[key]}</strong><small>{qualityExplanation(key)}</small></div>)}</div><div className="whatDoesNotChange"><h3>Qué NO cambia todavía</h3><ul><li>Tu archivo original.</li><li>El resultado que quieres predecir: todavía no está elegido.</li><li>Los faltantes que el modelo pueda manejar.</li><li>La imputación, el escalado y la codificación que se aprenderán durante el entrenamiento.</li></ul></div><button className="button primary" disabled={busy} onClick={() => void createPreparedVersion()}>Crear versión preparada</button></div>}
        </section>
      )}
      {step === 4 && profile && (
        <section className="panel">
          {prepared && <div className="preparedConfirmation"><span className="successMark">✓</span><div><h2>Tu versión preparada está lista.</h2><p>{preparationPreview?.rows_input.toLocaleString('es-PE')} filas en el original · {profile.row_count.toLocaleString('es-PE')} preparadas · {preparationPreview?.rows_quarantined ?? 0} apartadas · {available.length} variables activas.</p><strong>Todavía no hemos entrenado ningún modelo.</strong><div className="miniActions"><a className="button secondary" href={`/api/v1/dataset-versions/${version}/prepared-excel/download`}>Descargar Excel preparado</a><a className="button secondary" href={`/api/v1/dataset-versions/${version}/recipe/download`}>Descargar receta</a><button type="button" className="button secondary" onClick={() => setStep(3)}>Revisar preparación</button></div></div></div>}
          <DataFlow compact />
          <h2>¿Qué quieres analizar?</h2>
          <div className="goalGrid">
            {goals.map((g) => (
              <button
                key={g.id}
                className={`goalCard ${goal === g.id ? "selected" : ""}`}
                onClick={() => { setGoal(g.id); setTarget(""); setDateCol(""); setPrimaryMetric(""); setPreflight(null) }}
              >
                <span>
                  {g.id === "forecast" ? "◷" : g.id === "explore" ? "⌁" : "◇"}
                </span>
                <strong>{g.title}</strong>
                <small>{g.desc}</small>
              </button>
            ))}
          </div>
          {goal !== "explore" && (
            <div className="formGrid">
              <label>
                Resultado que quieres predecir
                <select
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                >
                  <option value="">Selecciona una columna</option>
                  {targetOptions.map((c) => (
                    <option key={c.column_id} value={c.column_id}>
                      {c.display_name}
                    </option>
                  ))}
                </select>
              </label>
              {goal === "forecast" && (
                <label>
                  Columna de fecha
                  <select
                    value={dateCol}
                    onChange={(e) => setDateCol(e.target.value)}
                  >
                    <option value="">Selecciona una columna</option>
                    {profile.columns.filter((c) => c.inferred_semantic_type === "datetime").map((c) => (
                      <option key={c.column_id} value={c.column_id}>
                        {c.display_name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}
          {goal !== 'explore' && <ConceptHelp concept="target" />}
          {goal !== 'explore' && selected && <div className="targetAvailability"><h3>Disponibilidad para este objetivo</h3><p><strong>{profile.row_count.toLocaleString('es-PE')}</strong> filas en la versión preparada</p><p><strong>{(profile.row_count-selected.null_count).toLocaleString('es-PE')}</strong> tienen valor en <strong>{selected.display_name}</strong></p><p><strong>{selected.null_count.toLocaleString('es-PE')}</strong> no podrán participar porque no tienen un resultado conocido.</p><small>Estas filas siguen en tu versión preparada. Solo quedan fuera de este análisis porque no podemos entrenar o evaluar sin conocer el valor real del resultado.</small></div>}
          {goal !== 'explore' && selected && <div className="alert info"><strong>Para este análisis</strong><span><strong>{selected.display_name}</strong> será el resultado que intentaremos estimar. Las demás variables seleccionadas serán la información que el modelo podrá utilizar.</span></div>}
          {goal === 'forecast' && temporalCheck && <div className="panel temporalCheck"><h3>Chequeo temporal</h3><dl className="reviewList"><div><dt>Primera fecha</dt><dd>{temporalCheck.first_date?.slice(0,10) ?? 'No disponible'}</dd></div><div><dt>Última fecha</dt><dd>{temporalCheck.last_date?.slice(0,10) ?? 'No disponible'}</dd></div><div><dt>Frecuencia detectada</dt><dd>{temporalCheck.frequency}</dd></div><div><dt>Meses observados</dt><dd>{temporalCheck.observed_months}</dd></div><div><dt>Meses faltantes</dt><dd>{temporalCheck.missing_months.length ? temporalCheck.missing_months.join(', ') : '0'}</dd></div><div><dt>Filas en meses duplicados</dt><dd>{temporalCheck.duplicate_month_rows}</dd></div></dl>{temporalCheck.monthly_aggregation_required && <div className="alert warning"><strong>Estos datos aún no son una serie mensual única</strong><span>Elige explícitamente suma o promedio en Revisar. Laboratorio ML no inventará qué agregación corresponde.</span></div>}</div>}
          {goal !== "explore" && goal !== "forecast" && (
            <fieldset className="featurePicker">
              <legend>¿Qué información podrá usar el modelo?</legend>
              <p>Marca solo columnas que existirían al momento de hacer una predicción real. Por ejemplo, para predecir retrasos antes de que ocurran puedes usar la fecha programada, pero no la fecha real de llegada porque aún no la conocerías.</p>
              {available.filter((column) => column.column_id !== target).map((column) => (
                <label key={column.column_id}><input type="checkbox" checked={included.includes(column.column_id)} onChange={(event) => setIncluded((current) => event.target.checked ? [...new Set([...current, column.column_id])] : current.filter((id) => id !== column.column_id))} /> {column.display_name}</label>
              ))}
            </fieldset>
          )}
          <div className="alert info"><strong>Cómo preparar mi data</strong><span>Usa variables disponibles antes del resultado. Laboratorio ML detecta algunos problemas, imputa y transforma dentro del entrenamiento, pero no entiende tu negocio, no corrige todas las categorías ni evita todo leakage. <Link to="/guide#preparar">Leer la guía</Link>.</span></div>
          <div className="footerActions">
            <button className="button secondary" onClick={() => setStep(3)}>
              Atrás
            </button>
            <button className="button primary" onClick={continueGoal}>
              Continuar
            </button>
          </div>
        </section>
      )}
      {step === 5 && (
        <section className="reviewGrid">
          <div className="panel">
            <h2>Revisa antes de ejecutar</h2>
            <DataFlow compact />
            <dl className="reviewList">
              <div>
                <dt>Objetivo</dt>
                <dd>{goals.find((g) => g.id === goal)?.title}</dd>
              </div>
              <div>
                <dt>Resultado que quieres predecir</dt>
                <dd>{selected?.display_name ?? "Exploración general"}</dd>
              </div>
              <div>
                <dt>Datos</dt>
                <dd>
                  {profile?.row_count} filas · {available.length} variables
                  candidatas
                </dd>
              </div>
              <div>
                <dt>Evaluación</dt>
                <dd>
                  La aplicación elegirá splits según el tamaño y soporte, sin
                  usar datos de evaluación para aprender transformaciones. Esto
                  supone registros independientes; grupos y usos temporales
                  tabulares no están soportados.
                </dd>
              </div>
            </dl>
            <label>
              Profundidad
              <select value={depth} onChange={(e) => { setDepth(e.target.value); setPreflight(null) }}>
                <option value="quick">Rápido</option>
                <option value="recommended">Recomendado</option>
              </select>
              <small>{depth === "quick" ? "Referencia y modelo lineal correspondiente. Primera revisión y menos tiempo." : "Añade Extra Trees y Random Forest. Prueba más familias y toma más tiempo; no garantiza un resultado mejor."}</small>
            </label>
            {goal !== "explore" && (
              <label>
                Métrica principal
                <select value={primaryMetric || defaultMetric} onChange={(event) => { setPrimaryMetric(event.target.value); setPreflight(null) }}>
                  {resolvedProblem === "classification" ? <><option value="balanced_accuracy">Exactitud balanceada</option><option value="macro_f1">F1 macro</option><option value="accuracy">Exactitud</option></> : <><option value="mae">MAE</option><option value="rmse">RMSE</option></>}
                </select>
                <small>{explain(primaryMetric || defaultMetric)}</small>
                <ConceptHelp concept={primaryMetric || defaultMetric} label={`Entender ${(primaryMetric || defaultMetric) === 'macro_f1' ? 'F1 macro' : 'esta métrica'}`} />
              </label>
            )}
            {goal === "forecast" && (
              <div className="forecastAggregation">
                <h3>¿Cómo debería resumirse cada mes?</h3><p>Un pronóstico mensual necesita un único valor por mes. Laboratorio ML no puede saber qué resumen representa correctamente tu negocio.</p>
                <div className="formGrid">
                <label>Horizonte mensual<input type="number" min="1" max="24" value={horizon} onChange={(event) => { setHorizon(Number(event.target.value)); setPreflight(null) }} /><small>Meses futuros que se estimarán, entre 1 y 24.</small></label>
                <label>Resumen mensual<select value={aggregation} onChange={(event) => { setAggregation(event.target.value); setPreflight(null) }}><option value="">Elegir solo si corresponde</option><option value="sum">Suma</option><option value="mean">Promedio</option></select><small>{aggregation === 'sum' ? 'Útil para cantidades acumulables, como ventas totales.' : aggregation === 'mean' ? 'Útil cuando interesa el nivel medio, como temperatura promedio.' : 'Elige según el significado de tus datos.'}</small></label>
                </div><p><strong>Esta agrupación pertenece solo a este análisis de pronóstico.</strong> No modifica el Excel preparado anterior.</p>
              </div>
            )}
            {goal === 'forecast' && aggregation && <div className="alert info"><strong>Agrupación de este análisis</strong><span>Usaremos {aggregation === 'sum' ? 'la suma' : 'el promedio'} para obtener un valor por mes. Esta decisión no modifica el Excel preparado.</span></div>}
            {preflight && <div className={`preflightBox ${preflight.can_run ? "ready" : "blocked"}`} role="status"><h3>{preflight.can_run ? "Listo para analizar" : "No conviene ejecutar todavía"}</h3><p>{preflight.can_run ? 'Revisamos que el resultado, las variables y la estrategia de evaluación sean compatibles.' : preflight.explanation}</p>{preflight.blockers.map((item) => <div key={item.code}><strong>Qué encontramos: {item.explanation}</strong><span>Qué hacer: {item.suggestion}</span></div>)}{preflight.warnings.map((item) => <div key={item.code}><strong>Conviene revisar: {item.explanation}</strong><span>{item.suggestion}</span></div>)}</div>}
            <div className="alert warning">
              <strong>Importante</strong>
              <span>
                La importancia predictiva no demuestra necesariamente
                causalidad. Si hay poca data, el resultado se marcará como
                exploratorio.
              </span>
            </div>
            <div className="footerActions">
              <button className="button secondary" onClick={() => setStep(4)}>
                Atrás
              </button>
              {!preflight?.can_run ? <button className="button primary" onClick={checkConfiguration} disabled={busy}>Revisar configuración</button> : <button className="button primary" onClick={run} disabled={busy}>Ejecutar análisis</button>}
            </div>
          </div>
          <aside className="privacyBox">
            <span className="shield">✓</span>
            <h3>Procesamiento local</h3>
            <p>
              El archivo permanece en el volumen local de esta instalación. No
              se enviará a OpenAI.
            </p>
            <small>
              La integración directa con OpenAI no está habilitada en esta versión; puedes
              revisar y copiar un contexto seguro.
            </small>
          </aside>
        </section>
      )}
    </main>
  );
}

function qualityLabel(key:string) {
  const labels:Record<string,string> = {rows:'Filas disponibles',row_count:'Filas disponibles',filas:'Filas disponibles',numeric_columns:'Columnas numéricas',columnas_numericas:'Columnas numéricas',datetime_columns:'Columnas de fecha',columnas_fecha:'Columnas de fecha',missing_count:'Valores sin dato',duplicate_count:'Filas idénticas'};
  return labels[key] ?? 'Indicador de estructura';
}

function qualityExplanation(key:string) {
  if (['rows','row_count','filas'].includes(key)) return 'Menos filas no significa automáticamente mejor calidad: refleja decisiones que confirmaste.';
  if (['numeric_columns','columnas_numericas'].includes(key)) return 'Una columna que estaba como texto ahora puede utilizarse como cantidad.';
  if (['datetime_columns','columnas_fecha'].includes(key)) return 'Una columna ahora tiene una interpretación de fecha confirmada.';
  if (key.includes('missing')) return 'Cambió al reconocer vacíos explícitos; no implica que se hayan inventado valores.';
  if (key.includes('duplicate')) return 'Cuenta filas idénticas; pueden ser eventos reales repetidos.';
  return 'Describe una diferencia de estructura, no una puntuación global de calidad.';
}
