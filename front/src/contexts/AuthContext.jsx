import React, { createContext, useState, useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { authService } from '../services/auth';
import { AUTH_CONFIG } from '../utils/constants';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem(AUTH_CONFIG.TOKEN_KEY));
  const queryClient = useQueryClient();

  useEffect(() => {
    const initAuth = async () => {
      const currentUser = authService.getCurrentUser();
      const currentToken = localStorage.getItem(AUTH_CONFIG.TOKEN_KEY);
      
      if (currentUser && currentToken) {
        setUser(currentUser);
        setToken(currentToken);
      }
      setLoading(false);
    };
    
    initAuth();
  }, []);

  // Функция для очистки кэша при смене пользователя
  const clearUserCache = useCallback(() => {
    // Очищаем все запросы
    queryClient.clear();
    // Или инвалидируем конкретные ключи
    queryClient.invalidateQueries(['samples']);
    queryClient.invalidateQueries(['sample']);
    queryClient.invalidateQueries(['similar']);
  }, [queryClient]);

  const login = useCallback(async (username, password) => {
    const response = await authService.login(username, password);
    setUser({
      username
    });
    setToken(localStorage.getItem(AUTH_CONFIG.TOKEN_KEY));
    // Очищаем кэш после логина
    clearUserCache();
    return response;
  }, [clearUserCache]);

  const register = useCallback(async (username, email, password) => {
    const response = await authService.register(username, email, password);
    setUser({
      username, email
    });
    setToken(localStorage.getItem(AUTH_CONFIG.TOKEN_KEY));
    // Очищаем кэш после регистрации
    clearUserCache();
    return response;
  }, [clearUserCache]);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    setToken(null);
    // Очищаем кэш после логаута
    clearUserCache();
  }, [clearUserCache]);

  const value = {
    user,
    token,
    loading,
    isAuthenticated: !!user && !!token,
    login,
    register,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};