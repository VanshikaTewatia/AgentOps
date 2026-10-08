# Database Troubleshooting & Performance Guide

## PostgreSQL Troubleshooting Overview
This guide provides systematic runbooks for diagnosing and mitigating database performance degradations, connection saturation, lock contention, and replication delays.

## 1. Connection Pool & Exhaustion Diagnosis
When application services report `connection pool exhausted` or `FATAL: remaining connection slots are reserved for non-replication superuser connections`:

### Immediate Checks:
1. **Total Active vs Idle Connections**:
   ```sql
   SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
   ```
2. **Connections by Database and User**:
   ```sql
   SELECT datname, usename, client_addr, count(*) 
   FROM pg_stat_activity 
   GROUP BY datname, usename, client_addr 
   ORDER BY count(*) DESC;
   ```
3. **Identify Connections Stuck in `idle in transaction`**:
   ```sql
   SELECT pid, now() - state_change AS idle_duration, query 
   FROM pg_stat_activity 
   WHERE state = 'idle in transaction' 
   ORDER BY idle_duration DESC;
   ```

### Resolution Steps:
- If a specific application pod leaked connections, terminate runaway sessions:
  ```sql
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = <PID>;
  ```
- Enforce `idle_in_transaction_session_timeout = '30s'` in PostgreSQL configuration to prevent hung transactions.
- Check PgBouncer connection pool mode: ensure `pool_mode = transaction` is enabled for high-throughput REST APIs instead of `session` mode.

## 2. Lock Contention & Blocked Queries
To find blocked queries waiting on table or row locks:
```sql
SELECT
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS blocking_statement
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

## 3. High CPU / Slow Query Optimization
- Check `pg_stat_statements` for the top 5 highest mean execution time queries.
- Look for `Seq Scan` on large tables missing composite indexes.
- Run `EXPLAIN (ANALYZE, BUFFERS)` on slow queries before modifying indexing strategies.
