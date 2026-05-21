import api from './api';

export const authService = {
  async register(username, email, password) {
    const response = await api.post('/register', {
      username,
      email,
      password,
    });
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('user', JSON.stringify({ 
        username, 
        email 
      }));
    }
    return response.data;
  },

  async login(username, password) {
    const response = await api.post('/login', {
      username,
      password,
    });
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('user', JSON.stringify({ 
        username 
      }));
    }
    return response.data;
  },

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  },

  getCurrentUser() {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      return JSON.parse(userStr);
    }
    return null;
  },

  isAuthenticated() {
    return !!localStorage.getItem('access_token');
  },
};