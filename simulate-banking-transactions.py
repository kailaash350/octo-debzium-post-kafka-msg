#!/usr/bin/env python3
"""
Banking Transaction Simulator
Simulates realistic banking activities to test CDC pipeline
"""

import psycopg2
import time
import random
from decimal import Decimal
from datetime import datetime
import sys

# Force UTF-8 encoding for stdout on Windows to prevent UnicodeEncodeError with emojis
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


# Database connection config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bankingdb',
    'user': 'bankuser',
    'password': 'bankpass'
}

def get_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG)

def get_random_account(cursor):
    """Get a random active account"""
    cursor.execute("""
        SELECT account_id, account_number, balance 
        FROM accounts 
        WHERE status = 'ACTIVE' 
        ORDER BY RANDOM() 
        LIMIT 1
    """)
    return cursor.fetchone()

def simulate_deposit(cursor, account_id, amount):
    """Simulate a deposit transaction"""
    cursor.execute("""
        UPDATE accounts 
        SET balance = balance + %s 
        WHERE account_id = %s 
        RETURNING balance
    """, (amount, account_id))
    
    new_balance = cursor.fetchone()[0]
    
    cursor.execute("""
        INSERT INTO transactions (account_id, transaction_type, amount, balance_after, description, status, processed_at)
        VALUES (%s, 'DEPOSIT', %s, %s, %s, 'COMPLETED', CURRENT_TIMESTAMP)
        RETURNING transaction_id
    """, (account_id, amount, new_balance, f'Deposit of ${amount}'))
    
    return cursor.fetchone()[0]

def simulate_withdrawal(cursor, account_id, balance, amount):
    """Simulate a withdrawal transaction"""
    if balance < amount:
        print(f"   ⚠️  Insufficient funds. Balance: ${balance}, Withdrawal: ${amount}")
        return None
    
    cursor.execute("""
        UPDATE accounts 
        SET balance = balance - %s 
        WHERE account_id = %s 
        RETURNING balance
    """, (amount, account_id))
    
    new_balance = cursor.fetchone()[0]
    
    cursor.execute("""
        INSERT INTO transactions (account_id, transaction_type, amount, balance_after, description, status, processed_at)
        VALUES (%s, 'WITHDRAWAL', %s, %s, %s, 'COMPLETED', CURRENT_TIMESTAMP)
        RETURNING transaction_id
    """, (account_id, amount, new_balance, f'Withdrawal of ${amount}'))
    
    return cursor.fetchone()[0]

def simulate_transfer(cursor):
    """Simulate a transfer between two accounts"""
    # Get two different accounts
    cursor.execute("""
        SELECT account_id, account_number, balance 
        FROM accounts 
        WHERE status = 'ACTIVE' 
        ORDER BY RANDOM() 
        LIMIT 2
    """)
    accounts = cursor.fetchall()
    
    if len(accounts) < 2:
        print("   ⚠️  Not enough accounts for transfer")
        return None
    
    from_account = accounts[0]
    to_account = accounts[1]
    from_id, from_number, from_balance = from_account
    to_id, to_number, to_balance = to_account
    
    # Random transfer amount (max 20% of balance or $1000)
    max_transfer = min(float(from_balance) * 0.2, 1000)
    if max_transfer < 10:
        print(f"   ⚠️  Insufficient funds for transfer. Balance: ${from_balance}")
        return None
    
    amount = round(random.uniform(10, max_transfer), 2)
    
    # Create transfer record
    cursor.execute("""
        INSERT INTO transfers (from_account_id, to_account_id, amount, transfer_type, status, initiated_at)
        VALUES (%s, %s, %s, 'INTERNAL', 'PENDING', CURRENT_TIMESTAMP)
        RETURNING transfer_id
    """, (from_id, to_id, amount))
    
    transfer_id = cursor.fetchone()[0]
    
    # Update transfer to IN_PROGRESS
    cursor.execute("""
        UPDATE transfers 
        SET status = 'IN_PROGRESS' 
        WHERE transfer_id = %s
    """, (transfer_id,))
    
    # Debit from source account
    cursor.execute("""
        UPDATE accounts 
        SET balance = balance - %s 
        WHERE account_id = %s 
        RETURNING balance
    """, (amount, from_id))
    from_new_balance = cursor.fetchone()[0]
    
    cursor.execute("""
        INSERT INTO transactions (account_id, transaction_type, amount, balance_after, description, reference_id, status, processed_at)
        VALUES (%s, 'TRANSFER_OUT', %s, %s, %s, %s, 'COMPLETED', CURRENT_TIMESTAMP)
    """, (from_id, amount, from_new_balance, f'Transfer to {to_number}', str(transfer_id)))
    
    # Credit to destination account
    cursor.execute("""
        UPDATE accounts 
        SET balance = balance + %s 
        WHERE account_id = %s 
        RETURNING balance
    """, (amount, to_id))
    to_new_balance = cursor.fetchone()[0]
    
    cursor.execute("""
        INSERT INTO transactions (account_id, transaction_type, amount, balance_after, description, reference_id, status, processed_at)
        VALUES (%s, 'TRANSFER_IN', %s, %s, %s, %s, 'COMPLETED', CURRENT_TIMESTAMP)
    """, (to_id, amount, to_new_balance, f'Transfer from {from_number}', str(transfer_id)))
    
    # Complete transfer
    cursor.execute("""
        UPDATE transfers 
        SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP 
        WHERE transfer_id = %s
    """, (transfer_id,))
    
    return transfer_id, from_number, to_number, amount

def run_simulation(num_operations=10, delay=2):
    """Run banking simulation"""
    print("🏦 Banking Transaction Simulator")
    print("=" * 60)
    print(f"Running {num_operations} random operations with {delay}s delay\n")
    
    conn = get_connection()
    
    operations = ['deposit', 'withdrawal', 'transfer']
    
    for i in range(num_operations):
        cursor = conn.cursor()
        
        try:
            operation = random.choice(operations)
            
            if operation == 'deposit':
                account = get_random_account(cursor)
                amount = round(random.uniform(50, 5000), 2)
                tx_id = simulate_deposit(cursor, account[0], amount)
                print(f"✅ [{i+1}] DEPOSIT: ${amount:,.2f} to {account[1]} (TX: {tx_id})")
                
            elif operation == 'withdrawal':
                account = get_random_account(cursor)
                amount = round(random.uniform(20, 500), 2)
                tx_id = simulate_withdrawal(cursor, account[0], account[2], amount)
                if tx_id:
                    print(f"✅ [{i+1}] WITHDRAWAL: ${amount:,.2f} from {account[1]} (TX: {tx_id})")
                
            elif operation == 'transfer':
                result = simulate_transfer(cursor)
                if result:
                    transfer_id, from_acc, to_acc, amount = result
                    print(f"✅ [{i+1}] TRANSFER: ${amount:,.2f} from {from_acc} to {to_acc} (ID: {transfer_id})")
            
            conn.commit()
            cursor.close()
            
            # Wait before next operation
            if i < num_operations - 1:
                time.sleep(delay)
                
        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()
            cursor.close()
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ Simulation completed!")

if __name__ == "__main__":
    import sys
    
    num_ops = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 2
    
    run_simulation(num_ops, delay)