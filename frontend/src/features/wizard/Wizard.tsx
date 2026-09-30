import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, Profile, waitJob } from "../../api/client";
import { excelChecklist, explain } from "../../education/concepts";

type Goal = "estimate_value" | "classify" | "forecast" | "drivers" | "explore";
type DatasetInfo = { safe_extension: string; metadata_json: { sheet_names?: string[] } };
type ExamplePreset = { id:string; name:string; description:string; filename:string; format:string; goal:Goal; problem_type:string; target:{name:string}|null; date_column:{name:string}|null; included_columns:string[]; primary_metric:string|null; depth:string; forecast_horizon:number|null; aggregation:string|null; parser_options:Record<string,unknown>; what_you_learn:string };
type Preflight = { id:string; config_sha256:string; can_run:boolean; blockers:Array<{code:string;explanation:string;suggestion:string}>; warnings:Array<{code:string;explanation:string;suggestion:string}>; explanation:string; suggestions:string[] };
type ColumnPreparation = {type:'auto'|'numeric'|'date'|'categorical'|'text';role:'variable'|'identifier'|'ignore';trim?:boolean;empty_to_missing?:boolean;date_format?:'DMY'|'MDY'|'YMD'|'UNAMBIGUOUS';excel_date_serials?:boolean;decimal_separator?:'.'|',';thousands_separator?:'.'|','|' ';percent?:boolean;currency?:'PEN'|'USD'|'EUR';invalid?:'block'|'segregate'};
type PreparationRecipe = {schema_version:'1.0';columns:Record<string,ColumnPreparation>;expected_columns:Record<string,string>;exact_duplicates:'keep'|'exclude';filters:unknown[]};
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
  const targetOptions = available.filter((column) => goal === "classify" ? column.inferred_semantic_type === "categorical" : goal === "estimate_value" || goal === "forecast" ? column.inferred_semantic_type === "numeric" : true);
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
            <p>Confirma qué contiene cada columna, cómo se usará y qué transformación aplicar. El original permanece intacto. La imputación, el escalado y la codificación aprendida siguen ocurriendo únicamente dentro de cada entrenamiento para evitar fugas.</p>
            <div className="alert info"><strong>Los faltantes pueden conservarse</strong><span>No necesariamente tienes que rellenarlos ahora. El pipeline del modelo los trata usando solo los datos de entrenamiento.</span></div>
          </div>
          <div className="panel">
            <div className="panelTitle"><div><h2>Configuración por columna</h2><p>Tipo, uso y transformación son decisiones distintas.</p></div><label className="button secondary importRecipe">Usar la misma preparación en otro archivo<input type="file" accept="application/json,.json" onChange={(event) => void importRecipe(event)} /></label></div>
            <div className="tableWrap preparationTable"><table><thead><tr><th>Columna y ejemplos</th><th>Detectado</th><th>Tipo que se usará</th><th>Uso</th><th>Acción de preparación</th></tr></thead><tbody>{suggestions.map((column) => {
              const config = recipe.columns[column.column_id] ?? {type:'auto',role:'variable'};
              return <tr key={column.column_id}><td><strong>{column.display_name}</strong><small>{column.examples.map((value) => String(value)).join(' · ') || 'Sin ejemplos'}</small><small>{column.null_count} faltantes · {column.distinct_count} distintos</small></td><td><span className="tag">{column.inferred_semantic_type === 'numeric' ? 'Número' : column.inferred_semantic_type === 'datetime' ? 'Fecha' : 'Categoría'}</span>{column.alerts.includes('NUMBER_STORED_AS_TEXT') && <span className="warningText">Parece número, pero Excel lo guardó como texto.</span>}{column.alerts.includes('AMBIGUOUS_DATE') && <span className="warningText">La fecha es ambigua; confirma día/mes/año.</span>}{column.alerts.includes('MIXED_CURRENCIES') && <span className="warningText">Hay monedas distintas. No se convertirán como una sola unidad.</span>}{column.possible_id && <span className="warningText">Parece identificar cada fila.</span>}</td><td><select aria-label={`Tipo para ${column.display_name}`} value={config.type} onChange={(event) => updateColumn(column.column_id,{type:event.target.value as ColumnPreparation['type']})}><option value="auto">Automático</option><option value="numeric">Número</option><option value="categorical">Categoría</option><option value="date">Fecha</option><option value="text">Texto</option></select></td><td><select aria-label={`Uso para ${column.display_name}`} value={config.role} onChange={(event) => updateColumn(column.column_id,{role:event.target.value as ColumnPreparation['role']})}><option value="variable">Variable</option><option value="identifier">Identificador</option><option value="ignore">Ignorar</option></select></td><td><label><input type="checkbox" checked={Boolean(config.trim)} onChange={(event) => updateColumn(column.column_id,{trim:event.target.checked})}/> Quitar espacios exteriores</label><label><input type="checkbox" checked={Boolean(config.empty_to_missing)} onChange={(event) => updateColumn(column.column_id,{empty_to_missing:event.target.checked})}/> Vacío como faltante</label>{config.type === 'date' && <><label>Cómo están escritas<select value={config.date_format ?? 'UNAMBIGUOUS'} onChange={(event) => updateColumn(column.column_id,{date_format:event.target.value as ColumnPreparation['date_format']})}><option value="DMY">Día / mes / año</option><option value="MDY">Mes / día / año</option><option value="YMD">Año / mes / día</option><option value="UNAMBIGUOUS">Solo formatos inequívocos</option></select></label><label>Si falla<select value={config.invalid ?? 'block'} onChange={(event) => updateColumn(column.column_id,{invalid:event.target.value as 'block'|'segregate'})}><option value="block">Detener y revisar</option><option value="segregate">Segregar la fila</option></select></label></>}{config.type === 'numeric' && <><div className="inlineFields"><label>Decimal<select value={config.decimal_separator ?? ''} onChange={(event) => updateColumn(column.column_id,{decimal_separator:(event.target.value || undefined) as '.'|','|undefined})}><option value="">Sin confirmar</option><option value=".">Punto</option><option value=",">Coma</option></select></label><label>Miles<select value={config.thousands_separator ?? ''} onChange={(event) => updateColumn(column.column_id,{thousands_separator:(event.target.value || undefined) as '.'|','|' '|undefined})}><option value="">Ninguno</option><option value=",">Coma</option><option value=".">Punto</option><option value=" ">Espacio</option></select></label></div><label><input type="checkbox" checked={Boolean(config.percent)} onChange={(event) => updateColumn(column.column_id,{percent:event.target.checked})}/> Convertir porcentaje explícitamente</label><label>Moneda<select value={config.currency ?? ''} onChange={(event) => updateColumn(column.column_id,{currency:(event.target.value || undefined) as 'PEN'|'USD'|'EUR'|undefined})}><option value="">Sin moneda</option><option value="PEN">Soles (PEN)</option><option value="USD">Dólares (USD)</option><option value="EUR">Euros (EUR)</option></select></label><label>Si falla<select value={config.invalid ?? 'block'} onChange={(event) => updateColumn(column.column_id,{invalid:event.target.value as 'block'|'segregate'})}><option value="block">Detener y revisar</option><option value="segregate">Segregar la fila</option></select></label></>}<div className="miniActions"><button className="textButton" onClick={() => acceptSuggestion(column)}>Aceptar sugerencia</button><button className="textButton" onClick={() => updateColumn(column.column_id,{type:'auto',role:column.possible_id?'identifier':'variable',trim:false,empty_to_missing:false,date_format:undefined,decimal_separator:undefined,thousands_separator:undefined,percent:false,currency:undefined,invalid:'block'})}>Conservar</button></div></td></tr>;
            })}</tbody></table></div>
            <fieldset className="duplicateChoice"><legend>Duplicados exactos</legend><p>Encontramos {profile.duplicate_count} filas idénticas. Observaciones iguales pueden ser legítimas.</p><label><input type="radio" name="duplicates" checked={recipe.exact_duplicates === 'keep'} onChange={() => {setRecipe((current) => ({...current,exact_duplicates:'keep'}));setPreparationPreview(null)}}/> Conservarlas</label><label><input type="radio" name="duplicates" checked={recipe.exact_duplicates === 'exclude'} onChange={() => {setRecipe((current) => ({...current,exact_duplicates:'exclude'}));setPreparationPreview(null)}}/> Excluir duplicados exactos dejando la primera aparición</label></fieldset>
            <div className="footerActions"><button className="button secondary" onClick={() => setStep(2)}>Atrás</button><button className="button primary" disabled={busy} onClick={() => void previewPreparation()}>Vista previa antes/después</button></div>
          </div>
          {preparationPreview && <div className="panel preparationPreview"><div className="panelTitle"><div><h2>Revisa antes de crear</h2><p>{preparationPreview.rows_quarantined} de {preparationPreview.rows_input.toLocaleString('es-PE')} filas no se utilizarán en esta versión.</p></div></div><div className="statRow"><div><span>TRANSFORMACIONES</span><strong>{preparationPreview.transformations.length}</strong></div><div><span>FILAS PREPARADAS</span><strong>{preparationPreview.rows_output}</strong></div><div><span>SEGREGADAS</span><strong>{preparationPreview.rows_quarantined}</strong></div><div><span>DUPLICADOS EXCLUIDOS</span><strong>{recipe.exact_duplicates === 'exclude' ? profile.duplicate_count : 0}</strong></div></div><h3>Antes / después</h3><div className="tableWrap"><table><thead><tr><th>Columna</th><th>Antes</th><th>Después</th></tr></thead><tbody>{preparationPreview.preview.map((item,index) => <tr key={`${item.row_id}-${item.column_id}-${index}`}><td>{profile.columns.find((column) => column.column_id === item.column_id)?.display_name}</td><td>{String(item.before ?? 'Faltante')}</td><td>{String(item.after ?? 'Faltante')}</td></tr>)}</tbody></table></div>{preparationPreview.quarantined.length > 0 && <details><summary>Revisar filas segregadas</summary>{preparationPreview.quarantined.map((item,index) => <p key={`${item.row_id}-${index}`}><strong>{item.row_id}</strong> · {item.reason}</p>)}</details>}<h3>Calidad original vs preparada</h3><div className="qualityCompare">{Object.keys(preparationPreview.quality.original).map((key) => <div key={key}><span>{key.replaceAll('_',' ')}</span><strong>{preparationPreview.quality.original[key]} → {preparationPreview.quality.prepared[key]}</strong></div>)}</div><button className="button primary" disabled={busy} onClick={() => void createPreparedVersion()}>Crear versión preparada</button></div>}
        </section>
      )}
      {step === 4 && profile && (
        <section className="panel">
          {prepared && <div className="alert success"><strong>Versión preparada creada</strong><span>El análisis usará esta versión; el archivo original permanece intacto. <a href={`/api/v1/dataset-versions/${version}/prepared-excel/download`}>Descargar Excel preparado</a> · <a href={`/api/v1/dataset-versions/${version}/recipe/download`}>Descargar receta JSON</a></span></div>}
          <h2>¿Qué quieres entender?</h2>
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
                Resultado que quieres analizar
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
          {goal !== 'explore' && selected && selected.null_count > 0 && <div className="alert warning"><strong>Filas que no entrarán al análisis</strong><span>{selected.null_count} filas no tienen resultado. Se apartarán explícitamente para este objetivo; no se borrarán del original.</span></div>}
          {goal === 'forecast' && temporalCheck && <div className="panel temporalCheck"><h3>Chequeo temporal</h3><dl className="reviewList"><div><dt>Primera fecha</dt><dd>{temporalCheck.first_date?.slice(0,10) ?? 'No disponible'}</dd></div><div><dt>Última fecha</dt><dd>{temporalCheck.last_date?.slice(0,10) ?? 'No disponible'}</dd></div><div><dt>Frecuencia detectada</dt><dd>{temporalCheck.frequency}</dd></div><div><dt>Meses observados</dt><dd>{temporalCheck.observed_months}</dd></div><div><dt>Meses faltantes</dt><dd>{temporalCheck.missing_months.length ? temporalCheck.missing_months.join(', ') : '0'}</dd></div><div><dt>Filas en meses duplicados</dt><dd>{temporalCheck.duplicate_month_rows}</dd></div></dl>{temporalCheck.monthly_aggregation_required && <div className="alert warning"><strong>Estos datos aún no son una serie mensual única</strong><span>Elige explícitamente suma o promedio en Revisar. Laboratorio ML no inventará qué agregación corresponde.</span></div>}</div>}
          {goal !== "explore" && goal !== "forecast" && (
            <fieldset className="featurePicker">
              <legend>Variables disponibles para el modelo</legend>
              <p>Desmarca cualquier columna que no existiría al momento de predecir.</p>
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
            <dl className="reviewList">
              <div>
                <dt>Objetivo</dt>
                <dd>{goals.find((g) => g.id === goal)?.title}</dd>
              </div>
              <div>
                <dt>Resultado</dt>
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
              </label>
            )}
            {goal === "forecast" && (
              <div className="formGrid">
                <label>Horizonte mensual<input type="number" min="1" max="24" value={horizon} onChange={(event) => { setHorizon(Number(event.target.value)); setPreflight(null) }} /><small>Meses futuros que se estimarán, entre 1 y 24.</small></label>
                <label>Varias filas en un mes<select value={aggregation} onChange={(event) => { setAggregation(event.target.value); setPreflight(null) }}><option value="">Elegir solo si corresponde</option><option value="mean">Promedio</option><option value="sum">Suma</option></select><small>Solo se aplica cuando el archivo contiene más de una fila por mes. No elegimos por ti.</small></label>
              </div>
            )}
            {preflight && <div className={`preflightBox ${preflight.can_run ? "ready" : "blocked"}`} role="status"><h3>{preflight.can_run ? "Configuración lista" : "Ajusta la configuración"}</h3><p>{preflight.explanation}</p>{preflight.blockers.map((item) => <div key={item.code}><strong>{item.explanation}</strong><span>{item.suggestion}</span></div>)}{preflight.warnings.map((item) => <div key={item.code}><strong>{item.explanation}</strong><span>{item.suggestion}</span></div>)}</div>}
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
