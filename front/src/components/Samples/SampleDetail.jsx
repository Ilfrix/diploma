import React from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { samplesService } from '../../services/samples';
import SimilarImages from '../Search/SimilarImages';
import Loader from '../Common/Loader';
import AuthorizedImage from '../Common/AuthorizedImage';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { FiEdit2, FiTrash2, FiArrowLeft } from 'react-icons/fi';
import toast from 'react-hot-toast';

const SampleDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: sample, isLoading } = useQuery(
    ['sample', id],
    () => samplesService.getById(id)
  );

  const isOwner = sample && sample.isOwner;

  const deleteMutation = useMutation(
    () => samplesService.delete(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('samples');
        toast.success('Эталон удален');
        navigate('/samples');
      },
      onError: (error) => {
        toast.error(error.response?.data?.detail || 'Ошибка удаления');
      }
    }
  );

  const handleDelete = () => {
      if (!isOwner) {
      toast.error('У вас нет прав на удаление этого эталона');
      return;
    }

    if (window.confirm('Вы уверены, что хотите удалить этот эталон?')) {
      deleteMutation.mutate();
    }
  };

  if (isLoading) return <Loader />;
  if (!sample) return <div className="text-center">Эталон не найден</div>;

  return (
    <div className="max-w-6xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="btn-secondary inline-flex items-center mb-6"
      >
        <FiArrowLeft className="mr-2" />
        Назад
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="card p-6">
          {sample.id}
          <AuthorizedImage
            sampleId={sample.id}
            alt={sample.name}
            className="w-full rounded-lg shadow-md"
            thumbnail={false}
          />
        </div>

        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold mb-2">{sample.name}</h1>
            {sample.description && (
              <p className="text-gray-600 text-lg">{sample.description}</p>
            )}
          </div>

          <div className="border-t pt-4">
            <p className="text-gray-500">
              Создан: {format(new Date(sample.created_at), 'dd MMMM yyyy, HH:mm', { locale: ru })}
            </p>
            <p className="text-gray-500">
              Обновлен: {format(new Date(sample.updated_at), 'dd MMMM yyyy, HH:mm', { locale: ru })}
            </p>
            {sample.owner_name && (
              <p className="text-gray-500">
                Владелец: {sample.owner_name}
              </p>
            )}
          </div>

          {isOwner && (
          <div className="flex space-x-4 pt-4">
            <Link
              to={`/samples/${sample.id}/edit`}
              className="btn-primary inline-flex items-center"
            >
              <FiEdit2 className="mr-2" />
              Редактировать
            </Link>
            <button
              onClick={handleDelete}
              disabled={deleteMutation.isLoading}
              className="btn-danger inline-flex items-center"
            >
              <FiTrash2 className="mr-2" />
              {deleteMutation.isLoading ? 'Удаление...' : 'Удалить'}
            </button>
          </div>
          )}

          {/* Сообщение для невладельцев */}
          {!isOwner && (
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-blue-700">
                🔒 Этот эталон создан другим пользователем. Вы можете просматривать его,
                но не можете редактировать или удалять.
              </p>
            </div>
          )}

        </div>
      </div>

      <div className="mt-12">
        <SimilarImages sampleId={id} sampleName={sample.name} />
      </div>
    </div>
  );
};

export default SampleDetail;
