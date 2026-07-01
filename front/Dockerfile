FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./

# Установка зависимостей
RUN npm ci --only=production

COPY . .

RUN npm run build

# ----
FROM node:18-alpine

WORKDIR /app

COPY --from=builder /app/build ./build
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules ./node_modules

# Установка serve для запуска статики
RUN npm install -g serve

EXPOSE 3000

CMD ["serve", "-s", "build", "-l", "3000"]
