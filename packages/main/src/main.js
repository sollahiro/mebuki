const { app, BrowserWindow, ipcMain, nativeTheme, dialog, Menu, shell } = require('electron');
const path = require('path');

// 明示的にアプリ名を指定することで、保存先ディレクトリを固定する
app.name = 'mebuki';
const { autoUpdater } = require('electron-updater');

const Store = require('electron-store');
const { spawn, exec } = require('child_process');
const fs = require('fs');
const McpConfigManager = require('./mcpConfigManager');
const keytar = require('keytar');

const store = new Store();
const isDev = !app.isPackaged;
const isDevFrontend = process.env.ELECTRON_DEV === 'true';
const FASTAPI_PORT = 8765;
let fastApiProcess = null;
let isManualUpdateCheck = false;

let mainWindow;

// バックエンド実行ファイルのパスを取得
function getBackendExecutablePath() {
  if (isDev) {
    // 開発時は仮想環境のPythonを返す
    const projectRoot = path.join(__dirname, '..', '..', '..');
    const venvPython = process.platform === 'win32'
      ? path.join(projectRoot, 'venv', 'Scripts', 'python.exe')
      : path.join(projectRoot, 'venv', 'bin', 'python3');

    console.log(`🔍 Checking Python at: ${venvPython}`);
    if (fs.existsSync(venvPython)) {
      return venvPython;
    }
    return process.platform === 'win32' ? 'python' : 'python3';
  } else {
    // パッケージ時は resources フォルダ内のバイナリを返す
    // electron-builder の extraResources 設定で /backend に配置することを想定
    const binName = process.platform === 'win32' ? 'mebuki-backend.exe' : 'mebuki-backend';
    const binPath = path.join(process.resourcesPath, 'backend', 'mebuki-backend', binName);
    console.log(`📦 Prod Backend Binary path: ${binPath}`);
    return binPath;
  }
}

// 資産（アイコン等）のパスを取得
function getAssetPath(filename) {
  if (isDev) {
    // 開発時はプロジェクトルートの assets フォルダ
    return path.join(__dirname, '..', '..', '..', 'assets', filename);
  } else {
    // 本番時は appPath 直下の assets フォルダ
    // ただし asarUnpack されたファイルを参照するため、.asar.unpacked を優先する
    const appPath = app.getAppPath();
    const unpackedPath = appPath.endsWith('.asar') ? `${appPath}.unpacked` : appPath;
    const assetPath = path.join(unpackedPath, 'assets', filename);

    // unpacked に存在しない場合（アイコン等）は通常の appPath を使う
    if (fs.existsSync(assetPath)) {
      return assetPath;
    }
    return path.join(appPath, 'assets', filename);
  }
}

// ポートが使用中かチェックし、既存のプロセスを停止
async function killProcessOnPort(port) {
  return new Promise((resolve) => {
    const command = process.platform === 'win32'
      ? `netstat -ano | findstr :${port}`
      : `lsof -ti:${port}`;

    exec(command, (error, stdout) => {
      if (error || !stdout.trim()) {
        resolve(false);
        return;
      }

      const pids = stdout.trim().split('\n').filter(pid => pid);
      pids.forEach(pid => {
        if (process.platform === 'win32') {
          exec(`taskkill /F /PID ${pid}`, () => { });
        } else {
          exec(`kill -9 ${pid}`, () => { });
        }
      });

      console.log(`🛑 Killed existing process on port ${port}`);
      setTimeout(resolve, 1000);
    });
  });
}

// FastAPIサーバーを起動
async function startFastAPIServer() {
  return new Promise(async (resolve, reject) => {
    const executablePath = getBackendExecutablePath();
    const projectRoot = path.join(__dirname, '..', '..', '..');

    console.log('🚀 Starting FastAPI server...');
    await killProcessOnPort(FASTAPI_PORT);

    if (isDev) {
      // 開発モード: python -m uvicorn ...
      console.log(`   Mode: Development (Python)`);

      // 開発モードでもユーザーデータパスを渡す（テスト・検証用）
      const userDataPath = app.getPath('userData');
      const assetsPath = getAssetPath('');

      fastApiProcess = spawn(executablePath, [
        '-m', 'uvicorn',
        'backend.main:app',
        '--host', '127.0.0.1',
        '--port', String(FASTAPI_PORT)
      ], {
        cwd: projectRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          PYTHONPATH: projectRoot,
          MEBUKI_USER_DATA_PATH: userDataPath,
          MEBUKI_ASSETS_PATH: assetsPath
        }
      });
    } else {
      // 本番モード: バイナリを直接実行
      console.log(`   Mode: Production (Binary)`);
      const backendRoot = path.dirname(executablePath);

      // 永続データ保存先のパスを取得
      const userDataPath = app.getPath('userData');
      const cachePath = path.join(userDataPath, 'analysis_cache');
      const dataPath = path.join(userDataPath, 'data');
      const reportsPath = path.join(userDataPath, 'reports');
      const assetsPath = getAssetPath('');

      // ディレクトリが存在することを確認
      if (!fs.existsSync(cachePath)) fs.mkdirSync(cachePath, { recursive: true });
      if (!fs.existsSync(dataPath)) fs.mkdirSync(dataPath, { recursive: true });
      if (!fs.existsSync(reportsPath)) fs.mkdirSync(reportsPath, { recursive: true });

      fastApiProcess = spawn(executablePath, [], {
        cwd: backendRoot, // バイナリの場所をカレントディレクトリに（内部リソース参照のため）
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          MEBUKI_USER_DATA_PATH: userDataPath,
          MEBUKI_ASSETS_PATH: assetsPath
        }
      });
    }

    const startupTimeout = setTimeout(() => {
      console.log('⚠️ FastAPI server startup timeout (15s), moving on...');
      resolve();
    }, 15000);

    fastApiProcess.stdout.on('data', (data) => {
      const output = data.toString();
      process.stdout.write(`[FastAPI STDOUT] ${output}`);
      if (output.includes('Uvicorn running')) {
        console.log('✅ FastAPI server started successfully');
        clearTimeout(startupTimeout);
        resolve();
      }
    });

    fastApiProcess.stderr.on('data', (data) => {
      const output = data.toString();
      process.stderr.write(`[FastAPI STDERR] ${output}`);
      if (output.includes('Uvicorn running')) {
        clearTimeout(startupTimeout);
        resolve();
      }
    });

    fastApiProcess.on('error', (err) => {
      console.error('❌ Failed to start FastAPI process:', err);
      clearTimeout(startupTimeout);
      reject(err);
    });

    fastApiProcess.on('close', (code) => {
      console.log(`ℹ️ FastAPI process exited with code ${code}`);
      fastApiProcess = null;
    });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    title: 'mebuki',
    icon: getAssetPath('icon.png'),
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 18, y: 18 },
    webPreferences: {
      preload: path.join(__dirname, '..', '..', '..', 'packages', 'preload', 'src', 'index.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // ダークモードに応じてアイコンを切り替える
  const updateIcon = () => {
    const iconName = nativeTheme.shouldUseDarkColors ? 'icon_dark.png' : 'icon.png';
    const iconPath = getAssetPath(iconName);
    if (fs.existsSync(iconPath)) {
      mainWindow.setIcon(iconPath);
      // macOSの場合、Dockアイコンも更新
      if (process.platform === 'darwin' && app.dock) {
        app.dock.setIcon(iconPath);
      }
    } else {
      console.warn(`⚠️ Icon not found: ${iconPath}`);
    }
  };

  nativeTheme.on('updated', updateIcon);
  updateIcon(); // 初回設定

  if (isDevFrontend) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    const indexPath = path.join(__dirname, '..', '..', 'renderer', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);

    // 開発環境（未パッケージ）の場合はデベロッパーツールを開けるようにする
    if (isDev) {
      mainWindow.webContents.on('before-input-event', (event, input) => {
        if ((input.control || input.meta) && input.shift && input.key.toLowerCase() === 'i') {
          mainWindow.webContents.openDevTools();
        }
      });
    }
  }

  // 外部リンクをシステムブラウザで開くように設定
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http:') || url.startsWith('https:')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createApplicationMenu() {
  const isMac = process.platform === 'darwin';

  const template = [
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { role: 'about', label: `${app.name}について` },
        {
          label: 'アップデートを確認...',
          click: () => {
            isManualUpdateCheck = true;
            autoUpdater.checkForUpdatesAndNotify();
          }
        },
        { type: 'separator' },
        {
          label: '設定...',
          accelerator: 'CmdOrCtrl+,',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.send('navigate', 'settings');
            }
          }
        },
        { type: 'separator' },
        { role: 'services', label: 'サービス' },
        { type: 'separator' },
        { role: 'hide', label: `${app.name}を隠す` },
        { role: 'hideOthers', label: 'ほかを隠す' },
        { role: 'unhide', label: 'すべてを表示' },
        { type: 'separator' },
        { role: 'quit', label: `${app.name}を終了` }
      ]
    }] : []),
    {
      label: '表示',
      submenu: [
        { role: 'reload', label: '再読み込み' },
        { role: 'forceReload', label: '強制的に再読み込み' },
        { role: 'toggleDevTools', label: 'デベロッパーツールを表示' },
        { type: 'separator' },
        { role: 'resetZoom', label: '実際のサイズ' },
        { role: 'zoomIn', label: '拡大' },
        { role: 'zoomOut', label: '縮小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: 'フルスクリーンにする' }
      ]
    },
    {
      label: 'ウィンドウ',
      submenu: [
        { role: 'minimize', label: '最小化' },
        { role: 'zoom', label: 'ズーム' },
        ...(isMac ? [
          { type: 'separator' },
          { role: 'front', label: 'すべてを手前に移動' },
          { type: 'separator' },
          { role: 'window', label: 'ウィンドウ' }
        ] : [
          { role: 'close', label: '閉じる' }
        ])
      ]
    },
    {
      label: 'ヘルプ',
      role: 'help',
      submenu: [
        {
          label: '詳細情報',
          click: async () => {
            const { shell } = require('electron');
            await shell.openExternal('https://github.com/sollahiro/mebuki');
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function setupIpcHandlers() {
  ipcMain.handle('get-settings', async () => {
    let jquantsApiKey = '';
    let edinetApiKey = '';

    try {
      jquantsApiKey = await keytar.getPassword('mebuki', 'jquantsApiKey') || '';
      edinetApiKey = await keytar.getPassword('mebuki', 'edinetApiKey') || '';
    } catch (err) {
      console.error('❌ Failed to get passwords from Keychain:', err);
    }

    return {
      jquantsApiKey,
      edinetApiKey,
      llmProvider: store.get('llmProvider', 'gemini'),
      mcpEnabled: true
    };
  });


  ipcMain.handle('get-app-info', () => {
    // 開発環境とパッケージ環境の両方でプロジェクトルートを推測
    const appPath = app.getAppPath();
    let projectRoot;

    if (isDev) {
      // 開発時は packages/main から見たルート
      projectRoot = path.join(__dirname, '..', '..', '..');
    } else {
      // パッケージ時は appPath (Contents/Resources/app.asar) をベースにするが、
      // 外部プロセスである ts-node から中身を読めるように .asar.unpacked をルートにする
      projectRoot = appPath.endsWith('.asar') ? `${appPath}.unpacked` : appPath;
    }

    console.log(`📂 App Info Requested. projectRoot: ${projectRoot}`);
    return {
      projectRoot,
      isDev
    };
  });

  ipcMain.handle('save-settings', async (event, settings) => {
    try {
      if (settings.jquantsApiKey !== undefined) {
        await keytar.setPassword('mebuki', 'jquantsApiKey', settings.jquantsApiKey || '');
        store.delete('jquantsApiKey'); // 平文保存を削除
      }
      if (settings.edinetApiKey !== undefined) {
        await keytar.setPassword('mebuki', 'edinetApiKey', settings.edinetApiKey || '');
        store.delete('edinetApiKey'); // 平文保存を削除
      }
    } catch (err) {
      console.error('❌ Failed to save passwords to Keychain:', err);
      return { success: false, error: 'Keychain access failed' };
    }

    store.set('llmProvider', settings.llmProvider || 'gemini');
    store.set('mcpEnabled', true);

    return { success: true };
  });

  // MCP Configuration Handlers
  ipcMain.handle('mcp:get-status', async () => {
    const isDev = !app.isPackaged;
    let projectRoot;
    if (isDev) {
      projectRoot = path.join(__dirname, '..', '..', '..');
    } else {
      projectRoot = app.getAppPath().endsWith('.asar') ? `${app.getAppPath()}.unpacked` : app.getAppPath();
    }

    const backendBin = getBackendExecutablePath();
    const assetsPath = getAssetPath('');
    const manager = new McpConfigManager({ projectRoot, isDev, backendBin, assetsPath });
    return await manager.getStatus();
  });

  ipcMain.handle('mcp:register', async (event, type) => {
    const isDev = !app.isPackaged;
    let projectRoot;
    if (isDev) {
      projectRoot = path.join(__dirname, '..', '..', '..');
    } else {
      projectRoot = app.getAppPath().endsWith('.asar') ? `${app.getAppPath()}.unpacked` : app.getAppPath();
    }

    const backendBin = getBackendExecutablePath();
    const assetsPath = getAssetPath('');
    const manager = new McpConfigManager({ projectRoot, isDev, backendBin, assetsPath });
    return await manager.register(type);
  });

  // 外部リンクをシステムブラウザで開く
  ipcMain.handle('shell:open-external', async (event, url) => {
    if (url.startsWith('http:') || url.startsWith('https:')) {
      await shell.openExternal(url);
      return { success: true };
    }
    return { success: false, error: 'Invalid URL' };
  });
}

// アップデート機能の初期化
function initAutoUpdater() {
  // 自動ダウンロードを無効化（ユーザーの許可を得てから開始する）
  autoUpdater.autoDownload = false;

  // 開発環境では詳細なログを出力
  if (isDev) {
    autoUpdater.logger = require('electron-log');
    autoUpdater.logger.transports.file.level = 'info';
  }


  autoUpdater.on('update-available', (info) => {
    console.log('📢 Update available.');
    dialog.showMessageBox({
      type: 'info',
      title: 'アップデートが見つかりました',
      message: `新しいバージョン（v${info.version}）が利用可能です。ダウンロードを開始しますか？`,
      buttons: ['ダウンロード', '後で'],
      defaultId: 0,
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.downloadUpdate();
      }
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    console.log('✅ Update downloaded.');
    dialog.showMessageBox({
      type: 'info',
      title: 'アップデート準備完了',
      message: `新しいバージョン（v${info.version}）の準備ができました。アプリを再起動して適用しますか？`,
      buttons: ['再起動', '後で'],
      defaultId: 0,
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall();
      }
    });
  });

  autoUpdater.on('error', (err) => {
    console.error('❌ Update error:', err);
    if (isManualUpdateCheck) {
      dialog.showErrorBox('アップデートの確認に失敗しました', `エラーが発生しました: ${err.message || err}`);
      isManualUpdateCheck = false;
    }
  });

  autoUpdater.on('update-not-available', () => {
    console.log('✅ App is up to date.');
    if (isManualUpdateCheck) {
      dialog.showMessageBox({
        type: 'info',
        title: 'アップデート確認',
        message: 'お使いのバージョンは最新です。',
        buttons: ['OK']
      });
      isManualUpdateCheck = false;
    }
  });

  // 定期的にチェック（例: 起動時）
  if (!isDev) {
    isManualUpdateCheck = false; // 起動時は自動チェック扱い
    autoUpdater.checkForUpdatesAndNotify().catch(err => {
      console.error('⚠️ Failed to check for updates (this is expected if no releases exist or token is missing):', err);
    });
  }
}

// 既存の平文設定からキーチェーンへの移行
async function migrateKeysToKeychain() {
  const keys = ['jquantsApiKey', 'edinetApiKey'];
  for (const key of keys) {
    const value = store.get(key);
    if (value) {
      console.log(`🔐 Migrating ${key} to Keychain...`);
      try {
        await keytar.setPassword('mebuki', key, value);
        store.delete(key);
        console.log(`✅ Migrated ${key} and removed from plain-text store.`);
      } catch (err) {
        console.error(`❌ Failed to migrate ${key}:`, err);
      }
    }
  }
}

app.whenReady().then(async () => {
  console.log('🏁 Electron App Ready');
  await migrateKeysToKeychain();
  try {
    await startFastAPIServer();
  } catch (err) {
    console.error('Critical error during server startup:', err);
  }
  setupIpcHandlers();
  initAutoUpdater();
  createApplicationMenu();
  createWindow();


  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

let isQuitting = false;
function quitApp() {
  if (isQuitting) return;
  isQuitting = true;

  if (fastApiProcess) {
    console.log('🛑 Killing FastAPI server before exit...');
    try {
      fastApiProcess.kill();
      fastApiProcess = null;
    } catch (err) {
      console.error('Error killing FastAPI process:', err);
    }
  }
  app.quit();
}

app.on('will-quit', () => {
  quitApp();
});

// シグナルハンドリング
process.on('SIGINT', () => {
  console.log('Received SIGINT, quitting...');
  quitApp();
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, quitting...');
  quitApp();
});

// 予期せぬエラーの捕捉
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  quitApp();
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  quitApp();
});
