import { useEffect, useState } from 'react'
import { Link, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { bootstrap } from '../api/client'
import { BrandSymbol } from '../brand/BrandSymbol'
import { Home } from '../features/home/Home'
import { Wizard } from '../features/wizard/Wizard'
import { Progress } from '../features/progress/Progress'
import { Results } from '../features/results/Results'
import { History } from '../features/history/History'
import { Settings } from '../features/settings/Settings'

export function App(){
 const [ready,setReady]=useState(false); const [error,setError]=useState('')
 useEffect(()=>{bootstrap().then(()=>setReady(true)).catch(e=>setError(String(e.message)))},[])
 if(error) return <main className="center"><section className="panel"><h1>Laboratorio ML no pudo conectarse</h1><p>{error}</p><button className="button primary" onClick={()=>location.reload()}>Reintentar</button></section></main>
 if(!ready) return <main className="center" aria-live="polite"><div className="loader"/><p>Conectando con el laboratorio local…</p></main>
 return <div className="app"><header className="topbar"><div className="brandBlock"><Link className="brand" to="/"><BrandSymbol className="brandMark" size={40}/><span className="brandName">Laboratorio <span className="brandAccent">ML</span></span></Link><a className="author" href="https://www.linkedin.com/in/luissalazarar/" target="_blank" rel="noopener noreferrer">Desarrollado por <strong>Luis Salazar</strong></a></div><nav aria-label="Principal"><NavLink to="/new">Nuevo análisis</NavLink><NavLink to="/history">Historial</NavLink><NavLink to="/settings">Estado</NavLink></nav></header><Routes><Route path="/" element={<Home/>}/><Route path="/new" element={<Wizard/>}/><Route path="/runs/:runId/progress" element={<Progress/>}/><Route path="/runs/:runId" element={<Results/>}/><Route path="/history" element={<History/>}/><Route path="/settings" element={<Settings/>}/><Route path="*" element={<Navigate to="/"/>}/></Routes></div>
}
