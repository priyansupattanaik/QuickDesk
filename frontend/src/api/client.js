import axios from "axios";

export const apiBase = import.meta.env.VITE_API_URL || "";
const client = axios.create({ baseURL: apiBase });
client.interceptors.request.use((config) => { const token = localStorage.getItem("quickdesk_token"); if (token) config.headers.Authorization = `Bearer ${token}`; return config; });
export default client;
