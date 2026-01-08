# frontend/Dockerfile (build-time VITE var)
FROM node:18-alpine as builder
WORKDIR /app

# Build args / env para Vite
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# importante usar --mode production (ou definir NODE_ENV=production)
RUN npm run build -- --mode production

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# substitua default.conf por um nginx.conf com SPA fallback (exemplo abaixo)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]