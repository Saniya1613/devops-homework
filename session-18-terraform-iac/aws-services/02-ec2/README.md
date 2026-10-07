# AWS EC2 – Elastic Compute Cloud

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

## What is EC2?
EC2 provides resizable **virtual servers ("instances")** in the AWS cloud. You choose the OS image, CPU/RAM size,
storage and network, launch in seconds, and pay per second/hour only while it runs. It is the classic
**IaaS** service: AWS manages the hardware and hypervisor; you manage the OS, patches and apps.

## AMI – Amazon Machine Image
A template used to launch an instance: root volume snapshot (OS + pre-installed software), architecture
(x86_64 / arm64), virtualization type and block-device mapping. AMIs are **regional** and have IDs like `ami-0abc...`.
- **AWS-provided:** Amazon Linux 2023, Ubuntu, Windows Server, RHEL…
- **Marketplace:** vendor images (e.g. with licensed software).
- **Custom/golden AMIs:** your own image built with Packer or "Create image" from an instance → faster, consistent launches.

## Instance types
Named `family + generation + [attributes].size`, e.g. `t3.micro`, `m7g.large` (`g` = Graviton/ARM).

| Family | Optimised for | Examples | Typical use |
|---|---|---|---|
| **T / M** (general purpose) | balanced CPU/RAM; T = burstable credits | `t2.micro`, `t3.medium`, `m6i.large` | web servers, dev/test, small DBs |
| **C** (compute) | high CPU | `c6i.xlarge` | batch, CI builds, gaming servers |
| **R / X** (memory) | high RAM | `r6i.2xlarge` | in-memory caches, big databases |
| **I / D** (storage) | fast local NVMe | `i4i.large` | NoSQL, data warehousing |
| **P / G / Inf** (accelerated) | GPUs / ML chips | `g5.xlarge`, `p4d` | ML training/inference, video |

Pricing models: **On-Demand**, **Reserved Instances / Savings Plans** (1–3 yr commitment, up to ~72% off),
**Spot** (spare capacity, up to ~90% off, can be interrupted), **Dedicated Hosts**. `t2.micro`/`t3.micro` are Free-Tier eligible.

## Key pairs
SSH login uses **public-key cryptography**: AWS stores the **public key** and injects it into the instance
(`~/.ssh/authorized_keys`); you keep the **private key** (`.pem`) – AWS shows it only once.
```bash
chmod 400 my-key.pem
ssh -i my-key.pem ec2-user@<public-ip>     # ubuntu@ for Ubuntu AMIs
```
Alternatives without opening port 22: **EC2 Instance Connect** and **SSM Session Manager**.

## Security groups
A **stateful virtual firewall at the instance (ENI) level**.
- Only **allow** rules (no deny). Default: all inbound denied, all outbound allowed.
- Stateful: if inbound traffic is allowed, the reply is automatically allowed out.
- Source can be a CIDR (`203.0.113.5/32`) or **another security group** (e.g. "DB SG allows 3306 only from App SG").
- Example web server: inbound 80/443 from `0.0.0.0/0`, 22 only from *my IP*.

## EBS – Elastic Block Store
Network-attached **block storage** volumes (virtual disks) for instances.
- Lives in **one AZ**; attach to an instance in the same AZ; persists independently of the instance (unless *Delete on termination*).
- Types: **gp3/gp2** (general SSD), **io2/io1** (provisioned IOPS for databases), **st1** (throughput HDD), **sc1** (cold HDD).
- **Snapshots** are incremental backups stored in S3 – used to restore, copy across regions or build AMIs.
- Can be **encrypted** with KMS; can be resized on the fly.
- Different from **instance store** (physically attached, very fast, but data lost when the instance stops).

## Public vs private IP
| | Private IP | Public IP | Elastic IP |
|---|---|---|---|
| Reachable from | inside the VPC (and peered/VPN networks) | the internet (via IGW) | the internet |
| Assigned | always, from the subnet CIDR (e.g. `10.20.1.4`) | only in public subnets with auto-assign / at launch | you allocate it and attach it |
| On stop/start | **kept** | **changes** (released on stop) | **kept** (static) |
| Cost | free | charged per hour (since 2024) | charged per hour |

The instance's OS only knows its private IP – the IGW does 1:1 NAT between public and private IP.

## Instance lifecycle
```text
           launch
  (AMI) ─────────► pending ──► running ◄──────────── start ──┐
                                 │  │                        │
                       reboot ◄──┘  ├── stop ──► stopping ──► stopped
                     (stays running)│
                                    └── terminate ──► shutting-down ──► terminated
```
- **pending** – being provisioned. **running** – billed for compute.
- **stopping/stopped** – not billed for compute (EBS still billed), public IP released, can change instance type.
- **reboot** – OS restart; same host, IPs kept.
- **hibernate** – RAM saved to EBS, resume later.
- **terminated** – gone for good (root EBS deleted by default).

## Use cases
- Hosting web/application servers (behind a load balancer, with Auto Scaling groups).
- Self-managed databases, Jenkins/GitLab runners, bastion hosts.
- Batch/HPC jobs, ML training on GPU instances, game servers.
- Dev/test environments that can be stopped at night to save money.
- Kubernetes worker nodes (EKS node groups) – the cluster in this course could run on EC2.

## Hands-on demo (LocalStack)
> Run against LocalStack community edition, where **EC2 is mocked**: API calls work and state transitions are
> tracked, but no real VM boots. No AWS account was available.

Create a key pair and a security group, then walk an instance through its lifecycle:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 create-key-pair --key-name saniya-key --query 'KeyName' --output text
saniya-key
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 create-security-group --group-name s18-web-sg --description 'web server SG'
{
    "GroupId": "sg-5b2583195efb94bb8",
    "Tags": []
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 authorize-security-group-ingress --group-id sg-5b2583195efb94bb8 --protocol tcp --port 80 --cidr 0.0.0.0/0 --query 'SecurityGroupRules[].[IpProtocol,FromPort,CidrIpv4]' --output text
tcp	80	0.0.0.0/0
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 run-instances --image-id ami-df5de72bdb3b --instance-type t2.micro --key-name saniya-key --security-group-ids sg-5b2583195efb94bb8 --query 'Instances[0].[InstanceId,InstanceType,State.Name,PrivateIpAddress]' --output text
i-1fc7bfbfcc85f9820	t2.micro	pending	10.228.251.3
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 describe-instances --instance-ids i-1fc7bfbfcc85f9820 --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,State:State.Name,PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress,AMI:ImageId}' --output table
--------------------------------------
|          DescribeInstances         |
+------------+-----------------------+
|  AMI       |  ami-df5de72bdb3b     |
|  Id        |  i-1fc7bfbfcc85f9820  |
|  PrivateIP |  10.228.251.3         |
|  PublicIP  |  54.214.127.155       |
|  State     |  running              |
|  Type      |  t2.micro             |
+------------+-----------------------+
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 stop-instances --instance-ids i-1fc7bfbfcc85f9820 --query 'StoppingInstances[].[InstanceId,PreviousState.Name,CurrentState.Name]' --output text
i-1fc7bfbfcc85f9820	running	stopping
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 start-instances --instance-ids i-1fc7bfbfcc85f9820 --query 'StartingInstances[].[InstanceId,PreviousState.Name,CurrentState.Name]' --output text
i-1fc7bfbfcc85f9820	stopped	pending
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 terminate-instances --instance-ids i-1fc7bfbfcc85f9820 --query 'TerminatingInstances[].[InstanceId,PreviousState.Name,CurrentState.Name]' --output text
i-1fc7bfbfcc85f9820	running	shutting-down
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/aws-services/02-ec2$ aws --endpoint-url http://localhost:31866 ec2 delete-security-group --group-id sg-5b2583195efb94bb8 && aws --endpoint-url http://localhost:31866 ec2 delete-key-pair --key-name saniya-key && echo 'cleaned up'
{
    "Return": true
}
cleaned up
```

**Observation:** the instance got a private IP (from LocalStack's default VPC) and a public IP, and the state columns
(`previous → current`) show the lifecycle from the diagram: `running → stopping`, `stopped → pending` (→ running) and
`running → shutting-down` (→ terminated). A full Terraform-managed EC2 deployment (VPC + SG + instance) is
in [session 19](../../../session-19-cloud-terraform/README.md).
