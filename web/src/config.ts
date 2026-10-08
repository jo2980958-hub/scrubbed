export const BRAND = 'Scrubbed';
export const TAGLINE =
  'The perioperative coordinator that keeps every case ready and nothing missed around it: the board, the paging ladder, patient readiness, the instrument second-count and post-op follow-up, in one record.';

const env = import.meta.env;

export const API_URL: string = (env.VITE_API_URL ?? '').replace(/\/+$/, '');
export const DEMO: boolean = env.VITE_DEMO === '1' || env.VITE_DEMO === 'true';
export const COGNITO_REGION: string = env.VITE_COGNITO_REGION ?? 'us-east-1';
export const COGNITO_CLIENT_ID: string = env.VITE_COGNITO_CLIENT_ID ?? '';
export const DEV_TOKEN: string = env.VITE_DEV_TOKEN ?? '';

/** The acknowledgement window before the paging ladder places a voice call. */
export const ACK_WINDOW_MINUTES = 30;

/** WhatsApp number the agent runs on (display only). */
export const WHATSAPP_SENDER = '+233 55 906 2312';
