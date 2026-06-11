FROM node:20-alpine

WORKDIR /app
RUN npm init -y && npm install mongodb-mcp-server@1.10.0

EXPOSE 8080
CMD ["npx", "mongodb-mcp-server", "--transport", "http", "--httpPort", "8080", "--httpHost", "0.0.0.0", "--readOnly"]
