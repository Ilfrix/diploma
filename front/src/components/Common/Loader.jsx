import React from 'react';

const Loader = ({ size = 'large' }) => {
  const sizeClasses = {
    small: 'w-6 h-6',
    large: 'w-12 h-12',
  };

  return (
    <div className="flex justify-center items-center py-8">
      <div
        className={`${sizeClasses[size]} border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin`}
        
      />
      Загрузка
    </div>
    
  );
};

export default Loader;