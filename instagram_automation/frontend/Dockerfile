# ---------------------------------------------------------------------------
# Instagram_Business — frontend (React + Vite, served by nginx)
# ---------------------------------------------------------------------------
# Stage 1: build the static bundle.
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve the bundle and reverse-proxy /api and /cdn to the backend.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
