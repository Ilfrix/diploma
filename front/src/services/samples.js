import api from './api';

export const samplesService = {
  async getAll(params = {}) {
    const response = await api.get('/samples', { params });
    return response.data;
  },

  async getById(id) {
    const response = await api.get(`/samples/${id}`);
    return response.data;
  },

  async create(formData) {
    const response = await api.post('/samples', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async update(id, data) {
    const response = await api.put(`/samples/${id}`, data);
    return response.data;
  },

  async delete(id) {
    const response = await api.delete(`/samples/${id}`);
    return response.data;
  },

  async getSimilar(id, limit = 10, threshold = 0.7) {
    const response = await api.get(`/samples/${id}/similar`, {
      params: { limit, threshold },
    });
    return response.data;
  },

  async searchByImage(formData, limit = 10, threshold = 0.7) {
    const response = await api.post('/search/similar', formData, {
      params: { limit, threshold },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};