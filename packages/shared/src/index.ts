/**
 * Shared types and constants for mebuki
 */

export interface SystemSettings {
    jquantsApiKey: string;
    edinetApiKey: string;
    llmProvider: 'gemini' | 'openai';
}

export const APP_CHANNELS = {
    GET_SETTINGS: 'get-settings',
    SAVE_SETTINGS: 'save-settings',
    ANALYZE_STOCK: 'analyze-stock',
    PROGRESS_UPDATE: 'progress-update',
    ERROR: 'error'
};
