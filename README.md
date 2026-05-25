# Banking CDC Pipeline - Learning Guide

- **CDC Basics**: How database changes become events in real-time
- **Debezium**: Industry-standard CDC tool for capturing database changes
- **Kafka**: Event streaming platform used in 80% of Fortune 100 companies
- **Fintech Patterns**: Transaction tracking, audit trails, and data consistency

## Architecture Overview

```
PostgreSQL (Banking DB)
    ↓ WAL (Write-Ahead Log)
Debezium Connector
    ↓ Captures changes
Kafka Topics (Event Stream)
    ↓ Streams events
Your Applications (Consumers)
```

### Components Explained

1. **PostgreSQL** - Source database with banking data (accounts, transactions, transfers)
2. **Debezium** - CDC engine that reads PostgreSQL's Write-Ahead Log (WAL)
3. **Kafka** - Distributed event streaming platform
4. **Zookeeper** - Coordinates Kafka brokers (legacy, being phased out)
5. **Kafka Connect** - Framework that runs Debezium connectors
6. **Debezium UI** - Web interface to manage CDC connectors (http://localhost:8080)
7. **Kafka UI** - Visualize topics and messages (http://localhost:8090)

## Quick Start

### Step 1: Start the Pipeline

Open PowerShell/CMD in the project directory:

```bash
docker-compose up -d
```

Wait ~60 seconds for all services to start. Check status:

```bash
docker-compose ps
```

All services should be "Up" or "healthy".

### Step 2: Verify PostgreSQL

Check that the database initialized correctly:

```bash
docker exec -it banking-postgres psql -U bankuser -d bankingdb -c "SELECT COUNT(*) FROM accounts;"
```

You should see 5 accounts.

### Step 3: Register Debezium Connector

This tells Debezium to start capturing changes from PostgreSQL:

```bash
curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d @debezium-connector-config.json
```

Verify connector is running:

```bash
curl http://localhost:8083/connectors/banking-postgres-connector/status
```

You should see `"state": "RUNNING"`.

### Step 4: View CDC Topics

Open Kafka UI in browser: http://localhost:8090

You should see these topics created automatically:
- `banking.public.accounts` - Account changes
- `banking.public.transactions` - Transaction changes  
- `banking.public.transfers` - Transfer changes

Click on any topic to see the initial snapshot of data.

### Step 5: Generate Live Transactions

Install Python dependencies:

```bash
pip install psycopg2-binary
```

Run the transaction simulator:

```bash
python simulate-banking-transactions.py 20 3
```

This creates 20 random banking operations with 3-second delays.

### Step 6: Watch CDC in Action

In Kafka UI (http://localhost:8090):
1. Click on `banking.public.transactions` topic
2. Click "Messages" tab
3. Set "Seek Type" to "Live" or "Newest"
4. Watch messages appear in real-time as transactions occur!

## Understanding CDC Events

### Event Structure

Each CDC event contains:

```json
{
  "before": null,  // Old values (null for INSERT)
  "after": {       // New values
    "account_id": "uuid-here",
    "balance": 15000.00,
    "customer_name": "Alice Johnson"
  },
  "op": "c",       // Operation: c=create, u=update, d=delete, r=read(snapshot)
  "ts_ms": 1234567890,  // Timestamp in milliseconds
  "db": "bankingdb",
  "table": "accounts"
}
```

### Try This: Update an Account

Open another terminal and run:

```bash
docker exec -it banking-postgres psql -U bankuser -d bankingdb
```

Then execute:

```sql
UPDATE accounts SET balance = balance + 1000 WHERE account_number = 'ACC-2024-001';
```

Check Kafka UI - you'll see an UPDATE event with:
- `before`: old balance
- `after`: new balance
- `op`: "u"

## Key CDC Concepts

### 1. Write-Ahead Log (WAL)

PostgreSQL writes all changes to WAL before applying them. Debezium reads this log without impacting database performance.

**Why it matters in Fintech**: Non-invasive monitoring means zero performance impact on critical banking operations.

### 2. Exactly-Once Semantics

Kafka guarantees each change is captured exactly once - no duplicates, no missing events.

**Why it matters in Fintech**: A $1000 transfer must be captured exactly once, not twice or never.

### 3. Snapshot vs. Streaming

- **Snapshot**: Initial full copy of tables when connector starts
- **Streaming**: Ongoing capture of changes

Our config uses `"snapshot.mode": "initial"` to get existing data, then streams changes.

### 4. Topic Naming

Topics follow pattern: `{server.name}.{schema}.{table}`
- `banking.public.accounts`
- `banking.public.transactions`

### 5. Message Ordering

Kafka guarantees order **within a partition**. Changes to the same record (same key) stay ordered.

## Experiments to Try

### Experiment 1: Track Balance Changes

Run this in PostgreSQL:

```sql
UPDATE accounts SET balance = 99999.99 WHERE account_number = 'ACC-2024-001';
UPDATE accounts SET balance = 50000.00 WHERE account_number = 'ACC-2024-001';
UPDATE accounts SET balance = 75000.00 WHERE account_number = 'ACC-2024-001';
```

In Kafka UI, you'll see 3 UPDATE events in order, each with before/after values.

### Experiment 2: Simulate Failed Transfer

```sql
INSERT INTO transfers (from_account_id, to_account_id, amount, transfer_type, status, initiated_at)
SELECT 
    (SELECT account_id FROM accounts WHERE account_number = 'ACC-2024-001'),
    (SELECT account_id FROM accounts WHERE account_number = 'ACC-2024-002'),
    5000.00,
    'INTERNAL',
    'PENDING',
    CURRENT_TIMESTAMP;

-- Simulate failure
UPDATE transfers SET status = 'FAILED', failure_reason = 'Insufficient funds' WHERE status = 'PENDING';
```

Watch the transfer lifecycle in Kafka: PENDING → FAILED.

### Experiment 3: Account Suspension

```sql
UPDATE accounts SET status = 'SUSPENDED' WHERE account_number = 'ACC-2024-003';
```

See the status change event. Downstream systems can react (freeze transactions, notify customer, etc.).

## Monitoring & Debugging

### Check Connector Health

```bash
curl http://localhost:8083/connectors/banking-postgres-connector/status | python -m json.tool
```

### View Connector Logs

```bash
docker logs banking-kafka-connect -f
```

### Check Kafka Topic Lag

In Kafka UI → Topics → Click any topic → "Consumer Groups" tab

### PostgreSQL Replication Slot

See what Debezium is tracking:

```sql
SELECT * FROM pg_replication_slots;
```

## Planned Extensions

### Level 2: Add Schema Registry
- Avro encoding for efficient serialization
- Schema versioning for backwards compatibility
- Required for production fintech systems

### Level 3: Add Stream Processing
- KSQLDB for real-time transformations
- Kafka Streams for fraud detection
- Aggregate daily transaction volumes

### Level 4: Add Sink Connectors
- Write to Elasticsearch for search
- Write to data warehouse (BigQuery, Snowflake)
- Write to MongoDB for analytics


## Fintech Best Practices

### 1. Audit Trails
Every change is captured with timestamp and operation type. This meets regulatory requirements.

### 2. Data Lineage
You can trace any account balance back through all transactions that affected it.

### 3. Event-Driven Architecture
Downstream systems react to changes without polling the database:
- Fraud detection system watches for suspicious patterns
- Notification service sends alerts on large withdrawals
- Analytics system updates dashboards in real-time

### 4. Database Performance
CDC reads from WAL, not production tables. Zero query overhead on OLTP database.

### 5. Temporal Queries
With all changes in Kafka, you can answer "what was this account's balance at 2 PM yesterday?"


**Built with**: Debezium 2.5, Kafka 7.5, PostgreSQL 15
