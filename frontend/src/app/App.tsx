import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { bootstrap } from '../api/client'
import { Home } from '../features/home/Home'
import { Wizard } from '../features/wizard/Wizard'
import { Progress } from '../features/progress/Progress'
import { Results } from '../features/results/Results'
import { History } from '../features/history/History'
import { Settings } from '../features/settings/Settings'

export function App(){
 const [ready,setReady]=useState(false); const [error,setError]=useState('')
 useEffect(()=>{bootstrap().then(()=>setReady(true)).catch(e=>setError(String(e.message)))},[])
 if(error) return <main className="center"><section className="panel"><h1>No pudimos conectar</h1><p>{error}</p><button onClick={()=>location.reload()}>Reintentar</button></section></main>
 if(!ready) return <main className="center" aria-live="polite"><div className="loader"/><p>Conectando con el laboratorio local…</p></main>
 return <div className="app"><header className="topbar"><Link className="brand" to="/"><span className="brandMark">LM</span><span>Laboratorio ML</span></Link><nav aria-label="Principal"><Link to="/new">Nuevo análisis</Link><Link to="/history">Historial</Link><Link to="/settings">Estado</Link></nav></header><Routes><Route path="/" element={<Home/>}/><Route path="/new" element={<Wizard/>}/><Route path="/runs/:runId/progress" element={<Progress/>}/><Route path="/runs/:runId" element={<Results/>}/><Route path="/history" element={<History/>}/><Route path="/settings" element={<Settings/>}/><Route path="*" element={<Navigate to="/"/>}/></Routes></div>
}

