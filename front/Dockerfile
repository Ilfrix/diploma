# frontend/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Копируем package.json и package-lock.json
COPY package*.json ./

# Устанавливаем зависимости
RUN npm ci --only=production

# Копируем исходный код
COPY . .

# Сборка приложения (если есть)
RUN npm run build

# Второй этап: запуск
FROM node:18-alpine

WORKDIR /app

# Копируем собранное приложение
COPY --from=builder /app/build ./build
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules ./node_modules

# Устанавливаем serve для запуска статики
RUN npm install -g serve

EXPOSE 3000

CMD ["serve", "-s", "build", "-l", "3000"]
