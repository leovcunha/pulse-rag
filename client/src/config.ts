// Client Configuration File

const RAW_API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/query';

// Ensure the URL points specifically to the /api/query endpoint, 
// because Render's RENDER_EXTERNAL_URL env var only provides the base domain.
export const API_URL = RAW_API_URL.endsWith('/api/query') 
  ? RAW_API_URL 
  : `${RAW_API_URL.replace(/\/$/, '')}/api/query`;
