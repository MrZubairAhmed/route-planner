FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY RoutePlanner.slnx ./
COPY src/RoutePlanner.Core/RoutePlanner.Core.csproj src/RoutePlanner.Core/
COPY src/RoutePlanner.Web/RoutePlanner.Web.csproj src/RoutePlanner.Web/
RUN dotnet restore src/RoutePlanner.Web/RoutePlanner.Web.csproj
COPY src/ src/
RUN dotnet publish src/RoutePlanner.Web/RoutePlanner.Web.csproj -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
ENV ASPNETCORE_URLS=http://0.0.0.0:8080
ENV PORT=8080
EXPOSE 8080
COPY --from=build /app/publish .
RUN mkdir -p /app/web_jobs
ENTRYPOINT ["dotnet", "RoutePlanner.Web.dll"]
