const { app, BrowserWindow } = require('electron');

function createWindow() {
  const win = new BrowserWindow({
    width: 1280, height: 800,
    webPreferences: { contextIsolation: true }
  });
  const url = process.env.NEXT_DEV_SERVER_URL || 'http://127.0.0.1:3000';
  win.loadURL(url);
}

app.whenReady().then(()=>{
  createWindow();
  app.on('activate', ()=>{
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});
app.on('window-all-closed', ()=>{ if (process.platform !== 'darwin') app.quit(); });
