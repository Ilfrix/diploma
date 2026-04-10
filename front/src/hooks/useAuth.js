import { useContext, useCallback } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import toast from 'react-hot-toast';

export const useAuth = () => {
  const context = useContext(AuthContext);
  
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  
  const { user, loading, login: contextLogin, register: contextRegister, logout: contextLogout } = context;
  
  const login = useCallback(async (username, password) => {
    try {
      await contextLogin(username, password);
      toast.success('Добро пожаловать!');
      return true;
    } catch (error) {
      const message = error.response?.data?.detail || 'Ошибка входа';
      toast.error(message);
      return false;
    }
  }, [contextLogin]);
  
  const register = useCallback(async (username, email, password) => {
    try {
      await contextRegister(username, email, password);
      toast.success('Регистрация успешна!');
      return true;
    } catch (error) {
      const message = error.response?.data?.detail || 'Ошибка регистрации';
      toast.error(message);
      return false;
    }
  }, [contextRegister]);
  
  const logout = useCallback(() => {
    contextLogout();
    toast.success('Вы вышли из системы');
  }, [contextLogout]);
  
  return {
    user,
    isAuthenticated: !!user,
    loading,
    login,
    register,
    logout,
  };
};