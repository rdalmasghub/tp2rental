# Build stage
FROM gradle:8.14-jdk17@sha256:4adc63f5657468850c2012dc27efba47a25a61fab5a4993f4ff3bf8f295a751c AS builder
WORKDIR /app
COPY . .
RUN gradle clean build -x test

# Runtime stage
FROM eclipse-temurin:25-jre-jammy@sha256:1c6798886da1ae157e6c751cedb80eacf15d883e651ffe9acdcc534c19f482de
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
