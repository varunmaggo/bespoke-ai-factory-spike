# Build context: fintech/payment-gateway/ — builds and runs the MODERN module.
# The legacy module is the pre-migration reference and is not containerised.

# ── Stage 1: build ───────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /build
COPY modern/pom.xml .
COPY modern/src ./src

RUN apk add --no-cache maven && \
    mvn -q package -DskipTests

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine

LABEL maintainer="Payments Platform"
LABEL description="Modern payment gateway (fintech-java-spring2-to-spring3 output)"

WORKDIR /app

# Non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# OTel Java agent for automatic instrumentation (traces, metrics)
ADD --chown=appuser:appgroup \
    https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar \
    /app/opentelemetry-javaagent.jar

COPY --from=builder /build/target/payment-gateway-modern-*.jar app.jar

USER appuser

EXPOSE 9081

ENV JAVA_OPTS="-javaagent:/app/opentelemetry-javaagent.jar \
    -Dotel.service.name=payment-gateway \
    -Dotel.exporter.otlp.endpoint=http://otel-collector:4317 \
    -Dspring.threads.virtual.enabled=true"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD wget -qO- http://localhost:9081/actuator/health || exit 1
