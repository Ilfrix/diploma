from unittest.mock import patch
from app.models import Sample, ProcessStatus, ImageModel, Crop, Vector
from PIL import Image
import numpy as np


class TestSearchRouter:
    
    def test_search_similar_by_sample(self, client, auth_headers, db_session, test_user, mock_minio):
        """Поиск похожих изображений по семплу"""

        # Создаем тестовые данные
        image = ImageModel(
            image_path="test/path.jpg",
            image_hash="hash123",
            mime_type="image/jpeg"
        )
        db_session.add(image)
        db_session.flush()
        
        sample = Sample(
            user_id=test_user.id,
            name="Query Sample",
            image_id=image.id,
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.flush()
        
        crop = Crop(
            image_id=image.id,
            crop_index=0,
            bbox_x1=10, bbox_y1=20, bbox_x2=50, bbox_y2=60,
            class_name="object",
            confidence=0.95,
            crop_path="crop/path.jpg"
        )
        db_session.add(crop)
        db_session.flush()
        
        vector = Vector(
            crop_id=crop.id,
            milvus_id="test_milvus_id"
        )
        db_session.add(vector)
        db_session.commit()
        
        # Мокаем векторную БД
        with patch('app.routers.search.vector_db') as mock_vector_db:
            mock_vector_db.get_vector.return_value = np.random.rand(512).tolist()
            mock_vector_db.search_similar.return_value = [
                ("other_milvus_id", 0.85, {"sample_id": "other_sample_id"})
            ]
            
            response = client.get(
                f"/api/samples/{sample.id}/similar?limit=5&threshold=0.7",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["query_sample_id"] == sample.id
            assert "similar_images" in data
    
    def test_get_sample_crops(self, client, auth_headers, db_session, test_user, mock_minio):
        """Получение кропов семпла"""
        
        image = ImageModel(
            image_path="test/path.jpg",
            image_hash="hash123",
            mime_type="image/jpeg"
        )
        db_session.add(image)
        db_session.flush()
        
        sample = Sample(
            user_id=test_user.id,
            name="Sample with Crops",
            image_id=image.id,
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.flush()
        
        crops = [
            Crop(
                image_id=image.id,
                crop_index=i,
                bbox_x1=10*i, bbox_y1=10*i, bbox_x2=50+10*i, bbox_y2=50+10*i,
                class_name=f"object_{i}",
                confidence=0.9,
                crop_path=f"crop_{i}.jpg"
            )
            for i in range(3)
        ]
        db_session.add_all(crops)
        db_session.commit()
        with patch('app.routers.samples.minio_client', mock_minio):
            response = client.get(
                f"/api/samples/{sample.id}/crops",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("bbox" in crop for crop in data['crops'])
    
    def test_search_similar_by_image_upload(self, client, auth_headers, test_image_bytes):
        """Поиск по загруженному изображению"""
        with patch('app.routers.search.process_image_with_crops') as mock_process:
            mock_process.return_value = (
                # [np.random.rand(512).tolist()],  # embeddings
                [Image.open('/home/polyanskii/Pictures/projects_picture/sofa_1.jpeg')],
                [],  # detections
                []   # crops_data
            )
            
            with patch('app.routers.search.vector_db') as mock_vector_db:
                mock_vector_db.search_similar.return_value = [
                    ("vec_id", 0.85, {"sample_id": "sample123"})
                ]
                
                files = {
                    "image": ("test.jpg", test_image_bytes, "image/jpeg")
                }
                
                response = client.post(
                    "/api/search/similar?limit=5&threshold=0.7",
                    headers=auth_headers,
                    files=files
                )
                
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
    
    def test_get_sample_vectors(self, client, auth_headers, db_session, test_user):
        """Получение информации о векторах семпла"""
        
        image = ImageModel(
            image_path="test/path.jpg",
            image_hash="hash123",
            mime_type="image/jpeg"
        )
        db_session.add(image)
        db_session.flush()
        
        sample = Sample(
            user_id=test_user.id,
            name="Sample with Vectors",
            image_id=image.id,
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.flush()
        
        crop = Crop(
            image_id=image.id,
            crop_index=0,
            bbox_x1=10, bbox_y1=20, bbox_x2=50, bbox_y2=60,
            class_name="object",
            confidence=0.95,
            crop_path="crop.jpg"
        )
        db_session.add(crop)
        db_session.flush()
        
        vector = Vector(
            crop_id=crop.id,
            milvus_id="milvus_123"
        )
        db_session.add(vector)
        db_session.commit()
        
        response = client.get(
            f"/api/samples/{sample.id}/vectors",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["vectors"][0]["milvus_id"] == "milvus_123"
