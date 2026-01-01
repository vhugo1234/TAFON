# frontend/Dockerfile

# 1. Fase de Build
FROM node:18-alpine as builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
# A flag --mode production é crucial para que o Vite use as variáveis VITE_... corretas
RUN npm run build -- --mode production 

# 2. Fase Final (Servindo estaticamente com Nginx)
FROM nginx:alpine
# Copia os arquivos estáticos gerados pelo Vite para o diretório de serviço do Nginx
COPY --from=builder /app/dist /usr/share/nginx/html
# Copia uma configuração customizada do Nginx (opcional, mas recomendado)
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Comando padrão do Nginx para iniciar
CMD ["nginx", "-g", "daemon off;"]