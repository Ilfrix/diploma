import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Интерсептор для добавления токена
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Интерсептор для обработки ошибок
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
      toast.error('Сессия истекла, войдите снова');
    } else if (error.response?.status === 403) {
      toast.error('Доступ запрещен');
    } else if (error.response?.status === 409) {
      toast.error(error.response.data.detail || 'Дубликат изображения');
    } else if (error.response?.status === 500) {
      toast.error('Ошибка сервера');
    } else if (error.message === 'Network Error') {
      toast.error('Ошибка сети, проверьте подключение');
    }
    return Promise.reject(error);
  }
);

export default api;