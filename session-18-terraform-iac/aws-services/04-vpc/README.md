# AWS VPC – Virtual Private Cloud

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

## What is a VPC?
A VPC is your own **logically isolated private network** inside an AWS region. You choose its IP range, split it into
subnets, and control routing and firewalls. Every EC2 instance, RDS database, load balancer, EKS node etc. lives in a VPC.
Each region has a *default VPC* (`172.31.0.0/16`) so you can start quickly; production uses custom VPCs.
A VPC spans **all AZs of one region**; subnets live in **one AZ**.

## CIDR (Classless Inter-Domain Routing)
Notation `IP/prefix` – the prefix says how many leading bits are the network part; the rest are host addresses.

| CIDR | Addresses | Typical use |
|---|---|---|
| `10.0.0.0/16` | 65,536 | whole VPC (allowed VPC size: /16 – /28) |
| `10.0.1.0/24` | 256 (251 usable in AWS) | one subnet |
| `10.0.1.0/28` | 16 (11 usable) | smallest subnet |
| `203.0.113.7/32` | 1 | a single IP in a SG rule |
| `0.0.0.0/0` | everything | "the internet" / default route |

Use RFC 1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) and plan non-overlapping ranges if VPCs
will be peered or connected to on-prem. AWS reserves **5 IPs** in every subnet (network, VPC router, DNS, future, broadcast).

## Subnets
A range of IPs from the VPC CIDR, placed in **one Availability Zone**. Spread subnets across ≥2 AZs for high availability.
Whether a subnet is "public" or "private" is decided purely by its **route table**.

## Route tables
A set of rules (`destination CIDR → target`) that decides where traffic from a subnet goes.
- Every route table has the implicit **local** route (`10.0.0.0/16 → local`) so all subnets in the VPC can talk.
- Each subnet is associated with exactly one route table (or the VPC's *main* route table).
- Targets: `igw-…`, `nat-…`, VPC peering, Transit Gateway, VPN gateway, VPC endpoints…

## Internet Gateway (IGW)
A horizontally scaled, highly available VPC component that allows **two-way** communication between the VPC and the
internet. One IGW per VPC. A subnet becomes public when its route table has `0.0.0.0/0 → igw-…`, and instances also need a
public/Elastic IP.

## NAT Gateway
Lets instances in **private** subnets make **outbound** connections to the internet (OS updates, calling APIs) while
**blocking inbound** connections from the internet. Placed in a public subnet with an Elastic IP; the private route table
gets `0.0.0.0/0 → nat-…`. It's managed and AZ-scoped (use one per AZ for HA) and charged per hour + per GB.
(Older alternative: a self-managed NAT instance.)

## Security groups vs Network ACLs
| | **Security Group** | **Network ACL** |
|---|---|---|
| Level | instance / ENI | subnet |
| State | **stateful** – return traffic auto-allowed | **stateless** – return traffic must be allowed explicitly (ephemeral ports 1024-65535) |
| Rules | allow only | allow **and deny** |
| Evaluation | all rules evaluated together | rules processed **in number order**, first match wins |
| Default | deny all in, allow all out | default NACL allows all; custom NACL denies all until rules are added |
| Typical use | main firewall per tier (web/app/db) | coarse subnet-wide guard rail, e.g. block a malicious IP range |

## Public vs private subnet
| | Public subnet | Private subnet |
|---|---|---|
| Route `0.0.0.0/0` | → **Internet Gateway** | → **NAT Gateway** (or none) |
| Instances have public IPs | yes | no |
| Reachable from internet | yes (if SG allows) | **no** |
| Can reach internet | yes | outbound only via NAT |
| Put here | load balancers, bastion host, NAT gateway | app servers, databases, caches, internal services |

## Typical 2-tier layout
```text
                           Internet
                              │
                     ┌────────┴────────┐
                     │ Internet Gateway│
 VPC 10.0.0.0/16     └────────┬────────┘
 ┌────────────────────────────┼──────────────────────────────────┐
 │  Public subnet 10.0.1.0/24 │ (RT: 0.0.0.0/0 → IGW)            │
 │     [ ALB ]   [ NAT GW ]   [ Bastion ]                         │
 │                   │                                            │
 │  Private subnet 10.0.2.0/24 (RT: 0.0.0.0/0 → NAT GW)           │
 │     [ App EC2 ]  ──►  [ RDS ]   (SG: DB allows 3306 from App SG)│
 └───────────────────────────────────────────────────────────────┘
```

## Hands-on
The VPC → public subnet → IGW → route table → security group → EC2 chain is built **with Terraform and verified with
`aws ec2 describe-vpcs`** in [session 19](../../../session-19-cloud-terraform/README.md), so it isn't repeated here.
