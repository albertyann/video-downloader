# Frontend Dockerfile for Vue 3 + Vite
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build args for API configuration
ARG VITE_API_BASE_URL=http://localhost:8000/api
ARG VITE_WS_BASE_URL=ws://localhost:8000/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_WS_BASE_URL=${VITE_WS_BASE_URL}

# Build for production
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

# Copy built files to nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
