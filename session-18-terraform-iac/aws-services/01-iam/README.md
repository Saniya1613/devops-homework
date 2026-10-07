# AWS IAM – Identity and Access Management

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

## What is IAM?
IAM is the AWS service that controls **who** (authentication) can do **what** (authorization) on **which AWS resources**.
It is global (not tied to a region) and free. Every AWS API call is checked against IAM: if no policy explicitly
*allows* the action, it is **denied by default**; an explicit **Deny** always wins over any Allow.

## Core building blocks

| Concept | What it is | Example |
|---|---|---|
| **Root user** | The email that created the account. Has unlimited power – lock it away with MFA and don't use it day-to-day. | `owner@company.com` |
| **User** | A permanent identity for one person or application. Has long-term credentials: console password and/or access keys. | `saniya-dev` |
| **Group** | A collection of users. Policies attached to a group apply to every member. Groups can't be nested and can't be assumed. | `Developers`, `ReadOnly` |
| **Role** | An identity with permissions but **no long-term credentials**. Someone/something *assumes* it and gets temporary credentials from STS. | EC2 instance role, cross-account role, GitHub Actions OIDC role |
| **Policy** | A JSON document listing permissions (`Effect`, `Action`, `Resource`, optional `Condition`). | `AmazonS3ReadOnlyAccess` |
| **Permission** | The effective result of all policies that apply to a request – an action on a resource is allowed or denied. | `s3:GetObject` on `arn:aws:s3:::bucket/*` |

### Users vs Roles
- **Users** = long-lived identity, long-lived keys → risk if keys leak.
- **Roles** = short-lived (15 min – 12 h) credentials issued by STS on `AssumeRole` → nothing to leak permanently.
  Prefer roles for EC2/Lambda/ECS, CI/CD pipelines (OIDC federation) and cross-account access.

### Types of policies
- **AWS managed** – written and maintained by AWS (e.g. `AdministratorAccess`, `AmazonEC2ReadOnlyAccess`).
- **Customer managed** – your own reusable policies (like the one below).
- **Inline** – embedded directly in one user/group/role (1:1, deleted with it).
- **Resource-based** – attached to the resource instead of the identity (S3 bucket policy, SQS queue policy) and has a `Principal`.
- Also: permission boundaries, Service Control Policies (AWS Organizations), session policies.

### Policy anatomy – sample least-privilege policy
[`s3-read-only-policy.json`](./s3-read-only-policy.json) – allows *only* listing and reading objects of *one* bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListOnlyTheDemoBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::saniya-24bcs10246-demo-bucket"
    },
    {
      "Sid": "ReadObjectsInTheDemoBucket",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::saniya-24bcs10246-demo-bucket/*"
    }
  ]
}
```
- `Version` – policy language version (always `2012-10-17`).
- `Statement` – list of rules. `Sid` is an optional label.
- `Effect` – `Allow` or `Deny`.
- `Action` – API operations (`service:Operation`, wildcards allowed like `s3:Get*`).
- `Resource` – ARNs the statement applies to. Note `ListBucket` acts on the bucket ARN, `GetObject` on `bucket/*`.
- `Condition` (optional) – e.g. `"Condition": {"Bool": {"aws:SecureTransport": "true"}}` or restrict by source IP / MFA.

## Principle of least privilege
Grant **only the permissions needed to do the job, on only the resources needed, for only as long as needed**.
Start with nothing, add specific actions, scope `Resource` to exact ARNs instead of `"*"`, and use IAM Access Analyzer /
"last accessed" data to remove unused permissions. The policy above is an example: the user can read one bucket but
can't delete it, write to it, or even see other buckets.

## Best practices
1. **Protect the root user**: enable MFA, delete its access keys, use it only for the few root-only tasks.
2. **Enable MFA** for all human users.
3. **Use roles and temporary credentials** instead of long-lived access keys (IAM Identity Center/SSO for people, instance profiles for EC2, OIDC for CI).
4. **Assign permissions to groups**, not individual users.
5. **Least privilege**; prefer customer-managed policies scoped to specific resources.
6. **Rotate** any access keys that must exist; never commit keys to Git.
7. Use a **strong password policy**.
8. **Audit**: CloudTrail logs every API call; use the credential report, Access Analyzer and "last accessed" info.
9. Use **conditions** (MFA required, source IP, `aws:SecureTransport`) for sensitive actions.
10. Use **permission boundaries / SCPs** to put guardrails on what admins can delegate.

## Use cases
- Give each developer their own login, grouped by team (`Developers`, `Ops`, `ReadOnly`).
- Let an **EC2 instance** read from S3 / write to CloudWatch via an **instance role** – no keys on the server.
- Let **GitHub Actions** deploy with Terraform via an **OIDC role** – no secrets stored in GitHub.
- **Cross-account access**: a role in the prod account that the ops team in another account can assume.
- **Federation / SSO**: employees log in with Google Workspace / Azure AD and get mapped to roles.
- Terraform itself authenticates via an IAM user/role and needs permissions for every resource it manages.

## Hands-on demo (LocalStack)
> Run against LocalStack (local AWS emulator) – no AWS account was available. Note: LocalStack community edition stores
> IAM entities but does **not enforce** them, so this demo shows the *management* workflow, not access denials.

Create a group, a user, a customer-managed policy, attach the policy to the **group** and put the user in it:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam create-group --group-name s18-readers
{
    "Group": {
        "Path": "/",
        "GroupName": "s18-readers",
        "GroupId": "dpyifjfv7x21wxxhym57",
        "Arn": "arn:aws:iam::000000000000:group/s18-readers",
        "CreateDate": "2026-10-07T13:40:15.626000Z"
    }
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam create-user --user-name saniya-dev --tags Key=Roll,Value=24bcs10246
{
    "User": {
        "Path": "/",
        "UserName": "saniya-dev",
        "UserId": "8es63g1vujksoevd4yln",
        "Arn": "arn:aws:iam::000000000000:user/saniya-dev",
        "CreateDate": "2026-10-07T13:40:16.090000Z",
        "Tags": [
            {
                "Key": "Roll",
                "Value": "24bcs10246"
            }
        ]
    }
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam add-user-to-group --group-name s18-readers --user-name saniya-dev && echo added
added
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam create-policy --policy-name S18DemoBucketReadOnly --policy-document file://s3-read-only-policy.json
{
    "Policy": {
        "PolicyName": "S18DemoBucketReadOnly",
        "PolicyId": "AWBBL49I7KOZTEK10GTAI",
        "Arn": "arn:aws:iam::000000000000:policy/S18DemoBucketReadOnly",
        "Path": "/",
        "DefaultVersionId": "v1",
        "AttachmentCount": 0,
        "CreateDate": "2026-10-07T13:40:17.052000Z",
        "UpdateDate": "2026-10-07T13:40:17.052000Z"
    }
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam attach-group-policy --group-name s18-readers --policy-arn arn:aws:iam::000000000000:policy/S18DemoBucketReadOnly && echo attached
attached
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam list-attached-group-policies --group-name s18-readers
{
    "AttachedPolicies": [
        {
            "PolicyName": "S18DemoBucketReadOnly",
            "PolicyArn": "arn:aws:iam::000000000000:policy/S18DemoBucketReadOnly"
        }
    ]
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam get-group --group-name s18-readers --query 'Users[].UserName'
[
    "saniya-dev"
]
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam list-groups-for-user --user-name saniya-dev --query 'Groups[].GroupName'
[
    "s18-readers"
]
```

Clean up:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/01-iam$ aws --endpoint-url http://localhost:31866 iam detach-group-policy --group-name s18-readers --policy-arn arn:aws:iam::000000000000:policy/S18DemoBucketReadOnly && aws --endpoint-url http://localhost:31866 iam remove-user-from-group --group-name s18-readers --user-name saniya-dev && aws --endpoint-url http://localhost:31866 iam delete-policy --policy-arn arn:aws:iam::000000000000:policy/S18DemoBucketReadOnly && aws --endpoint-url http://localhost:31866 iam delete-user --user-name saniya-dev && aws --endpoint-url http://localhost:31866 iam delete-group --group-name s18-readers && echo 'cleaned up'
cleaned up
```

**Observation:** the permission was attached once, to the group – any user later added to `s18-readers` inherits it,
and removing a user from the group revokes it. The account ID `000000000000` is LocalStack's default fake account.
