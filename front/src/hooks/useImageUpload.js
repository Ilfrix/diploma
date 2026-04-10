import { useState, useCallback } from 'react';
import toast from 'react-hot-toast';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'];

export const useImageUpload = (options = {}) => {
  const {
    maxSize = MAX_FILE_SIZE,
    allowedTypes = ALLOWED_TYPES,
    multiple = false,
    onSuccess,
    onError,
  } = options;
  
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const validateFile = useCallback((file) => {
    if (!allowedTypes.includes(file.type)) {
      throw new Error(`Неподдерживаемый тип файла: ${file.type}. Разрешены: ${allowedTypes.join(', ')}`);
    }
    
    if (file.size > maxSize) {
      throw new Error(`Файл слишком большой. Максимальный размер: ${maxSize / 1024 / 1024}MB`);
    }
    
    return true;
  }, [allowedTypes, maxSize]);
  
  const generatePreview = useCallback((file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        resolve(reader.result);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }, []);
  
  const addFiles = useCallback(async (newFiles) => {
    setError(null);
    const fileArray = Array.isArray(newFiles) ? newFiles : [newFiles];
    
    const validFiles = [];
    const validPreviews = [];
    
    for (const file of fileArray) {
      try {
        validateFile(file);
        const preview = await generatePreview(file);
        validFiles.push(file);
        validPreviews.push(preview);
      } catch (err) {
        toast.error(err.message);
        if (onError) onError(err);
      }
    }
    
    if (multiple) {
      setFiles(prev => [...prev, ...validFiles]);
      setPreviews(prev => [...prev, ...validPreviews]);
    } else {
      setFiles(validFiles.slice(0, 1));
      setPreviews(validPreviews.slice(0, 1));
    }
    
    if (validFiles.length > 0 && onSuccess) {
      onSuccess(validFiles);
    }
    
    return validFiles;
  }, [validateFile, generatePreview, multiple, onSuccess, onError]);
  
  const removeFile = useCallback((index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setPreviews(prev => prev.filter((_, i) => i !== index));
  }, []);
  
  const clearFiles = useCallback(() => {
    setFiles([]);
    setPreviews([]);
    setError(null);
  }, []);
  
  const uploadToServer = useCallback(async (uploadFn, additionalData = {}) => {
    if (files.length === 0) {
      toast.error('Нет файлов для загрузки');
      return null;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      
      if (multiple) {
        files.forEach((file, index) => {
          formData.append(`images[${index}]`, file);
        });
      } else {
        formData.append('image', files[0]);
      }
      
      Object.entries(additionalData).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          formData.append(key, value);
        }
      });
      
      const result = await uploadFn(formData);
      toast.success('Загрузка успешна!');
      return result;
    } catch (err) {
      const message = err.response?.data?.detail || 'Ошибка загрузки';
      setError(message);
      toast.error(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [files, multiple]);
  
  return {
    files,
    previews,
    loading,
    error,
    addFiles,
    removeFile,
    clearFiles,
    uploadToServer,
    hasFiles: files.length > 0,
    fileCount: files.length,
  };
};

// Хук для загрузки одного изображения
export const useSingleImageUpload = (options = {}) => {
  return useImageUpload({ ...options, multiple: false });
};

// Хук для загрузки нескольких изображений
export const useMultipleImageUpload = (options = {}) => {
  return useImageUpload({ ...options, multiple: true });
};