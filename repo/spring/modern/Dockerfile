# ── Stage 1: build ───────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app
COPY pom.xml .
COPY src ./src

RUN apk add --no-cache maven && \
    mvn -q package -DskipTests

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine

LABEL maintainer="AI Factory Team"
LABEL description="Modern Spring Boot 3.x AI Factory service (AWS Transform Custom output)"

WORKDIR /app

# Non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

COPY --from=builder /app/target/ai-factory-modern-*.jar app.jar

# OTel Java agent for automatic instrumentation (traces, metrics)
ADD --chown=appuser:appgroup \
    https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar \
    /app/opentelemetry-javaagent.jar

EXPOSE 8080

ENV JAVA_OPTS="-javaagent:/app/opentelemetry-javaagent.jar \
    -Dotel.service.name=ai-factory-modern \
    -Dotel.exporter.otlp.endpoint=http://otel-collector:4317 \
    -Dspring.threads.virtual.enabled=true"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD wget -qO- http://localhost:8080/api/v1/health || exit 1
