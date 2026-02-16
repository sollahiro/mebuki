const fs = require('fs');
const path = require('path');
const os = require('os');
const yaml = require('js-yaml');

class McpConfigManager {
    constructor(appInfo) {
        this.projectRoot = appInfo.projectRoot;
        this.isDev = appInfo.isDev;
    }

    getPaths() {
        const home = os.homedir();
        return {
            claude: process.platform === 'darwin'
                ? path.join(home, 'Library/Application Support/Claude/claude_desktop_config.json')
                : process.platform === 'win32'
                    ? path.join(process.env.APPDATA || '', 'Claude', 'claude_desktop_config.json')
                    : null,
            goose: path.join(home, '.config/goose/config.yaml'),
            lmstudio: path.join(home, '.lmstudio/mcp.json')
        };
    }

    getMebukiConfig() {
        // パッケージ時は dist/index.js を、開発時は src/index.ts (ts-node経由) を想定
        // ただし、外部アプリ(Claude等)から呼び出すため、常に実行可能なパスにする必要がある。
        // 一般的にはビルド済みのパッケージ版のパスを渡すが、開発時はプロジェクト内のパスを渡す。

        const mcpPath = path.join(this.projectRoot, 'packages', 'mcp', 'dist', 'index.js');

        return {
            command: 'node',
            args: [mcpPath],
            env: {
                MEBUKI_BACKEND_URL: 'http://localhost:8765'
            }
        };
    }

    async getStatus() {
        const paths = this.getPaths();
        const status = {
            claude: { registered: false, path: paths.claude, exists: false },
            goose: { registered: false, path: paths.goose, exists: false },
            lmstudio: { registered: false, path: paths.lmstudio, exists: false }
        };

        // Claude
        if (paths.claude && fs.existsSync(paths.claude)) {
            status.claude.exists = true;
            try {
                const config = JSON.parse(fs.readFileSync(paths.claude, 'utf8'));
                if (config.mcpServers && config.mcpServers.mebuki) {
                    status.claude.registered = true;
                }
            } catch (e) {
                console.error('Error parsing Claude config:', e);
            }
        }

        // Goose
        if (paths.goose && fs.existsSync(paths.goose)) {
            status.goose.exists = true;
            try {
                const config = yaml.load(fs.readFileSync(paths.goose, 'utf8'));
                if (config && config.extensions && config.extensions.mebuki) {
                    status.goose.registered = true;
                }
            } catch (e) {
                console.error('Error parsing Goose config:', e);
            }
        }

        // LM Studio
        if (paths.lmstudio && fs.existsSync(paths.lmstudio)) {
            status.lmstudio.exists = true;
            try {
                const config = JSON.parse(fs.readFileSync(paths.lmstudio, 'utf8'));
                if (config.mcpServers && config.mcpServers.mebuki) {
                    status.lmstudio.registered = true;
                }
            } catch (e) {
                console.error('Error parsing LM Studio config:', e);
            }
        }

        return status;
    }

    async register(type) {
        const paths = this.getPaths();
        const configPath = paths[type];
        if (!configPath) throw new Error(`Unsupported client type: ${type}`);

        const mebukiConfig = this.getMebukiConfig();
        const dir = path.dirname(configPath);
        if (!fs.existsSync(dir)) {
            try {
                fs.mkdirSync(dir, { recursive: true });
            } catch (err) {
                throw new Error(`Failed to create directory ${dir}: ${err.message}`);
            }
        }

        try {
            if (type === 'claude') {
                let config = { mcpServers: {} };
                if (fs.existsSync(configPath)) {
                    config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
                }
                config.mcpServers = config.mcpServers || {};
                config.mcpServers.mebuki = mebukiConfig;
                fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
            } else if (type === 'goose') {
                let config = { extensions: {} };
                if (fs.existsSync(configPath)) {
                    const content = fs.readFileSync(configPath, 'utf8');
                    config = yaml.load(content) || { extensions: {} };
                }

                // Goose use "cmd", "args", "envs" for MCP extensions
                config.extensions = config.extensions || {};
                config.extensions.mebuki = {
                    enabled: true,
                    name: 'mebuki',
                    description: 'Expert investment analyst tool for Japanese stocks. Provides high-precision financial data from J-QUANTS and EDINET.',
                    type: 'stdio',
                    cmd: mebukiConfig.command,
                    args: mebukiConfig.args,
                    envs: mebukiConfig.env,
                    timeout: 300
                };
                fs.writeFileSync(configPath, yaml.dump(config));
            } else if (type === 'lmstudio') {
                let config = { mcpServers: {} };
                if (fs.existsSync(configPath)) {
                    config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
                }
                config.mcpServers = config.mcpServers || {};
                config.mcpServers.mebuki = mebukiConfig;
                fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
            }
        } catch (err) {
            throw new Error(`登録中にエラーが発生しました (${type}): ${err.message}`);
        }

        return { success: true };
    }
}

module.exports = McpConfigManager;
