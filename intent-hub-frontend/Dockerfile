ARG BASE_IMAGE=node:20-alpine
ARG NGINX_BASE=nginx:alpine

FROM ${BASE_IMAGE} AS builder

ARG NPM_REGISTRY

WORKDIR /app

COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    if [ -n "$NPM_REGISTRY" ]; then npm config set registry $NPM_REGISTRY; fi && \
    npm install

COPY . .
RUN npm run build

FROM ${NGINX_BASE}

# 复制构建好的静态文件到 nginx 的 html 目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 官方 nginx 入口脚本会在启动时将环境变量注入 default.conf。
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]
