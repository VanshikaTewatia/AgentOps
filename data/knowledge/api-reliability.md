# Microservice API Reliability & Resilience Patterns

## 1. Timeout, Retry & Exponential Backoff Strategies
- **Client Timeouts**: Always set explicit socket connection (e.g. 500ms) and read timeouts (e.g. 2000ms) on all outbound HTTP / RPC clients.
- **Idempotency**: Only retry idempotent operations (GET, PUT, DELETE, or POST with `Idempotency-Key` header). Never blindly retry non-idempotent credit card debits.
- **Exponential Backoff with Jitter**: Avoid retry storms by applying randomized exponential backoff:
  `sleep_time = min(max_backoff, base_backoff * (2 ** attempt)) + random_jitter`

## 2. Circuit Breaker Configuration
- **Failure Rate Threshold**: 50% errors over a 10-second rolling window triggers state transition from `CLOSED` to `OPEN`.
- **Wait Duration in Open State**: 5 seconds before entering `HALF_OPEN` state.
- **Permitted Calls in Half-Open**: 5 test probes to verify downstream health before closing circuit.
