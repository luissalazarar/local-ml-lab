import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, Profile, waitJob } from "../../api/client";

type Goal = "estimate_value" | "classify" | "forecast" | "drivers" | "explore";
type DatasetInfo = { safe_extension: string; metadata_json: { sheet_names?: string[] } };
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
  const [aggregation, setAggregation] = useState("mean");
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
  const prepare = useCallback(async (id: string, options: Record<string, unknown> = {}) => {
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
    setIncluded(p.columns.filter((column) => !column.possible_id).map((column) => column.column_id));
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
        await prepare(created.dataset_id);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [prepare],
  );
  useEffect(() => {
    const ex = params.get("example");
    if (ex && !dataset) void loadExample(ex);
  }, [dataset, loadExample, params]);
  const available = profile?.columns.filter((c) => !c.possible_id) ?? [];
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
    setError("");
    setStep(4);
  }
  async function run() {
    setBusy(true);
    setError("");
    try {
      const config = {
        schema_version: "1.0",
        dataset_version_id: version,
        goal,
        problem_type: resolvedProblem,
        target_column_id: goal === "explore" ? null : target,
        date_column_id: goal === "forecast" ? dateCol : null,
        included_column_ids: included,
        excluded_column_ids:
          profile?.columns
            .filter((c) => c.possible_id)
            .map((c) => c.column_id) ?? [],
        depth,
        primary_metric: goal === "explore" ? null : primaryMetric || defaultMetric,
        validation_context: "independent_records",
        seed: 42,
        forecast_options: goal === "forecast" ? { horizon, aggregation } : null,
      };
      setStatus("Comprobando que la evaluación sea defendible…");
      const pf = await api<{ preflight_id: string; job_id: string }>(
        "/preflights",
        { method: "POST", body: JSON.stringify({ config }) },
      );
      await waitJob(pf.job_id, (j) =>
        setStatus(j.progress.message ?? "Preparando evaluación…"),
      );
      const ready = await api<{ config_sha256: string }>(
        `/preflights/${pf.preflight_id}`,
      );
      const created = await api<{ run_id: string; job_id: string }>("/runs", {
        method: "POST",
        body: JSON.stringify({
          preflight_id: pf.preflight_id,
          config_sha256: ready.config_sha256,
        }),
      });
      nav(`/runs/${created.run_id}/progress?job=${created.job_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return (
    <main className="wizardPage">
      <div className="wizardHeader">
        <div>
          <span className="eyebrow">NUEVO ANÁLISIS</span>
          <h1>De archivo a evidencia, paso a paso.</h1>
        </div>
        <ol className="stepper" aria-label="Progreso">
          {["Archivo", "Entender", "Objetivo", "Revisar"].map((x, i) => (
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
          <h2>Sube tu archivo</h2>
          <p>
            CSV, XLSX o Parquet · máximo 100 MiB. Conservamos el original y
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
          <div className="examples">
            <span>O prueba con data sintética:</span>
            <button onClick={() => loadExample("regression")} disabled={busy}>
              Regresión
            </button>
            <button
              onClick={() => loadExample("classification")}
              disabled={busy}
            >
              Clasificación
            </button>
            <button
              onClick={() => loadExample("forecast_monthly")}
              disabled={busy}
            >
              Pronóstico
            </button>
          </div>
        </section>
      )}
      {step === 2 && profile && (
        <section>
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
                Elegir objetivo
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
                        <small>{c.column_id}</small>
                      </td>
                      <td>
                        <span className="tag">
                          {c.inferred_semantic_type === "numeric"
                            ? "Numérica"
                            : "Categoría"}
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
                          c.quality_issue_codes.join(", ") ||
                          "Sin alertas principales"
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
        <section className="panel">
          <h2>¿Qué quieres entender?</h2>
          <div className="goalGrid">
            {goals.map((g) => (
              <button
                key={g.id}
                className={`goalCard ${goal === g.id ? "selected" : ""}`}
                onClick={() => setGoal(g.id)}
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
                  {available.map((c) => (
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
                    {profile.columns.map((c) => (
                      <option key={c.column_id} value={c.column_id}>
                        {c.display_name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}
          {goal !== "explore" && goal !== "forecast" && (
            <fieldset className="featurePicker">
              <legend>Variables disponibles para el modelo</legend>
              <p>Desmarca cualquier columna que no existiría al momento de predecir.</p>
              {available.filter((column) => column.column_id !== target).map((column) => (
                <label key={column.column_id}><input type="checkbox" checked={included.includes(column.column_id)} onChange={(event) => setIncluded((current) => event.target.checked ? [...new Set([...current, column.column_id])] : current.filter((id) => id !== column.column_id))} /> {column.display_name}</label>
              ))}
            </fieldset>
          )}
          <div className="footerActions">
            <button className="button secondary" onClick={() => setStep(2)}>
              Atrás
            </button>
            <button className="button primary" onClick={continueGoal}>
              Continuar
            </button>
          </div>
        </section>
      )}
      {step === 4 && (
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
              <select value={depth} onChange={(e) => setDepth(e.target.value)}>
                <option value="quick">Rápido</option>
                <option value="recommended">Recomendado</option>
              </select>
            </label>
            {goal !== "explore" && (
              <label>
                Métrica principal
                <select value={primaryMetric || defaultMetric} onChange={(event) => setPrimaryMetric(event.target.value)}>
                  {resolvedProblem === "classification" ? <><option value="balanced_accuracy">Exactitud balanceada</option><option value="macro_f1">F1 macro</option><option value="accuracy">Exactitud</option></> : <><option value="mae">MAE</option><option value="rmse">RMSE</option></>}
                </select>
              </label>
            )}
            {goal === "forecast" && (
              <div className="formGrid">
                <label>Horizonte mensual<input type="number" min="1" max="24" value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} /></label>
                <label>Varias filas en un mes<select value={aggregation} onChange={(event) => setAggregation(event.target.value)}><option value="mean">Promedio</option><option value="sum">Suma</option></select></label>
              </div>
            )}
            <div className="alert warning">
              <strong>Importante</strong>
              <span>
                La importancia predictiva no demuestra necesariamente
                causalidad. Si hay poca data, el resultado se marcará como
                exploratorio.
              </span>
            </div>
            <div className="footerActions">
              <button className="button secondary" onClick={() => setStep(3)}>
                Atrás
              </button>
              <button className="button primary" onClick={run} disabled={busy}>
                Ejecutar análisis
              </button>
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
