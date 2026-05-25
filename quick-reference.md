# Quick Reference Guide

## 🚀 Common Commands

### Docker Operations

```bash
# Start all services
docker-compose up -d

# View logs for specific service
docker logs banking-kafka-connect -f
docker logs banking-postgres -f
docker logs banking-kafka -f

# Check service status
docker-compose ps

# Stop all services
docker-compose down

# Stop and remove all data
docker-compose down -v

# Restart a specific service
docker-compose restart kafka-connect
```

### Debezium Connector Management

```bash
# Register connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @debezium-connector-config.json

# Check connector status
curl http://localhost:8083/connectors/banking-postgres-connector/status

# List all connectors
curl http://localhost:8083/connectors

# Delete connector
curl -X DELETE http://localhost:8083/connectors/banking-postgres-connector

# Restart connector
curl -X POST http://localhost:8083/connectors/banking-postgres-connector/restart

# Pause connector
curl -X PUT http://localhost:8083/connectors/banking-postgres-connector/pause

# Resume connector
curl -X PUT http://localhost:8083/connectors/banking-postgres-connector/resume
```

### Kafka Commands

```bash
# List topics
docker exec banking-kafka kafka-topics --bootstrap-server localhost:29092 --list

# Describe topic
docker exec banking-kafka kafka-topics --bootstrap-server localhost:29092 \
  --describe --topic banking_connect_configs

# Consume messages from beginning
docker exec banking-kafka kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic banking.public.transactions \
  --from-beginning

# Consume live messages
docker exec banking-kafka kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic banking.public.accounts \
  --property print.timestamp=true

# Delete topic (careful!)
docker exec banking-kafka kafka-topics --bootstrap-server localhost:29092 \
  --delete --topic banking.public.accounts
```

### PostgreSQL Operations

```bash
# Connect to PostgreSQL
docker exec -it banking-postgres psql -U bankuser -d bankingdb

# Run single query
docker exec -it banking-postgres psql -U bankuser -d bankingdb \
  -c "SELECT COUNT(*) FROM transactions;"

# Execute SQL file
docker exec -i banking-postgres psql -U bankuser -d bankingdb < my-script.sql
```

## 📊 Useful SQL Queries

### Banking Analytics

```sql
-- Total balance across all accounts
SELECT 
    COUNT(*) as total_accounts,
    SUM(balance) as total_balance,
    AVG(balance) as avg_balance
FROM accounts
WHERE status = 'ACTIVE';

-- Transactions by type (last 24 hours)
SELECT 
    transaction_type,
    COUNT(*) as count,
    SUM(amount) as total_amount
FROM transactions
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY transaction_type
ORDER BY total_amount DESC;

-- Top accounts by transaction volume
SELECT 
    a.account_number,
    a.customer_name,
    COUNT(t.transaction_id) as tx_count,
    SUM(CASE WHEN t.transaction_type IN ('DEPOSIT', 'TRANSFER_IN') THEN t.amount ELSE 0 END) as total_credits,
    SUM(CASE WHEN t.transaction_type IN ('WITHDRAWAL', 'TRANSFER_OUT') THEN t.amount ELSE 0 END) as total_debits
FROM accounts a
LEFT JOIN transactions t ON a.account_id = t.account_id
GROUP BY a.account_id, a.account_number, a.customer_name
ORDER BY tx_count DESC
LIMIT 10;

-- Recent transfers with details
SELECT 
    t.transfer_id,
    t.status,
    from_acc.account_number as from_account,
    to_acc.account_number as to_account,
    t.amount,
    t.initiated_at,
    t.completed_at
FROM transfers t
JOIN accounts from_acc ON t.from_account_id = from_acc.account_id
JOIN accounts to_acc ON t.to_account_id = to_acc.account_id
ORDER BY t.initiated_at DESC
LIMIT 10;

-- Account balance history (reconstructed from transactions)
SELECT 
    created_at,
    transaction_type,
    amount,
    balance_after,
    description
FROM transactions
WHERE account_id = (SELECT account_id FROM accounts WHERE account_number = 'ACC-2024-001')
ORDER BY created_at DESC
LIMIT 20;
```

### CDC Debugging Queries

```sql
-- Check PostgreSQL WAL settings
SHOW wal_level;
SHOW max_wal_senders;
SHOW max_replication_slots;

-- View active replication slots
SELECT * FROM pg_replication_slots;

-- Check replication lag (should be near 0)
SELECT 
    slot_name,
    confirmed_flush_lsn,
    pg_current_wal_lsn(),
    pg_current_wal_lsn() - confirmed_flush_lsn AS lag_bytes
FROM pg_replication_slots;

-- View WAL sender processes
SELECT * FROM pg_stat_replication;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## 🧪 Testing Scenarios

### Scenario 1: High-Frequency Deposits

```sql
-- Simulate rapid deposits to same account
DO $$
DECLARE
    acc_id UUID := (SELECT account_id FROM accounts WHERE account_number = 'ACC-2024-001');
    i INT;
BEGIN
    FOR i IN 1..50 LOOP
        UPDATE accounts SET balance = balance + 100 WHERE account_id = acc_id;
        INSERT INTO transactions (account_id, transaction_type, amount, balance_after, status, processed_at)
        SELECT acc_id, 'DEPOSIT', 100, balance, 'COMPLETED', CURRENT_TIMESTAMP
        FROM accounts WHERE account_id = acc_id;
        PERFORM pg_sleep(0.1);  -- 100ms between deposits
    END LOOP;
END $$;
```

### Scenario 2: Bulk Transfer Batch

```sql
-- Create multiple simultaneous transfers
INSERT INTO transfers (from_account_id, to_account_id, amount, transfer_type, status, initiated_at)
SELECT 
    (SELECT account_id FROM accounts WHERE account_number = 'ACC-2024-001'),
    (SELECT account_id FROM accounts WHERE account_number = 'ACC-2024-002'),
    random() * 500 + 100,  -- Random amount between 100-600
    'INTERNAL',
    'COMPLETED',
    CURRENT_TIMESTAMP
FROM generate_series(1, 10);
```

### Scenario 3: Account Lifecycle

```sql
-- Create new account
INSERT INTO accounts (account_number, customer_name, account_type, balance, status)
VALUES ('ACC-2024-999', 'Test User', 'CHECKING', 1000.00, 'ACTIVE');

-- Modify account
UPDATE accounts SET balance = 5000.00 WHERE account_number = 'ACC-2024-999';

-- Suspend account
UPDATE accounts SET status = 'SUSPENDED' WHERE account_number = 'ACC-2024-999';

-- Reactivate
UPDATE accounts SET status = 'ACTIVE' WHERE account_number = 'ACC-2024-999';

-- Close account (soft delete via status)
UPDATE accounts SET status = 'CLOSED', balance = 0 WHERE account_number = 'ACC-2024-999';
```

## 🔧 Troubleshooting Commands

### Check Service Health

```bash
# Check if Kafka is ready
docker exec banking-kafka kafka-broker-api-versions --bootstrap-server localhost:29092

# Check if PostgreSQL is accepting connections
docker exec banking-postgres pg_isready -U bankuser

# Check Kafka Connect is running
curl http://localhost:8083/

# List installed connectors plugins
curl http://localhost:8083/connector-plugins
```

### Reset Everything

```bash
# Nuclear option: complete reset
docker-compose down -v
docker system prune -f
docker volume prune -f

# Then restart from scratch
docker-compose up -d
sleep 60
curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d @debezium-connector-config.json
```

### View Connector Configuration

```bash
# Get current connector config
curl http://localhost:8083/connectors/banking-postgres-connector | python -m json.tool
```

## 📈 Performance Monitoring

### Kafka Topic Metrics

```bash
# Get topic offset information
docker exec banking-kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:29092 \
  --topic banking.public.accounts
```

### PostgreSQL Performance

```sql
-- Active queries
SELECT pid, usename, state, query, now() - query_start AS duration
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Cache hit ratio (should be > 95%)
SELECT 
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit) as heap_hit,
    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as cache_hit_ratio
FROM pg_statio_user_tables;
```

## 🌐 Web Interfaces

- **Kafka UI**: http://localhost:8090
- **Debezium UI**: http://localhost:8080
- **Kafka Connect REST API**: http://localhost:8083

## 📱 Python Helper Scripts

### Quick Balance Check

```python
import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, database='bankingdb', user='bankuser', password='bankpass')
cur = conn.cursor()
cur.execute("SELECT account_number, customer_name, balance FROM accounts WHERE status='ACTIVE'")
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]} - ${row[2]:,.2f}")
conn.close()
```

### Count CDC Events

```bash
# Using kafkacat (install separately)
kafkacat -b localhost:9092 -t banking.public.accounts -C -e -q | wc -l
```

