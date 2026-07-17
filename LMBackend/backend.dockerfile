FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /app
EXPOSE 5165
USER root
# 關鍵核心修正：補上 Linux 系統缺少的 Kerberos 安全驗證與網路元件
RUN apt-get update && apt-get install -y \
    libgssapi-krb5-2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY *.csproj ./
RUN dotnet restore

COPY . ./
RUN dotnet publish -c Release -o out

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /app/out .

ENV ASPNETCORE_URLS=http://+:5165
EXPOSE 5165
ENTRYPOINT ["dotnet", "LMBackend.dll"]

USER root
RUN apt-get update && apt-get install -y libgssapi-krb5-2 && rm -rf /var/lib/apt/lists/*
