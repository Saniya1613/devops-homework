# AWS DynamoDB & RDS – Databases

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

---

# Part A – Amazon DynamoDB

## What is DynamoDB? (NoSQL)
A fully managed, **serverless NoSQL key-value and document database**. No servers, no patching, automatic scaling,
single-digit millisecond latency at any scale, data replicated across 3 AZs. "NoSQL" means: **no fixed schema** (apart
from the key), no joins; you design the table around your **access patterns**.
Capacity modes: **On-Demand** (pay per request) or **Provisioned** (set RCU/WCU, optionally auto-scaled).

## Tables, items, attributes
| DynamoDB | Relational analogy | Notes |
|---|---|---|
| **Table** | table | collection of items; has a primary key definition |
| **Item** | row | max 400 KB; items in one table can have different attributes |
| **Attribute** | column | typed: `S` string, `N` number, `B` binary, `BOOL`, `NULL`, `L` list, `M` map, `SS`/`NS`/`BS` sets |

## Primary key
- **Partition key (hash key)** – required. DynamoDB hashes it to decide which physical partition stores the item.
  Pick a **high-cardinality** value (userId, orderId) so load spreads evenly and avoid "hot partitions".
  With only a partition key, it must be unique per item.
- **Sort key (range key)** – optional. Items with the same partition key are stored together, ordered by the sort key.
  `PK + SK` must be unique. Enables range queries: `begins_with`, `between`, `>`, "latest 10 orders of user X".
- **Secondary indexes:** GSI (different PK/SK, any time) and LSI (same PK, different SK, at creation) for other access patterns.
- `Query` = efficient lookup by key; `Scan` = reads the whole table (avoid on big tables).

## Use cases
- User profiles, sessions, shopping carts, game state & leaderboards.
- IoT / time-series events (deviceId + timestamp).
- Serverless backends (API Gateway + Lambda + DynamoDB).
- High-traffic catalogs, metadata stores, feature flags.
- **Terraform state locking** (`dynamodb_table` in the S3 backend).

## Hands-on demo (LocalStack)
> Run against LocalStack (local AWS emulator) – no AWS account was available.

Table with partition key `StudentId` (string) and sort key `Session` (number):

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/05-dynamodb-rds$ aws --endpoint-url http://localhost:31866 dynamodb create-table --table-name s18-homework --attribute-definitions AttributeName=StudentId,AttributeType=S AttributeName=Session,AttributeType=N --key-schema AttributeName=StudentId,KeyType=HASH AttributeName=Session,KeyType=RANGE --billing-mode PAY_PER_REQUEST --query 'TableDescription.{Name:TableName,Status:TableStatus,Keys:KeySchema}'
{
    "Name": "s18-homework",
    "Status": "ACTIVE",
    "Keys": [
        {
            "AttributeName": "StudentId",
            "KeyType": "HASH"
        },
        {
            "AttributeName": "Session",
            "KeyType": "RANGE"
        }
    ]
}
```

Two items (note item 2 has an extra `Tags` attribute – no fixed schema). Files: [item1.json](./item1.json), [item2.json](./item2.json)

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/05-dynamodb-rds$ aws --endpoint-url http://localhost:31866 dynamodb put-item --table-name s18-homework --item file://item1.json && aws --endpoint-url http://localhost:31866 dynamodb put-item --table-name s18-homework --item file://item2.json && echo 'items written'
items written
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/05-dynamodb-rds$ aws --endpoint-url http://localhost:31866 dynamodb get-item --table-name s18-homework --key '{"StudentId":{"S":"24bcs10246"},"Session":{"N":"18"}}'
{
    "Item": {
        "Status": {
            "S": "Submitted"
        },
        "Topic": {
            "S": "Terraform IaC"
        },
        "StudentId": {
            "S": "24bcs10246"
        },
        "Session": {
            "N": "18"
        }
    }
}
```

Query by partition key with a sort-key condition:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/05-dynamodb-rds$ aws --endpoint-url http://localhost:31866 dynamodb query --table-name s18-homework --key-condition-expression 'StudentId = :s AND #n >= :n' --expression-attribute-names '{"#n":"Session"}' --expression-attribute-values '{":s":{"S":"24bcs10246"},":n":{"N":"19"}}' --query 'Items[].{Session:Session.N,Topic:Topic.S,Status:Status.S}' --output table
-------------------------------------------------
|                     Query                     |
+---------+---------------+---------------------+
| Session |    Status     |        Topic        |
+---------+---------------+---------------------+
|  19     |  In progress  |  Cloud + Terraform  |
+---------+---------------+---------------------+
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/05-dynamodb-rds$ aws --endpoint-url http://localhost:31866 dynamodb scan --table-name s18-homework --query 'Count'
2
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/05-dynamodb-rds$ aws --endpoint-url http://localhost:31866 dynamodb delete-table --table-name s18-homework --query 'TableDescription.TableStatus'
"ACTIVE"
```

**Observation:** `get-item` needs the **full primary key** (partition + sort key); `query` uses the partition key plus a
condition on the sort key and returned only session 19.

---

# Part B – Amazon RDS

## What is RDS? (relational)
**Relational Database Service** – AWS runs a traditional **SQL database** for you (tables with fixed schema, joins,
transactions/ACID, SQL). AWS handles hardware, OS & DB patching, backups, failover and monitoring; you handle schema,
queries, users and tuning. You cannot SSH into the host.

## Engines
**MySQL, PostgreSQL, MariaDB, Oracle, Microsoft SQL Server, IBM Db2** and **Amazon Aurora** (AWS-built,
MySQL/PostgreSQL-compatible, storage auto-grows and is replicated 6 ways across 3 AZs; also Aurora Serverless v2).

## DB instances
A DB instance = an isolated database environment with a **DB instance class** (`db.t3.micro`, `db.m6g.large`,
`db.r6g.xlarge`…), **storage** (gp3 / io1 / io2, autoscaling), engine version, parameter group, and a DNS **endpoint**
(`mydb.xxxx.ap-south-1.rds.amazonaws.com:3306`) that apps connect to. It runs in a **DB subnet group** (subnets in ≥2 AZs) in your VPC.

## Security
- Put RDS in **private subnets**, `Publicly accessible = No`.
- **Security group**: allow the DB port (3306/5432) **only from the app servers' security group**.
- **Encryption at rest** with KMS (chosen at creation; covers storage, snapshots, replicas) and **in transit** with SSL/TLS.
- **Credentials**: master password in **Secrets Manager** with rotation, or **IAM database authentication**.
- IAM policies control who can manage (create/delete/modify) instances; CloudTrail audits it; enhanced monitoring/Performance Insights for visibility.

## Backups
- **Automated backups**: daily snapshot + transaction logs, retention 1–35 days → **point-in-time restore** to any second (≈5 min back).
- **Manual snapshots**: kept until you delete them; can be copied to other regions/accounts.
- Restoring always creates a **new** DB instance.

## Multi-AZ
**High availability / disaster recovery**: RDS keeps a **synchronous standby** replica in another AZ. On failure
(AZ outage, instance crash, patching) it **fails over automatically** (~60–120 s) by flipping the same DNS endpoint to the standby.
The standby is **not readable** (in the classic setup) – it's for availability, not performance.
(Multi-AZ *DB cluster* deployments have two readable standbys.)

## Read replicas
**Asynchronous** copies used to **scale reads**: up to 15 replicas, same AZ / other AZ / **cross-region**, each with its own
endpoint. App sends writes to the primary and reads (reports, analytics) to replicas. Small replication lag possible.
A replica can be **promoted** to a standalone DB (e.g. for DR).

| | Multi-AZ | Read replica |
|---|---|---|
| Goal | high availability | read scaling |
| Replication | synchronous | asynchronous |
| Readable | no (standby) | yes |
| Failover | automatic | manual promotion |

## Use cases
- Classic web/e-commerce apps (orders, payments – need transactions and joins).
- ERP / CRM / financial systems with complex relational data and reporting.
- Lift-and-shift of existing MySQL/PostgreSQL/Oracle/SQL Server workloads.
- SaaS backends; WordPress/Moodle databases.

## DynamoDB vs RDS
| | DynamoDB | RDS |
|---|---|---|
| Model | NoSQL key-value / document | relational (SQL) |
| Schema | flexible (only key fixed) | fixed schema, migrations |
| Queries | by key / index, no joins | full SQL, joins, aggregates |
| Scaling | automatic, virtually unlimited, serverless | vertical (bigger class) + read replicas |
| Management | fully serverless | managed instances you size |
| Best for | massive scale, simple predictable access patterns | complex queries, transactions, existing SQL apps |

> **No RDS demo:** RDS is not part of LocalStack community edition (it's a Pro feature) and I had no AWS account, so RDS is
> covered in notes only. On real AWS the CLI would be e.g.
> `aws rds create-db-instance --db-instance-identifier saniya-db --engine mysql --db-instance-class db.t3.micro --allocated-storage 20 --master-username admin --manage-master-user-password --multi-az`.
