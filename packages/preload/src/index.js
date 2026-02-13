const { contextBridge, ipcRenderer } = require('electron');

// セキュアなIPCブリッジを提供
contextBridge.exposeInMainWorld('electronAPI', {
    // 設定関連
    getSettings: () => ipcRenderer.invoke('get-settings'),
    saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

    // アプリ情報関連
    getAppInfo: () => ipcRenderer.invoke('get-app-info'),

    // 分析関連
    analyzeStock: (code) => ipcRenderer.invoke('analyze-stock', code),

    // 進捗更新（必要に応じて）
    onProgressUpdate: (callback) => {
        ipcRenderer.on('progress-update', (event, data) => callback(data));
    },

    // エラーハンドリング
    onError: (callback) => {
        ipcRenderer.on('error', (event, error) => callback(error));
    },

    // 遷移通知
    onNavigate: (callback) => {
        ipcRenderer.on('navigate', (event, target) => callback(target));
    },

    // MCP設定関連
    getMcpStatus: () => ipcRenderer.invoke('mcp:get-status'),
    registerMcpClient: (type) => ipcRenderer.invoke('mcp:register', type)
});
