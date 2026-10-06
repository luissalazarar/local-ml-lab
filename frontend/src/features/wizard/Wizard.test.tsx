import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Wizard } from './Wizard'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

const originalProfile = {
  row_count: 3, column_count: 3, duplicate_count: 1, sampled: false,
  columns: [
    { column_id: 'c0001', display_name: 'Fecha', inferred_semantic_type: 'categorical', null_count: 0, distinct_count: 3, possible_id: false, quality_issue_codes: [] },
    { column_id: 'c0002', display_name: 'Monto', inferred_semantic_type: 'categorical', null_count: 0, distinct_count: 3, possible_id: false, quality_issue_codes: [] },
    { column_id: 'c0003', display_name: 'Cliente ID', inferred_semantic_type: 'categorical', null_count: 0, distinct_count: 3, possible_id: true, quality_issue_codes: ['POSSIBLE_IDENTIFIER'] },
  ],
}

describe('preparación guiada', () => {
  it('confirma tipos, muestra preview, segrega y continúa con la versión preparada', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input)
      let body: unknown = {}
      if (url.endsWith('/examples')) body = { items: [{ id:'prep', name:'Excel típico', description:'Fechas y montos', filename:'prep.xlsx', format:'xlsx', goal:'estimate_value', problem_type:'regression', target:{name:'Monto'}, date_column:null, included_columns:['Monto'], primary_metric:'mae', depth:'quick', forecast_horizon:null, aggregation:null, parser_options:{sheet_name:'Datos',header_row:0}, what_you_learn:'Preparar antes de analizar' }] }
      else if (url.includes('/datasets/from-example/')) body = { dataset_id:'d1', job_id:'j1' }
      else if (url.endsWith('/datasets/d1/versions')) body = { dataset_version_id:'v1', job_id:'j2' }
      else if (url.includes('/jobs/')) body = { id:'job', status:'succeeded', progress:{} }
      else if (url.endsWith('/dataset-versions/v1/profile')) body = originalProfile
      else if (url.endsWith('/dataset-versions/v1/preparation-suggestions')) body = { columns: [
        {...originalProfile.columns[0], examples:['01/02/2026'], alerts:['AMBIGUOUS_DATE'], recommended:{type:'date',role:'variable',date_format:'DMY'}},
        {...originalProfile.columns[1], examples:['1.234,50'], alerts:['NUMBER_STORED_AS_TEXT'], recommended:{type:'numeric',role:'variable',decimal_separator:',',thousands_separator:'.'}},
        {...originalProfile.columns[2], examples:['C-1'], alerts:['POSSIBLE_IDENTIFIER'], recommended:{type:'auto',role:'identifier'}},
      ] }
      else if (url.endsWith('/dataset-versions/v1/preparation-preview')) body = { rows_input:3, rows_output:2, rows_quarantined:1, preview:[{row_id:'row-0000001',column_id:'c0001',before:'01/02/2026',after:'2026-02-01'}], quarantined:[{row_id:'row-0000003',reason:'Fecha inválida'}], transformations:[{column_id:'c0001',transformation:'interpretar como fecha DMY',affected_count:2,invalid_count:1}], quality:{original:{filas:3,columnas_fecha:0},prepared:{filas:2,columnas_fecha:1}} }
      else if (url.endsWith('/dataset-versions/v1/preparations')) body = { dataset_version_id:'v2', job_id:'j3' }
      else if (url.endsWith('/dataset-versions/v2/profile')) body = {...originalProfile,row_count:2,duplicate_count:0,columns:[{...originalProfile.columns[0],inferred_semantic_type:'datetime',configured_role:'variable'},{...originalProfile.columns[1],inferred_semantic_type:'numeric',configured_role:'variable'},{...originalProfile.columns[2],configured_role:'identifier'}]}
      else throw new Error(`Unhandled ${options?.method ?? 'GET'} ${url}`)
      return { ok:true, json:async () => body } as Response
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter><Wizard /></MemoryRouter>)
    expect(screen.getByText(/máximo 200 MiB/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: '¿Necesitas datos para empezar?' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Datos Abiertos del Perú/ })).toBeTruthy()
    fireEvent.click(await screen.findByRole('button', { name: /Excel típico/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Preparar datos' }))
    expect(screen.getByText('¿Qué contiene esta columna?')).toBeTruthy()
    expect(screen.getByText('¿Para qué sirve esta columna?')).toBeTruthy()
    expect(screen.getByText(/Dos filas iguales no siempre son un error/)).toBeTruthy()
    expect(screen.getAllByText('ORIGINAL').length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText('Tipo para Fecha'), { target: { value: 'date' } })
    expect(screen.getByText(/Cómo están escritas tus fechas/)).toBeTruthy()
    expect(screen.getByRole('option', {name:/Día \/ mes \/ año/})).toBeTruthy()
    fireEvent.click(screen.getByRole('button', {name:/^Monto/}))
    fireEvent.change(screen.getByLabelText('Tipo para Monto'), {target:{value:'numeric'}})
    expect(screen.getByText(/¿Cómo están escritos los números/)).toBeTruthy()
    expect(screen.getByText(/La representación cambia, no el significado/)).toBeTruthy()
    fireEvent.click(screen.getByText('Opciones avanzadas'))
    expect(screen.getByText(/Una receta guarda tus decisiones/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', {name:/^Fecha/}))
    fireEvent.click(screen.getByRole('button', { name: 'Vista previa antes/después' }))
    expect(await screen.findByText('2026-02-01')).toBeTruthy()
    expect(screen.getByText('FILAS APARTADAS')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Crear versión preparada' }))
    await waitFor(() => expect(screen.getByText('Tu versión preparada está lista.')).toBeTruthy())
    expect(screen.getByRole('link', { name: 'Descargar Excel preparado' }).getAttribute('href')).toContain('/v2/')
    expect(screen.getByRole('option', { name: 'Monto' })).toBeTruthy()
    expect((screen.getByRole('checkbox', { name: 'Fecha' }) as HTMLInputElement).checked).toBe(false)
    expect((screen.getByRole('checkbox', { name: 'Monto' }) as HTMLInputElement).checked).toBe(true)
    fireEvent.change(screen.getByLabelText('Resultado que quieres predecir'), {target:{value:'c0002'}})
    expect(screen.getByText('Disponibilidad para este objetivo')).toBeTruthy()
    expect(screen.getByText(/Todavía no hemos entrenado ningún modelo/)).toBeTruthy()
  })
})
