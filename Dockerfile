# ChickHub Server — Node.js + better-sqlite3
FROM node:20-alpine AS builder
WORKDIR /app
COPY server/package*.json ./
RUN npm ci --only=production

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY server/ .

EXPOSE 3000
CMD ["node", "index.js"]
