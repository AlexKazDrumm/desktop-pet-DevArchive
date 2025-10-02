export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body style={{fontFamily:'system-ui, Segoe UI, Roboto, Arial, sans-serif', background:'#0b0b0b', color:'#f2f2f2', margin:0}}>
        <div style={{maxWidth: 1100, margin: '16px auto', padding: '0 16px'}}>
          <h1>Dev Archive Manager</h1>
          <nav style={{display:'flex', gap:12, marginBottom:12}}>
            <a href="/" style={{color:'#ffd700'}}>Проекты</a>
            <a href="/new" style={{color:'#ffd700'}}>Создать проект</a>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
