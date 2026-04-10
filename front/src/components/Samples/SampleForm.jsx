import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { samplesService } from '../../services/samples';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import Loader from '../Common/Loader';
import { FiUpload, FiX } from 'react-icons/fi';

const SampleForm = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEditing = !!id;

  const [formData, setFormData] = useState({
    name: '',
    description: '',
  });
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

  const { data: sample, isLoading: isLoadingSample } = useQuery(
    ['sample', id],
    () => samplesService.getById(id),
    { enabled: isEditing }
  );

  useEffect(() => {
    if (sample) {
      setFormData({
        name: sample.name,
        description: sample.description || '',
      });
      if (sample.image_path) {
        setImagePreview(`http://localhost:8000/${sample.image_path}`);
      }
    }
  }, [sample]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.bmp']
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      const file = acceptedFiles[0];
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  });

  const createMutation = useMutation(
    (data) => samplesService.create(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('samples');
        toast.success('Эталон успешно создан');
        navigate('/samples');
      },
      onError: (error) => {
        toast.error(error.response?.data?.detail || 'Ошибка создания');
      }
    }
  );

  const updateMutation = useMutation(
    ({ id, data }) => samplesService.update(id, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['sample', id]);
        queryClient.invalidateQueries('samples');
        toast.success('Эталон успешно обновлен');
        navigate(`/samples/${id}`);
      },
      onError: (error) => {
        toast.error(error.response?.data?.detail || 'Ошибка обновления');
      }
    }
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!isEditing && !imageFile) {
      toast.error('Выберите изображение');
      return;
    }
    
    if (isEditing) {
      await updateMutation.mutateAsync({ id, data: formData });
    } else {
      const formDataObj = new FormData();
      formDataObj.append('name', formData.name);
      if (formData.description) formDataObj.append('description', formData.description);
      formDataObj.append('image', imageFile);
      await createMutation.mutateAsync(formDataObj);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  if (isEditing && isLoadingSample) return <Loader />;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">
        {isEditing ? 'Редактировать эталон' : 'Создать новый эталон'}
      </h1>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-gray-700 mb-2">Название *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            className="input-field"
            placeholder="Введите название эталона"
          />
        </div>
        
        <div>
          <label className="block text-gray-700 mb-2">Описание</label>
          <textarea
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows={4}
            className="input-field"
            placeholder="Введите описание (необязательно)"
          />
        </div>
        
        {(!isEditing || (isEditing && !sample?.image_path)) && (
          <div>
            <label className="block text-gray-700 mb-2">Изображение *</label>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-500'}`}
            >
              <input {...getInputProps()} />
              <FiUpload className="mx-auto text-4xl text-gray-400 mb-2" />
              {isDragActive ? (
                <p>Отпустите файл здесь...</p>
              ) : (
                <p>Перетащите изображение или кликните для выбора</p>
              )}
              <p className="text-sm text-gray-500 mt-2">Поддерживаются: JPEG, PNG, GIF, BMP</p>
            </div>
          </div>
        )}
        
        {imagePreview && (
          <div className="relative inline-block">
            <img src={imagePreview} alt="Preview" className="max-h-64 rounded-lg" />
            <button
              type="button"
              onClick={() => {
                setImageFile(null);
                setImagePreview(null);
              }}
              className="absolute top-2 right-2 bg-red-600 text-white p-1 rounded-full hover:bg-red-700"
            >
              <FiX size={20} />
            </button>
          </div>
        )}
        
        <div className="flex space-x-4">
          <button
            type="submit"
            disabled={createMutation.isLoading || updateMutation.isLoading}
            className="btn-primary"
          >
            {createMutation.isLoading || updateMutation.isLoading
              ? 'Сохранение...'
              : isEditing
              ? 'Обновить'
              : 'Создать'}
          </button>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="btn-secondary"
          >
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
};

export default SampleForm;