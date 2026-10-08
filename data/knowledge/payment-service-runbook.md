# Payment Service Operational Runbook

## Service Overview
The `payment-service` handles payment authorization, capture, refunds, and webhook event processing for e-commerce transactions. It operates as a critical tier-1 microservice with an SLA of 99.99% availability and p99 latency target of < 250ms.

## Architecture & Dependencies
- **Primary Database**: PostgreSQL 16 cluster with primary-replica configuration.
- **Connection Pooler**: HikariCP connection pool with a maximum size of 30 connections per pod.
- **Caching Layer**: Redis cluster for idempotent transaction tokens and rate limiting.
- **Message Broker**: Apache Kafka topic `payment.transactions.v1` for downstream ledger notifications.
- **External Gateways**: Stripe and Adyen payment gateway APIs via outbound HTTPS.

## Common Alerts & Remediation

### 1. Database Connection Pool Exhaustion (HikariPool-1 - Connection is not available)
**Symptoms:**
- High rate of HTTP 500 responses with `HikariPool - ConnectionTimeoutException`.
- Service error rate spiking above 5%.
- Elevated request queue length in pod metrics.

**Diagnosis Steps:**
1. Check active database connection metrics via `/api/v1/services/payment-service/metrics`.
2. Inspect long-running PostgreSQL queries:
   `SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;`
3. Check for unindexed queries on the `payment_transactions` table during checkout spikes.
4. Verify whether transaction timeout is set (`spring.datasource.hikari.leak-detection-threshold=2000ms`).

**Remediation:**
- Terminate lingering idle in transaction queries blocking locks:
  `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND query_start < now() - interval '5 minutes';`
- Scale the payment-service replica deployment or adjust `maximum-pool-size` dynamically.
- If upstream connection pooler (PgBouncer) is saturated, increase `max_client_conn` and verify client transaction cleanup.

### 2. External Payment Gateway Timeouts (HTTP 504)
**Symptoms:**
- Gateway latency exceeds 2.5s on `/v1/charges` requests.
- Circuit breaker state transitions to `OPEN`.

**Remediation:**
- Validate third-party status pages (Stripe / Adyen).
- Enable secondary gateway fallback route by flipping feature flag `PAYMENT_GATEWAY_FALLBACK_ENABLED=true`.

### 3. Kafka Producer Failures
**Symptoms:**
- Error logs reporting `org.apache.kafka.common.errors.TimeoutException: Topic payment.transactions.v1 not present in metadata after 60000 ms`.
- Unsent transaction notifications accumulating in internal memory buffer.

**Remediation:**
- Check Kafka broker disk space and partition leader rebalancing.
- Verify consumer group lag on `payment-ledger-consumer`.
