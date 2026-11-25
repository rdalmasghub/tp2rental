# Build stage
FROM gradle:8.14-jdk17@sha256:4adc63f5657468850c2012dc27efba47a25a61fab5a4993f4ff3bf8f295a751c AS builder
WORKDIR /app
COPY . .
RUN gradle clean build -x test

# Runtime stage
FROM eclipse-temurin:17-jre-jammy@sha256:c6a5dd70fb24f4e07ef88cbda8efb613a5a649a1af071a41de8eaabd1ee6b5da
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
