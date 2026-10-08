# Apache Kafka Cluster Operations & Troubleshooting Guide

## 1. Consumer Group Lag & Partition Imbalance
**Symptoms:**
- Consumer lag steadily increasing on `kafka_consumergroup_lag` metrics.
- Message processing delays in event-driven microservices.

**Diagnostic Commands:**
```bash
# Describe consumer group state and lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group payment-ledger-consumer
```

**Mitigation Steps:**
- Check for slow processing or downstream database lock contention in consumer workers.
- Increase consumer instances up to the total number of topic partitions.
- If individual partitions are disproportionately large, inspect message key distribution for hotspotting.

## 2. Under-Replicated Partitions (URP)
**Root Causes:**
- Broker disk saturation or network partition.
- JVM Garbage Collection pauses causing Zookeeper/KRaft session expiration.

**Remediation:**
- Check broker disk utilization (`df -h`). If disk > 85%, clean old log segments or adjust `retention.ms`.
- Trigger replica reassignment if a specific broker underwent hardware failure.
