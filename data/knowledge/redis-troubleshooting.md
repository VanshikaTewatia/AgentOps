# Redis In-Memory Cache Troubleshooting Guide

## 1. High Memory Utilization & OOM (Out Of Memory)
**Symptoms:**
- Error: `OOM command not allowed when used memory > 'maxmemory'`.
- Client requests timing out or returning cache misses.

**Diagnostic Commands:**
```bash
redis-cli INFO memory
redis-cli --bigkeys
```

**Remediation:**
- Verify eviction policy (`maxmemory-policy`): recommend `volatile-lru` or `allkeys-lru` for cache workloads.
- Check for unbounded key creation without TTL (Time To Live).
- Scan for big keys consuming excessive memory (> 5MB per key).

## 2. Redis Connection Limits & Latency Spikes
- Check connected clients: `redis-cli INFO clients`.
- Check slow execution log: `redis-cli SLOWLOG GET 25`. Avoid blocking operations like `KEYS *` or huge `SMEMBERS` in production; replace with `SCAN` and `SSCAN`.
