/**
 * Shared types and constants for mebuki
 */

export interface SystemSettings {
    jquantsApiKey: string;
    edinetApiKey: string;
    geminiApiKey: string;
    llmProvider: 'gemini' | 'openai';
    geminiModel: string;
}

export const APP_CHANNELS = {
    GET_SETTINGS: 'get-settings',
    SAVE_SETTINGS: 'save-settings',
    ANALYZE_STOCK: 'analyze-stock',
    PROGRESS_UPDATE: 'progress-update',
    ERROR: 'error'
};
