# Build context is services/ to match the Python services' Dockerfiles.
FROM node:22-alpine AS build

WORKDIR /app
COPY gateway/package.json gateway/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY gateway/tsconfig.json ./
COPY gateway/src ./src
RUN npm run build

FROM node:22-alpine

ENV NODE_ENV=production
WORKDIR /app
COPY gateway/package.json gateway/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY --from=build /app/dist ./dist

USER node
CMD ["node", "dist/index.js"]
