# Stage 1: build the static bundle.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve it with nginx.
# The API base URL (http://localhost:8000) is fixed in src/api/client.ts and
# is resolved by the browser, not inside this container -- no build arg needed.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
