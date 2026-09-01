import axios from 'axios';

// No default Content-Type here: the video upload is multipart/form-data
// (axios sets that header with the correct boundary automatically when the
// request body is a FormData instance) and nothing else needs a body.
export const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api`,
});
