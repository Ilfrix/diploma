import React, { createContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/auth';
import { AUTH_CONFIG } from '../utils/constants';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem(AUTH_CONFIG.TOKEN_KEY));

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

  const login = useCallback(async (username, password) => {
    const response = await authService.login(username, password);
    setUser({ username });
    setToken(localStorage.getItem(AUTH_CONFIG.TOKEN_KEY));
    return response;
  }, []);

  const register = useCallback(async (username, email, password) => {
    const response = await authService.register(username, email, password);
    setUser({ username, email });
    setToken(localStorage.getItem(AUTH_CONFIG.TOKEN_KEY));
    return response;
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    setToken(null);
  }, []);

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