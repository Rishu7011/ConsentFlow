import axios from "axios";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use(config => {
  const userId = typeof window !== "undefined"
    ? sessionStorage.getItem("active_user_id")
    : null;
  if (userId) config.headers["X-User-ID"] = userId;
  return config;
});

export default api;
