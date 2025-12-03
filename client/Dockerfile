# Build stage
FROM node:20-alpine as build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build arg for API URL (can be overridden at build time)
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# Build the app - API will be proxied via nginx
RUN npm run build

# Production stage - nginx for serving static files and proxying API
FROM nginx:alpine

# Copy built files to nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration (handles routing /api to backend)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
