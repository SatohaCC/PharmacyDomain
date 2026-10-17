FROM node:24-alpine AS build
WORKDIR /frontend
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
ARG VITE_OIDC_AUTHORITY
ARG VITE_OIDC_CLIENT_ID
ARG VITE_OIDC_SCOPE="openid profile"
ENV VITE_OIDC_AUTHORITY=$VITE_OIDC_AUTHORITY VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID VITE_OIDC_SCOPE=$VITE_OIDC_SCOPE
RUN pnpm build
FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html
EXPOSE 80
