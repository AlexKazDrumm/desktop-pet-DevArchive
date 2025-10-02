'use client';
import axios from 'axios';
import { useEffect, useState } from 'react';

type Project = { id:string; name:string; kind:string; context?:string|null; localPath?:string|null; };

export default function Page() {
  const [items, setItems] = useState<Project[]>([]);
  const [q, setQ] = useState('');
  const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7780';

  const load = async () => {
    const { data } = await axios.get(API + '/projects', { params: q ? { q } : undefined });
    setItems(data);
  };
  useEffect(()=>{ load().catch(console.error); },[]);

  return (
    <div>
      <div style={{display:'flex', gap:8, marginBottom:10}}>
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Поиск..." style={{padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}} />
        <button onClick={load} style={{background:'#ffd700', color:'#000', border:0, borderRadius:8, padding:'8px 12px'}}>Найти</button>
      </div>
      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
        {items.map(p => (
          <div key={p.id} style={{border:'1px solid #333', borderRadius:10, padding:12, background:'#121212'}}>
            <div style={{fontWeight:700, fontSize:16}}>{p.name}</div>
            <div style={{opacity:.8}}>Тип: {p.kind}</div>
            {p.context ? <div style={{opacity:.8}}>Контекст: {p.context}</div> : null}
            {p.localPath ? <div style={{opacity:.8}}>Путь: {p.localPath}</div> : null}
            <div style={{display:'flex', gap:8, marginTop:10}}>
              <button onClick={async()=>{ await axios.post(API + `/projects/${p.id}/scan`); alert('Запущен scan'); }} style={{background:'#ffd700', color:'#000', border:0, borderRadius:8, padding:'6px 10px'}}>Snap Tree</button>
              <button onClick={async()=>{ await axios.post(API + `/projects/${p.id}/concat`); alert('Запущен concat'); }} style={{background:'#ffd700', color:'#000', border:0, borderRadius:8, padding:'6px 10px'}}>Concat</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
