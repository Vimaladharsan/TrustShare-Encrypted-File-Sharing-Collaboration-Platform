FROM node:20-alpine

WORKDIR /app

# Install packages first (cached unless package files change).
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
