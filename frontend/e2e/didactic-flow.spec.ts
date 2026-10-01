import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { writeFile } from 'node:fs/promises'

async function openPreparation(page: import('@playwright/test').Page) {
  await page.goto('/new?example=preparation')
  await expect(page.getByRole('heading', {name:'Así entendimos tus columnas'})).toBeVisible()
  await page.getByRole('button', {name:'Preparar datos'}).click()
  await expect(page.getByRole('heading', {name:'Revisa tus columnas'})).toBeVisible()
}

test('una persona sin jerga completa el recorrido didáctico', async ({ page }) => {
  await page.setViewportSize({width:1440,height:950})
  await openPreparation(page)
  await expect(page.getByText('¿Qué contiene esta columna?')).toBeVisible()
  await page.getByRole('button', {name:/^Fecha venta/}).click()
  await page.getByRole('button', {name:'Usar esta recomendación'}).click()
  await expect(page.getByText('¿Cómo están escritas tus fechas?')).toBeVisible()
  await page.getByRole('button', {name:/^Monto texto/}).click()
  await page.getByRole('button', {name:'Usar esta recomendación'}).click()
  await expect(page.getByText('¿Cómo están escritos los números?')).toBeVisible()
  await page.getByLabel(/Apartar copias exactas/).check()
  await page.getByRole('button', {name:'Vista previa antes/después'}).click()
  await expect(page.getByRole('heading', {name:'Esto es lo que cambiará'})).toBeVisible()
  await page.getByRole('button', {name:'Crear versión preparada'}).click()
  await expect(page.getByRole('heading', {name:'Tu versión preparada está lista.'})).toBeVisible()
  await expect(page.getByText('Todavía no hemos entrenado ningún modelo.')).toBeVisible()
  await page.getByLabel('Resultado que quieres predecir').selectOption({label:'Ventas'})
  await expect(page.getByRole('heading', {name:'Disponibilidad para este objetivo'})).toBeVisible()
  await page.getByRole('button', {name:'Continuar'}).click()
  await expect(page.getByText(/Error absoluto promedio/)).toBeVisible()
  await page.getByRole('button', {name:'Revisar configuración'}).click()
  await expect(page.getByRole('heading', {name:'Listo para analizar'})).toBeVisible()
  await page.getByRole('button', {name:'Ejecutar análisis'}).click()
  await expect(page).toHaveURL(/\/runs\/[^/]+\/progress/)
  await expect(page.getByText('EVALUACIÓN TERMINADA')).toBeVisible({timeout:120_000})
  await page.getByRole('link', {name:'Ver resultado completo'}).click()
  await expect(page.getByText(/¿APORTÓ FRENTE A UNA REGLA SENCILLA?/)).toBeVisible({timeout:120_000})
  await expect(page.getByText(/Este nivel describe la solidez/)).toBeVisible()
  await expect(page.getByRole('heading', {name:'Qué pasó con tus datos'})).toBeVisible()
})

for (const viewport of [{width:768,height:900},{width:390,height:844}]) {
  test(`Preparar no desborda a ${viewport.width} px`, async ({page}) => {
    await page.setViewportSize(viewport)
    await openPreparation(page)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(1)
    await expect(page.getByText('¿Qué contiene esta columna?')).toBeVisible()
  })
}

test('20+ columnas, nombres largos y 100+ categorías siguen manejables', async ({page}) => {
  const file = '/tmp/local-ml-lab-ui-stress.csv'
  const headers = ['Categoría con un nombre especialmente largo para comprobar el ajuste', ...Array.from({length:24},(_,index) => `Variable operativa con nombre largo ${index+1}`)]
  const rows = Array.from({length:130},(_,row) => [`Categoría extensa número ${row+1}`, ...Array.from({length:24},(_,column) => String(row+column))])
  await writeFile(file,[headers,...rows].map(values => values.join(',')).join('\n'),'utf8')
  await page.setViewportSize({width:390,height:844})
  await page.goto('/new')
  const chooser = page.waitForEvent('filechooser')
  await page.getByText('Arrastra un archivo o selecciónalo').click()
  await (await chooser).setFiles(file)
  await expect(page.getByRole('heading',{name:'Así entendimos tus columnas'})).toBeVisible()
  await page.getByRole('button',{name:'Preparar datos'}).click()
  await expect(page.getByText(/de 25 columnas revisadas/)).toBeVisible()
  await page.getByLabel('Buscar columna').fill('especialmente largo')
  await expect(page.getByRole('button',{name:/^Categoría con un nombre especialmente largo/})).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth-document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})

test('Preparar conserva lectura y foco a zoom 200 %', async ({page}) => {
  await page.setViewportSize({width:720,height:900})
  await openPreparation(page)
  await expect(page.getByText('¿Qué contiene esta columna?')).toBeVisible()
  await page.getByRole('button',{name:'¿Qué significa?'}).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('region',{name:/Ayuda sobre Uso de columna/})).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('region',{name:/Ayuda sobre Uso de columna/})).toBeHidden()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth-document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})

test.describe('interacción táctil emulada', () => {
  test.use({hasTouch:true})
  test('selecciona una columna y abre ayuda sin hover', async ({page}) => {
    await page.setViewportSize({width:390,height:844})
    await openPreparation(page)
    await page.getByRole('button',{name:/^Monto texto/}).tap()
    await expect(page.getByRole('heading',{name:'Monto texto'})).toBeVisible()
    await page.getByRole('button',{name:'¿Qué significa?'}).tap()
    await expect(page.getByRole('region',{name:/Ayuda sobre Uso de columna/})).toBeVisible()
  })
})

test('v0.7 muestra evidencia LIVE, replay, resultados y capturas reales', async ({page}) => {
  await page.emulateMedia({reducedMotion:'reduce'})
  await page.setViewportSize({width:1440,height:950})
  await page.goto('/')
  await expect(page.getByText('v0.7.0000')).toBeVisible()
  await page.screenshot({path:'../docs/screenshots/home.png',fullPage:true})
  await page.setViewportSize({width:390,height:844})
  await page.screenshot({path:'../docs/screenshots/mobile-home.png',fullPage:true})
  await page.setViewportSize({width:1440,height:950})
  await openPreparation(page)
  await page.screenshot({path:'../docs/screenshots/preparation.png',fullPage:true})

  const response=await page.request.get('/api/v1/runs')
  expect(response.ok()).toBeTruthy()
  const runs=(await response.json()).items as Array<{id:string;problem_type:string;result_available:boolean;latest_job_id?:string}>
  const regression=runs.find(run=>run.problem_type==='regression'&&run.result_available&&run.latest_job_id)
  const forecast=runs.find(run=>run.problem_type==='forecasting'&&run.result_available)
  expect(regression).toBeTruthy();expect(forecast).toBeTruthy()

  await page.goto(`/runs/${regression!.id}/progress?job=${regression!.latest_job_id}`)
  await expect(page.getByRole('heading',{name:'Así estamos evaluando tu data'})).toBeVisible()
  await expect(page.locator('.liveKpis article')).toHaveCount(5)
  await expect(page.getByRole('heading',{name:'¿Qué necesita cumplir un modelo para reemplazar la referencia?'})).toBeVisible()
  await expect(page.getByText('c0001')).toHaveCount(0)
  await page.screenshot({path:'../docs/screenshots/live-analysis.png',fullPage:true})
  await page.getByRole('button',{name:'Revisar cómo se obtuvo'}).click()
  await expect(page.getByText('Recorrido de una ejecución terminada.')).toBeVisible()

  await page.goto(`/runs/${regression!.id}`)
  await expect(page.getByRole('heading',{name:'Qué seleccionamos y qué comprobamos'})).toBeVisible()
  await page.screenshot({path:'../docs/screenshots/regression-result.png',fullPage:true})
  await page.goto(`/runs/${forecast!.id}`)
  await expect(page.getByText('Error histórico por distancia al futuro')).toBeVisible()
  await page.screenshot({path:'../docs/screenshots/forecast-result.png',fullPage:true})
})

test('pantallas principales no desbordan y axe no detecta violaciones automáticas', async ({page}) => {
  await page.emulateMedia({reducedMotion:'reduce'})
  await page.goto('/')
  const response=await page.request.get('/api/v1/runs')
  const run=(await response.json()).items.find((item:{result_available:boolean})=>item.result_available)
  for(const viewport of [{width:1440,height:900},{width:1024,height:800},{width:768,height:900},{width:430,height:850},{width:390,height:844}]){
    await page.setViewportSize(viewport)
    for(const path of ['/', '/guide', `/runs/${run.id}`]){
      await page.goto(path)
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)
      expect(overflow).toBeLessThanOrEqual(1)
    }
  }
  await page.setViewportSize({width:1440,height:900})
  await page.goto('/')
  const results=await new AxeBuilder({page}).analyze()
  expect(results.violations).toEqual([])
})
