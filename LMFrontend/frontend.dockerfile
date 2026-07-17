# 第一階段：編譯打包環境
FROM node:20 AS build
WORKDIR /app

COPY package*.json ./

# 💡 修正：使用官方最標準的 npm 鏡像節點伺服器網址 (registry.npmmirror.com)
RUN npm config set registry https://registry.npmmirror.com && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm install

COPY . .
RUN npm run build

# 第二階段：Nginx 網頁伺服器環境
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# 🔀 反向代理設定：讓瀏覽器不管從哪台電腦連進來，都用同一個 origin 打 /api，
# 由 nginx 內部轉發給 C# 後端(Docker 內部網路 service name)，不用再寫死 127.0.0.1
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

