'use client';
import { useState } from 'react';
import axios from 'axios';

export default function NewProject() {
  const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7780';
  const [name, setName] = useState('');
  const [kind, setKind] = useState('WEB');
  const [context, setContext] = useState('');
  const [localPath, setLocalPath] = useState('');
  const [notes, setNotes] = useState('');
  const [links, setLinks] = useState<{type:string,url:string,label?:string}[]>([]);

  const addLink = () => setLinks([...links, {type:'REPO_GITHUB', url:''}]);

  const submit = async () => {
    if(!name || !kind){ alert('Название и тип — обязательны'); return; }
    const payload:any = { name, kind };
    if (context) payload.context = context;
    if (localPath) payload.localPath = localPath;
    if (notes) payload.notes = notes;
    if (links.length) payload.links = links.filter(l=>l.url);
    await axios.post(API + '/projects', payload);
    window.location.href = '/';
  };

  return (
    <div>
      <div style={{display:'grid', gap:10, maxWidth:650}}>
        <label>Название*<br/>
          <input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%', padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}}/>
        </label>
        <label>Тип*<br/>
          <select value={kind} onChange={e=>setKind(e.target.value)} style={{padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}}>
            {['WEB','DESKTOP','MOBILE','PARSER','BOT','LIBRARY','SERVICE','DATA_PIPELINE','GAME','OTHER'].map(k=>(<option key={k} value={k}>{k}</option>))}
          </select>
        </label>
        <label>Контекст (WORK/ORDER/PET)<br/>
          <select value={context} onChange={e=>setContext(e.target.value)} style={{padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}}>
            <option value="">—</option>
            {['WORK','ORDER','PET'].map(k=>(<option key={k} value={k}>{k}</option>))}
          </select>
        </label>
        <label>Локальный путь (опционально)<br/>
          <input value={localPath} onChange={e=>setLocalPath(e.target.value)} placeholder="D:/dev/..." style={{width:'100%', padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}}/>
        </label>
        <label>Заметки<br/>
          <textarea value={notes} onChange={e=>setNotes(e.target.value)} style={{width:'100%', height:120, padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}} />
        </label>

        <div style={{border:'1px dashed #333', borderRadius:10, padding:10}}>
          <div style={{display:'flex', justifyContent:'space-between'}}>
            <strong>Ссылки</strong>
            <button onClick={addLink} style={{background:'#ffd700', color:'#000', border:0, borderRadius:8, padding:'6px 10px'}}>+ ссылка</button>
          </div>
          <div style={{display:'grid', gap:8, marginTop:8}}>
            {links.map((l,idx)=>(
              <div key={idx} style={{display:'grid', gridTemplateColumns:'1fr 2fr 1fr auto', gap:8}}>
                <select value={l.type} onChange={e=>{ const arr=[...links]; arr[idx]={...l,type:e.target.value}; setLinks(arr); }}
                        style={{padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}}>
                  {['REPO_GITHUB','REPO_GITLAB','REPO_OTHER','FIGMA','DOCS','ISSUE_TRACKER','CI','PROD_URL','MIRROR','OTHER'].map(t=>(<option key={t} value={t}>{t}</option>))}
                </select>
                <input value={l.url} onChange={e=>{ const arr=[...links]; arr[idx]={...l,url:e.target.value}; setLinks(arr); }}
                       placeholder="https://..." style={{padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}}/>
                <input value={l.label||''} onChange={e=>{ const arr=[...links]; arr[idx]={...l,label:e.target.value}; setLinks(arr); }}
                       placeholder="label" style={{padding:8, borderRadius:8, border:'1px solid #333', background:'#111', color:'#eee'}}/>
                <button onClick={()=>{ const arr=[...links]; arr.splice(idx,1); setLinks(arr);}} style={{background:'#222', color:'#fff', border:0, borderRadius:8, padding:'6px 10px'}}>x</button>
              </div>
            ))}
          </div>
        </div>

        <button onClick={submit} style={{background:'#ffd700', color:'#000', border:0, borderRadius:8, padding:'10px 14px'}}>Создать</button>
      </div>
    </div>
  );
}
