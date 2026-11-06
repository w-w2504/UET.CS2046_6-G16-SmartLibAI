# ==============================================================================
# Dockerfile - Web Frontend Build Service (React + Vite)
# ==============================================================================

FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage copy static files
FROM alpine:3.20

WORKDIR /app
COPY --from=builder /app/dist /app/dist

CMD ["sh", "-c", "echo 'Web assets built successfully'"]

