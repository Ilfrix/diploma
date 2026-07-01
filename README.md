# Интеллектуальная информационная система распознавания графических объектов на основе нейросетевых моделей

## Назначение
Добавление новых объектов мебели, их хранение и поиск визуально похожих элементов. Поиск позволяет гибко настраивать параметры:
- Минимальный порог схожести;
- Максимальное количество товаров в выдаче;
- Цвет искомого объекта.

## Стек
Python, FastAPI, React, Torch, Ultralytics YOLO, Timm, Trion Inference Server, Kafka, MiniO, Milvus

## Модели
- Ultralytics YOLOv8n - дообученная на датасете мебели, единственный класс bed;
- EfficientNetV2m, обученная авторами на ImageNet-21k. В этом проекте никак не изменялась.

## Настройки репозитория
Используется pre-commit с настроенными линтерами через ruff, mypy проверками. Настрое CI через GitHub Actions на проверку кода линтерами и на тестах.

## Данные
Использовался датасет диванов и кроватей (bed) с Kaggle https://www.kaggle.com/datasets/oortdatahub/furniture-dataset-for-multi-angle-ai-training?resource=download&select=Bed+Dataset


## Запуск
```
sudo docker-compose up
```
