import React from 'react';
import { FiAlertCircle } from 'react-icons/fi';

const ErrorMessage = ({ message, onRetry }) => {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
      <FiAlertCircle className="mx-auto text-red-500 text-4xl mb-2" />
      <p className="text-red-700 mb-3">{message || 'Произошла ошибка'}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary text-sm">
          Попробовать снова
        </button>
      )}
    </div>
  );
};

export default ErrorMessage;
