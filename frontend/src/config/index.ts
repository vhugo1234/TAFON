// Define a URL base do seu backend.
// Se você está usando a porta 8000 (FastAPI), é ela que deve ser usada.
export const BACKEND_URL = 'http://localhost:8000'; 

// O restante da sua API (rotas, etc.)
export const API_BASE_PATH = `${BACKEND_URL}/api/v1`; 

// Pode ser que você já tenha essa constante em outro lugar. 
// Se sim, apenas use a constante existente.