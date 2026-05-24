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

// Базовые методы для работы с API
export const searchApi = {
  // Синхронный поиск (старый, для совместимости)
  searchSync: (formData, params) => 
    api.post('/search/similar', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  
  // Асинхронный поиск (отправка запроса)
  searchAsync: (formData, params) => 
    api.post('/search/async', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  
  // Получение результата по request_id
  getSearchResult: (requestId) => 
    api.get(`/search/result/${requestId}`),
  
  // Получение похожих по ID образца
  getSimilar: (sampleId, params) => 
    api.get(`/samples/${sampleId}/similar`, { params }),
  
  // CRUD для образцов
  getSamples: (params) => api.get('/samples', { params }),
  getSample: (id) => api.get(`/samples/${id}`),
  createSample: (formData) => api.post('/samples', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  updateSample: (id, data) => api.put(`/samples/${id}`, data),
  deleteSample: (id) => api.delete(`/samples/${id}`),
};

export default api;