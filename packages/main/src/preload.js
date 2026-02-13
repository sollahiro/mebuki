const { contextBridge, ipcRenderer } = require('electron');

// セキュアなIPCブリッジを提供
contextBridge.exposeInMainWorld('electronAPI', {
  // 設定関連
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

  // 分析関連
  analyzeStock: (code) => ipcRenderer.invoke('analyze-stock', code),

  // アプリ情報
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),

  // 進捗更新（必要に応じて）
  onProgressUpdate: (callback) => {
    ipcRenderer.on('progress-update', (event, data) => callback(data));
  },

  // エラーハンドリング
  onError: (callback) => {
    ipcRenderer.on('error', (event, error) => callback(error));
  }
});
