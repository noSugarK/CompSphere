# compsphere-web 构建镜像：产出 dist/ 供 nginx 容器挂载/拷贝
# 两阶段：builder 编译 → 最终镜像仅含 nginx + 静态文件
FROM node:22-alpine AS builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # 产出 /build/dist

FROM nginx:1.27-alpine
COPY --from=builder /build/dist /usr/share/nginx/html
# SPA 路由与 API 反代规则在 docker/nginx/nginx.conf（挂载于外层 nginx 容器）；
# 本镜像内兜底配置：
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location / { try_files $uri $uri/ /index.html; }\n}\n' \
    > /etc/nginx/conf.d/default.conf
EXPOSE 80
