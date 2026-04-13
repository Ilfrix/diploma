"""
Модуль для работы с MinIO S3
"""
import io
from typing import Optional, BinaryIO
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from fastapi import HTTPException, status, UploadFile

from app.config import config

class MinIOClient:
    """Клиент для работы с MinIO"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Инициализация клиента MinIO"""
        try:
            self.client = Minio(
                config.MINIO_ENDPOINT,
                access_key=config.MINIO_ACCESS_KEY,
                secret_key=config.MINIO_SECRET_KEY,
                secure=False
            )
            
            # Создаем bucket если не существует
            if not self.client.bucket_exists(config.MINIO_BUCKET_NAME):
                self.client.make_bucket(config.MINIO_BUCKET_NAME)
             
        except Exception as e:
            print(f"Failed to initialize MinIO client: {e}")
            self.client = None
        print('client')
        print(config.MINIO_ENDPOINT,config.MINIO_ACCESS_KEY,config.MINIO_SECRET_KEY)
        print(self.client)
        print(config.KAFKA_CONSUMER_GROUP)
        print('-'*100)
    
    def upload_file(
        self, 
        file_data: bytes, 
        object_path: str, 
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Загрузить файл в MinIO
        
        Args:
            file_data: Содержимое файла в байтах
            object_path: Путь к объекту в MinIO
            content_type: MIME тип файла
        
        Returns:
            str: Путь к загруженному объекту
        """
        print(self.client)
        print('upload file')
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MinIO client not initialized"
            )
        
        try:
            file_io = io.BytesIO(file_data)
            file_size = len(file_data)
            
            self.client.put_object(
                bucket_name=config.MINIO_BUCKET_NAME,
                object_name=object_path,
                data=file_io,
                length=file_size,
                content_type=content_type
            )
            return object_path
            
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to MinIO: {str(e)}"
            )
    
    def upload_uploadfile(
        self, 
        upload_file: UploadFile, 
        object_path: str
    ) -> str:
        """
        Загрузить UploadFile в MinIO
        
        Args:
            upload_file: FastAPI UploadFile объект
            object_path: Путь к объекту в MinIO
        
        Returns:
            str: Путь к загруженному объекту
        """
        content = upload_file.file.read()
        return self.upload_file(
            file_data=content,
            object_path=object_path,
            content_type=upload_file.content_type or "application/octet-stream"
        )
    
    def download_file(self, object_path: str) -> bytes:
        """
        Скачать файл из MinIO
        
        Args:
            object_path: Путь к объекту в MinIO
        
        Returns:
            bytes: Содержимое файла
        """
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MinIO client not initialized"
            )
        
        try:
            response = self.client.get_object(
                config.MINIO_BUCKET_NAME,
                object_path
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data
            
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found in MinIO: {str(e)}"
            )
    
    def delete_file(self, object_path: str) -> bool:
        """
        Удалить файл из MinIO
        
        Args:
            object_path: Путь к объекту в MinIO
        
        Returns:
            bool: True если удаление успешно
        """
        if not self.client:
            return False
        
        try:
            self.client.remove_object(config.MINIO_BUCKET_NAME, object_path)
            return True
        except S3Error:
            return False
    
    def get_file_url(self, object_path: str, expires: int = 3600) -> str:
        """
        Получить временную URL для доступа к файлу
        
        Args:
            object_path: Путь к объекту в MinIO
            expires: Время жизни ссылки в секундах
        
        Returns:
            str: Временная URL
        """
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MinIO client not initialized"
            )
        
        try:
            url = self.client.presigned_get_object(
                bucket_name=config.MINIO_BUCKET_NAME,
                object_name=object_path,
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate file URL: {str(e)}"
            )
    
    def file_exists(self, object_path: str) -> bool:
        """
        Проверить существование файла в MinIO
        
        Args:
            object_path: Путь к объекту в MinIO
        
        Returns:
            bool: True если файл существует
        """
        if not self.client:
            return False
        
        try:
            self.client.stat_object(config.MINIO_BUCKET_NAME, object_path)
            return True
        except S3Error:
            return False
    
    def list_files(self, prefix: str = "", recursive: bool = True) -> list:
        """
        Получить список файлов в bucket'е
        
        Args:
            prefix: Префикс для фильтрации
            recursive: Рекурсивный обход
        
        Returns:
            list: Список объектов с метаданными
        """
        if not self.client:
            return []
        
        files = []
        try:
            objects = self.client.list_objects(
                config.MINIO_BUCKET_NAME,
                prefix=prefix,
                recursive=recursive
            )
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag
                })
            return files
        except S3Error:
            return []
    
    def get_file_info(self, object_path: str) -> dict:
        """
        Получить информацию о файле
        
        Args:
            object_path: Путь к объекту в MinIO
        
        Returns:
            dict: Информация о файле
        """
        if not self.client:
            return {}
        
        try:
            obj = self.client.stat_object(config.MINIO_BUCKET_NAME, object_path)
            return {
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified,
                "etag": obj.etag,
                "content_type": obj.content_type
            }
        except S3Error:
            return {}
    
    def copy_file(self, source_path: str, dest_path: str) -> str:
        """
        Скопировать файл внутри bucket'а
        
        Args:
            source_path: Исходный путь
            dest_path: Путь назначения
        
        Returns:
            str: Путь к новому файлу
        """
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MinIO client not initialized"
            )
        
        try:
            self.client.copy_object(
                bucket_name=config.MINIO_BUCKET_NAME,
                object_name=dest_path,
                source={
                    "bucket": config.MINIO_BUCKET_NAME,
                    "object": source_path
                }
            )
            return dest_path
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to copy file: {str(e)}"
            )
    
    def health_check(self) -> dict:
        """Проверка состояния подключения к MinIO"""
        if not self.client:
            return {"status": "not_initialized"}
        
        try:
            # Пытаемся получить список bucket'ов для проверки соединения
            self.client.list_buckets()
            return {
                "status": "healthy",
                "bucket": config.MINIO_BUCKET_NAME,
                "endpoint": config.MINIO_ENDPOINT
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Создаем глобальный экземпляр клиента
minio_client = MinIOClient()
