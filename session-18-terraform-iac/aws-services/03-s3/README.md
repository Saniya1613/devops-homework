# AWS S3 – Simple Storage Service

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

## What is S3?
S3 is AWS's **object storage** service: store any amount of data as objects in buckets and access it over HTTPS/API.
It is designed for **99.999999999 % (11 nines) durability** (data is replicated across ≥3 AZs) and is virtually
unlimited in size. It is not a filesystem or block disk – you `PUT`/`GET` whole objects by key.

## Buckets
- A **container for objects**. Name is **globally unique** across all AWS accounts, 3–63 chars, lowercase, DNS-compatible.
- Created in **one region** (data stays there unless you replicate it).
- Bucket-level settings: versioning, lifecycle rules, encryption default, bucket policy, Block Public Access, logging, replication, static website hosting.
- ARN: `arn:aws:s3:::bucket-name`.

## Objects
- An object = **key** (full "path", e.g. `logs/2026/10/app.log`) + **data** (0 B – 5 TB) + **metadata** (content-type, custom `x-amz-meta-*`) + optional **tags** + **version ID**.
- "Folders" are just key prefixes shown by the console.
- Uploads > 100 MB should use **multipart upload**; single PUT max is 5 GB.
- URL: `https://bucket.s3.region.amazonaws.com/key`.

## Storage classes
| Class | Use for | Availability / AZs | Retrieval |
|---|---|---|---|
| **S3 Standard** | frequently accessed data | 99.99 %, ≥3 AZ | ms |
| **S3 Intelligent-Tiering** | unknown/changing access patterns – auto moves between tiers | 99.9 %, ≥3 AZ | ms |
| **S3 Standard-IA** | infrequent access, but needs fast retrieval (backups) | 99.9 %, ≥3 AZ | ms, retrieval fee |
| **S3 One Zone-IA** | re-creatable infrequent data | 99.5 %, **1 AZ** | ms, retrieval fee |
| **S3 Glacier Instant Retrieval** | archive accessed ~once a quarter | ≥3 AZ | ms |
| **S3 Glacier Flexible Retrieval** | archive | ≥3 AZ | minutes – 12 h |
| **S3 Glacier Deep Archive** | long-term compliance archive (cheapest) | ≥3 AZ | 12 – 48 h |
| **S3 Express One Zone** | ultra-low-latency hot data | 1 AZ | single-digit ms |

## Versioning
- Bucket states: *unversioned* (default) → *Enabled* → *Suspended* (can never go back to unversioned).
- Every overwrite creates a **new version**; a delete only adds a **delete marker** – older versions can be restored.
- Protects against accidental overwrite/delete; required for replication; combine with **MFA Delete** / **Object Lock** for stronger protection.
- Old versions cost storage → expire them with lifecycle rules.

## Lifecycle policies
Rules (by prefix/tag) that automatically **transition** objects to cheaper classes or **expire** (delete) them.
Example – [`lifecycle.json`](./lifecycle.json): logs move to Standard-IA after 30 days, Glacier after 90, deleted after
365; non-current versions deleted after 30 days.

## Encryption
- **In transit:** HTTPS/TLS (enforce with a bucket policy condition `aws:SecureTransport`).
- **At rest (server-side)** – since Jan 2023 every new object is encrypted by default:
  - **SSE-S3** – AES-256 keys managed by S3 (default).
  - **SSE-KMS** – keys in AWS KMS: audit trail in CloudTrail, key policies, rotation.
  - **DSSE-KMS** – dual-layer KMS encryption for compliance.
  - **SSE-C** – you supply the key with each request.
- **Client-side encryption** – encrypt before upload; AWS never sees plaintext.

## Bucket policies
A **resource-based JSON policy** attached to the bucket (has a `Principal`). Used to grant cross-account access, make a
static website public, restrict access to a VPC endpoint/IP, or deny non-TLS requests. Example – deny plain HTTP:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyInsecureTransport",
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:*",
    "Resource": ["arn:aws:s3:::saniya-24bcs10246-notes-bucket", "arn:aws:s3:::saniya-24bcs10246-notes-bucket/*"],
    "Condition": { "Bool": { "aws:SecureTransport": "false" } }
  }]
}
```
**Block Public Access** (on by default) overrides any policy/ACL that would make the bucket public – keep it on unless you
deliberately host public content. IAM policies (identity side) and bucket policies (resource side) are evaluated together.

## Use cases
- Backup & restore, disaster recovery, long-term archives (Glacier).
- **Static website hosting** (often behind CloudFront).
- Data lake for analytics (Athena, EMR, Redshift Spectrum).
- Application assets: user uploads, images, videos.
- Logs (CloudTrail, ALB, VPC flow logs).
- **Terraform remote state** backend (S3 bucket + DynamoDB/S3 lock) – see the [Terraform demo](../../terraform-s3-demo/README.md).
- Software artifacts / build outputs from CI pipelines.

## Hands-on demo (LocalStack)
> Run against LocalStack (local AWS emulator) – no AWS account was available. Lifecycle transitions are stored but not actually executed by LocalStack.

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3 mb s3://saniya-24bcs10246-notes-bucket
make_bucket: saniya-24bcs10246-notes-bucket
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3api put-bucket-versioning --bucket saniya-24bcs10246-notes-bucket --versioning-configuration Status=Enabled && aws --endpoint-url http://localhost:31866 s3api get-bucket-versioning --bucket saniya-24bcs10246-notes-bucket
{
    "Status": "Enabled"
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3api put-bucket-encryption --bucket saniya-24bcs10246-notes-bucket --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' && aws --endpoint-url http://localhost:31866 s3api get-bucket-encryption --bucket saniya-24bcs10246-notes-bucket
{
    "ServerSideEncryptionConfiguration": {
        "Rules": [
            {
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }
        ]
    }
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3api put-bucket-lifecycle-configuration --bucket saniya-24bcs10246-notes-bucket --lifecycle-configuration file://lifecycle.json && aws --endpoint-url http://localhost:31866 s3api get-bucket-lifecycle-configuration --bucket saniya-24bcs10246-notes-bucket --query 'Rules[].{ID:ID,Prefix:Filter.Prefix,Transitions:Transitions,ExpireDays:Expiration.Days}'
[
    {
        "ID": "logs-to-ia-then-glacier",
        "Prefix": "logs/",
        "Transitions": [
            {
                "Days": 30,
                "StorageClass": "STANDARD_IA"
            },
            {
                "Days": 90,
                "StorageClass": "GLACIER"
            }
        ],
        "ExpireDays": 365
    }
]
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3 cp lifecycle.json s3://saniya-24bcs10246-notes-bucket/logs/lifecycle.json --storage-class STANDARD_IA --no-progress
upload: ./lifecycle.json to s3://saniya-24bcs10246-notes-bucket/logs/lifecycle.json
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3api head-object --bucket saniya-24bcs10246-notes-bucket --key logs/lifecycle.json --query '{Size:ContentLength,Class:StorageClass,SSE:ServerSideEncryption,Version:VersionId}'
{
    "Size": 374,
    "Class": "STANDARD_IA",
    "SSE": "AES256",
    "Version": "aT4jjSTUHbtCsUksdK7WDgijGrABw835"
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3 ls s3://saniya-24bcs10246-notes-bucket --recursive
2026-10-07 13:40:33        374 logs/lifecycle.json
```

Try to delete the bucket – this **fails**, which nicely shows versioning at work:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3 rb s3://saniya-24bcs10246-notes-bucket --force
delete: s3://saniya-24bcs10246-notes-bucket/logs/lifecycle.json
remove_bucket failed: s3://saniya-24bcs10246-notes-bucket An error occurred (BucketNotEmpty) when calling the DeleteBucket operation: The bucket you tried to delete is not empty. You must delete all versions in the bucket.
```

`rb --force` only deleted the *current* view of the object – in a versioned bucket that just adds a **delete marker**; the old version is still there:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3api list-object-versions --bucket saniya-24bcs10246-notes-bucket --query '{Versions:Versions[].[Key,VersionId,IsLatest],DeleteMarkers:DeleteMarkers[].[Key,VersionId,IsLatest]}' --output json
{
    "Versions": [
        [
            "logs/lifecycle.json",
            "aT4jjSTUHbtCsUksdK7WDgijGrABw835",
            false
        ]
    ],
    "DeleteMarkers": [
        [
            "logs/lifecycle.json",
            "xeFmEzQz1uNxIRfMP8s3p_9CFS86ZVXL",
            true
        ]
    ]
}
```

Permanently delete the version and the delete marker (by version ID), then the bucket:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3api delete-object --bucket saniya-24bcs10246-notes-bucket --key logs/lifecycle.json --version-id aT4jjSTUHbtCsUksdK7WDgijGrABw835 && aws --endpoint-url http://localhost:31866 s3api delete-object --bucket saniya-24bcs10246-notes-bucket --key logs/lifecycle.json --version-id xeFmEzQz1uNxIRfMP8s3p_9CFS86ZVXL && aws --endpoint-url http://localhost:31866 s3api delete-bucket --bucket saniya-24bcs10246-notes-bucket && echo 'bucket deleted'
{
    "VersionId": "aT4jjSTUHbtCsUksdK7WDgijGrABw835"
}
{
    "DeleteMarker": true,
    "VersionId": "xeFmEzQz1uNxIRfMP8s3p_9CFS86ZVXL"
}
bucket deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/03-s3$ aws --endpoint-url http://localhost:31866 s3 ls
```

**Observation:** the uploaded object was stored in `STANDARD_IA`, encrypted with `AES256` (SSE-S3) and got a version ID
because versioning was enabled. Deleting an object in a versioned bucket only places a delete marker, so the bucket was
still "not empty" – a version must be deleted explicitly by its version ID. This is exactly what protects you from accidental deletes.
