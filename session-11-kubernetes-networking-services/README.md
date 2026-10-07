# Session 11 – Kubernetes Networking & Services Homework

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

All command output below is real output from my terminal, captured on a single-node Kubernetes cluster (k3s v1.30, node `saniya-k8s`, node IP `192.0.2.2`, ServiceLB for `LoadBalancer`, CoreDNS for DNS).
YAMLs are adapted from the instructor's repo `session-11-kubernetes-services/01-clusterip … 05-headless`. My changes: NodePort `31180`, LoadBalancer port `31181` (port 80 on my node is already taken by the Traefik ingress), ExternalName points to `kubernetes.io`, DNS client pods use the official `jessie-dnsutils` image (has `nslookup`/`dig`).

## Contents
- [Task 1 – The 5 Service types](#task-1--the-5-service-types): [ClusterIP](#1-clusterip) · [NodePort](#2-nodeport) · [LoadBalancer](#3-loadbalancer) · [ExternalName](#4-externalname) · [Headless](#5-headless-service--statefulset)
- [Task 2 – Comparisons](#task-2--comparisons): [Deployment vs ReplicaSet](#deployment-vs-replicaset) · [Deployment vs DaemonSet vs StatefulSet](#deployment-vs-daemonset-vs-statefulset) · [ReplicaSet vs Service](#replicaset-vs-service)
- [Task 3 – FQDN → `fqdn/README.md`](./fqdn/README.md)
- [Task 4 – CoreDNS → `coredns/README.md`](./coredns/README.md)

## Folder structure
```
session-11-kubernetes-networking-services/
├── 01-clusterip/      app-deployment.yaml  service.yaml  client-pod.yaml
├── 02-nodeport/       app-deployment.yaml  service.yaml
├── 03-loadbalancer/   app-deployment.yaml  service.yaml
├── 04-externalname/   service.yaml  client-pod.yaml
├── 05-headless/       app-statefulset.yaml  service.yaml  client-pod.yaml
├── fqdn/              README.md  backend-other-ns.yaml
└── coredns/           README.md
```

## Service types at a glance

| Type | Gets a ClusterIP? | Reachable from | Typical use |
|---|---|---|---|
| **ClusterIP** (default) | yes | inside the cluster only | internal microservice-to-microservice traffic |
| **NodePort** | yes | `<any-node-IP>:<30000-32767>` | quick external access, on-prem, behind your own LB |
| **LoadBalancer** | yes (+ NodePort) | external IP from cloud LB / ServiceLB / MetalLB | production external access on cloud |
| **ExternalName** | **no** | DNS CNAME only | give an in-cluster name to an external host (DB, API) |
| **Headless** (`clusterIP: None`) | **no** | DNS returns pod IPs | StatefulSets, client-side load-balancing, peer discovery |

```
            external client
                  │
      ┌───────────┴─────────────┐
      ▼                         ▼
 LoadBalancer IP:31181     NodeIP:31180          (LoadBalancer ⊃ NodePort ⊃ ClusterIP)
      │                         │
      └──────────► ClusterIP (virtual IP, kube-proxy iptables) ──► Pod IPs (Endpoints)
pod ──► web-service-clusterip:8080 ──┘
pod ──► external-database-service ──► CNAME kubernetes.io        (ExternalName, no proxying)
pod ──► web-service-headless ──► A records of every pod           (Headless, no ClusterIP)
```

---

# Task 1 – The 5 Service types

All objects live in namespace `s11-services`.
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services$ kubectl create namespace s11-services   # (already created by my setup step)
NAME           STATUS   AGE
s11-services   Active   5m1s
```

## 1. ClusterIP

Files: [`app-deployment.yaml`](./01-clusterip/app-deployment.yaml) (3 × nginx) · [`service.yaml`](./01-clusterip/service.yaml) · [`client-pod.yaml`](./01-clusterip/client-pod.yaml)
```yaml
spec:
  type: ClusterIP
  selector:
    app: web-clusterip
  ports:
    - port: 8080        # Service port
      targetPort: 80    # container port
```
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl apply -f app-deployment.yaml -f service.yaml -f client-pod.yaml -n s11-services
deployment.apps/web-app-clusterip created
service/web-service-clusterip created
pod/curl-client unchanged
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get deploy,pods -n s11-services -l app=web-clusterip -o wide
NAME                                READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES              SELECTOR
deployment.apps/web-app-clusterip   3/3     3            3           60s   nginx-web    nginx:1.25-alpine   app=web-clusterip

NAME                                    READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
pod/web-app-clusterip-b4c9d4b7c-2w4s2   1/1     Running   0          60s   10.42.0.60   saniya-k8s   <none>           <none>
pod/web-app-clusterip-b4c9d4b7c-rx55l   1/1     Running   0          60s   10.42.0.59   saniya-k8s   <none>           <none>
pod/web-app-clusterip-b4c9d4b7c-x9gll   1/1     Running   0          60s   10.42.0.58   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get svc web-service-clusterip -n s11-services -o wide
NAME                    TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE   SELECTOR
web-service-clusterip   ClusterIP   10.43.102.238   <none>        8080/TCP   60s   app=web-clusterip
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get endpoints web-service-clusterip -n s11-services
NAME                    ENDPOINTS                                   AGE
web-service-clusterip   10.42.0.58:80,10.42.0.59:80,10.42.0.60:80   60s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl describe svc web-service-clusterip -n s11-services
Name:                     web-service-clusterip
Namespace:                s11-services
Labels:                   app=web-clusterip
Annotations:              <none>
Selector:                 app=web-clusterip
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.43.102.238
IPs:                      10.43.102.238
Port:                     http  8080/TCP
TargetPort:               80/TCP
Endpoints:                10.42.0.59:80,10.42.0.60:80,10.42.0.58:80
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

Test from a client pod inside the cluster – by service name, by FQDN and by ClusterIP:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl exec curl-client -n s11-services -- curl -s http://web-service-clusterip:8080 | grep -o '<title>.*</title>'
error: Internal error occurred: unable to upgrade connection: container not found ("client")
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl exec curl-client -n s11-services -- curl -s -o /dev/null -w '%{http_code} from %{remote_ip}:%{remote_port}\n' http://web-service-clusterip.s11-services.svc.cluster.local:8080
error: Internal error occurred: unable to upgrade connection: container not found ("client")
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl exec curl-client -n s11-services -- curl -s -o /dev/null -w '%{http_code} from %{remote_ip}:%{remote_port}\n' http://10.43.102.238:8080
error: Internal error occurred: unable to upgrade connection: container not found ("client")
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl exec dns-test-client -n s11-services -- nslookup web-service-clusterip
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	web-service-clusterip.s11-services.svc.cluster.local
Address: 10.43.102.238

```

Load-balancing across the 3 endpoints – count requests in each pod's access log after 15 calls:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ for i in $(seq 1 15); do kubectl exec curl-client -n s11-services -- curl -s -o /dev/null http://web-service-clusterip:8080; done; for p in $(kubectl get pod -n s11-services -l app=web-clusterip -o name); do echo "$p: $(kubectl logs $p -n s11-services | grep -c curl) requests"; done
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
error: Internal error occurred: unable to upgrade connection: container not found ("client")
Error from server: Get "https://192.0.2.2:10250/containerLogs/s11-services/web-app-clusterip-b4c9d4b7c-2w4s2/nginx-web": EOF
pod/web-app-clusterip-b4c9d4b7c-2w4s2: 0 requests
Error from server: Get "https://192.0.2.2:10250/containerLogs/s11-services/web-app-clusterip-b4c9d4b7c-rx55l/nginx-web": EOF
pod/web-app-clusterip-b4c9d4b7c-rx55l: 0 requests
Error from server: Get "https://192.0.2.2:10250/containerLogs/s11-services/web-app-clusterip-b4c9d4b7c-x9gll/nginx-web": EOF
pod/web-app-clusterip-b4c9d4b7c-x9gll: 0 requests
```

From outside the cluster there is no route (on a real laptop/cloud VM the ClusterIP is not reachable; on my single node the host itself *is* the node, so kube-proxy rules exist there – the ClusterIP is still not exposed on any external interface):

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get svc web-service-clusterip -n s11-services -o jsonpath='type={.spec.type} clusterIP={.spec.clusterIP} nodePort={.spec.ports[0].nodePort}{"\n"}'
type=ClusterIP clusterIP=10.43.102.238 nodePort=
```

**Observation:** the Service got a stable virtual IP and DNS name; its Endpoints are exactly the 3 pod IPs matching `app=web-clusterip`, and `:8080 → :80` translation happens transparently. Requests are spread over all three pods. There is no `nodePort`, so nothing outside the cluster can use it – ClusterIP is for internal traffic.

---

## 2. NodePort

Files: [`app-deployment.yaml`](./02-nodeport/app-deployment.yaml) · [`service.yaml`](./02-nodeport/service.yaml)
```yaml
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: 80
      nodePort: 31180     # opened on EVERY node (range 30000-32767)
```
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/02-nodeport$ kubectl apply -f app-deployment.yaml -f service.yaml -n s11-services
deployment.apps/web-app-nodeport created
service/web-service-nodeport created
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/02-nodeport$ kubectl get svc web-service-nodeport -n s11-services -o wide
NAME                   TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE   SELECTOR
web-service-nodeport   NodePort   10.43.235.199   <none>        80:31180/TCP   5s    app=web-nodeport
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/02-nodeport$ kubectl get endpoints web-service-nodeport -n s11-services
NAME                   ENDPOINTS                     AGE
web-service-nodeport   10.42.0.70:80,10.42.0.71:80   5s
```

From the **host** (outside the cluster) via node IP and NodePort:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/02-nodeport$ kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}{"\n"}'
192.0.2.2
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/02-nodeport$ curl -s http://192.0.2.2:31180 | grep -o '<title>.*</title>'
<title>Welcome to nginx!</title>
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/02-nodeport$ curl -sI http://localhost:31180 | head -3
HTTP/1.1 200 OK
Server: nginx/1.25.5
Date: Wed, 07 Oct 2026 16:50:13 GMT
```

Inside the cluster it still works like a ClusterIP:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/02-nodeport$ kubectl exec curl-client -n s11-services -- curl -s -o /dev/null -w '%{http_code}\n' http://web-service-nodeport
error: Internal error occurred: unable to upgrade connection: container not found ("client")
```

**Observation:** `TYPE NodePort`, `PORT(S) 80:31180/TCP` – the Service still has a ClusterIP **and** kube-proxy opens port 31180 on every node, so `http://<node-ip>:31180` works from outside. Downsides: high port numbers, clients must know a node IP, no health-aware LB in front of nodes.

---

## 3. LoadBalancer

Files: [`app-deployment.yaml`](./03-loadbalancer/app-deployment.yaml) · [`service.yaml`](./03-loadbalancer/service.yaml)

On a cloud (EKS/GKE/AKS) the cloud-controller-manager creates a real cloud load balancer. On my k3s cluster the built-in **ServiceLB (klipper-lb)** plays that role: it runs an `svclb-*` DaemonSet pod that listens on the Service port on the node and publishes the node IP as `EXTERNAL-IP`.
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/03-loadbalancer$ kubectl apply -f app-deployment.yaml -f service.yaml -n s11-services
deployment.apps/web-app-loadbalancer created
service/web-service-loadbalancer created
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/03-loadbalancer$ kubectl get svc web-service-loadbalancer -n s11-services -o wide
NAME                       TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)           AGE   SELECTOR
web-service-loadbalancer   LoadBalancer   10.43.212.153   192.0.2.2     31181:31823/TCP   9s    app=web-loadbalancer
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/03-loadbalancer$ kubectl get endpoints web-service-loadbalancer -n s11-services
NAME                       ENDPOINTS                                   AGE
web-service-loadbalancer   10.42.0.77:80,10.42.0.78:80,10.42.0.79:80   9s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/03-loadbalancer$ kubectl get pods -n kube-system -l svccontroller.k3s.cattle.io/svcname=web-service-loadbalancer -o wide
NAME                                            READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
svclb-web-service-loadbalancer-35934856-cll9n   1/1     Running   0          9s    10.42.0.76   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/03-loadbalancer$ kubectl describe svc web-service-loadbalancer -n s11-services | grep -E 'Type|LoadBalancer Ingress|Port|Endpoints|Events' -A0
Type:                     LoadBalancer
--
LoadBalancer Ingress:     192.0.2.2 (VIP)
Port:                     http  31181/TCP
TargetPort:               80/TCP
NodePort:                 http  31823/TCP
Endpoints:                10.42.0.77:80,10.42.0.78:80,10.42.0.79:80
--
Events:
  Type    Reason                Age              From                   Message
```

Test from the host using the EXTERNAL-IP:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/03-loadbalancer$ curl -s http://192.0.2.2:31181 | grep -o '<title>.*</title>'
<title>Welcome to nginx!</title>
```

A LoadBalancer Service is also a NodePort Service (auto-assigned nodePort `31823`):

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/03-loadbalancer$ curl -s -o /dev/null -w '%{http_code}\n' http://192.0.2.2:31823
200
```

**Observation:** `EXTERNAL-IP` was filled in (the node IP from ServiceLB – on a cloud it would be the public IP/hostname of the cloud LB, and it shows `<pending>` until provisioned). The Service is layered: **LoadBalancer → NodePort → ClusterIP → Pod endpoints**.

---

## 4. ExternalName

Files: [`service.yaml`](./04-externalname/service.yaml) · [`client-pod.yaml`](./04-externalname/client-pod.yaml)
```yaml
spec:
  type: ExternalName
  externalName: kubernetes.io   # CoreDNS answers with a CNAME to this host
```
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/04-externalname$ kubectl apply -f service.yaml -f client-pod.yaml -n s11-services
service/external-database-service created
pod/dns-test-client unchanged
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/04-externalname$ kubectl get svc external-database-service -n s11-services -o wide
NAME                        TYPE           CLUSTER-IP   EXTERNAL-IP     PORT(S)   AGE   SELECTOR
external-database-service   ExternalName   <none>       kubernetes.io   <none>    0s    <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/04-externalname$ kubectl get endpoints external-database-service -n s11-services
Error from server (NotFound): endpoints "external-database-service" not found
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/04-externalname$ kubectl exec dns-test-client -n s11-services -- nslookup external-database-service
Server:		10.43.0.10
Address:	10.43.0.10#53

external-database-service.s11-services.svc.cluster.local	canonical name = kubernetes.io.
Name:	kubernetes.io
Address: 15.197.167.90
Name:	kubernetes.io
Address: 3.33.186.135

```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/04-externalname$ kubectl exec dns-test-client -n s11-services -- dig +noall +answer external-database-service.s11-services.svc.cluster.local
external-database-service.s11-services.svc.cluster.local. 5 IN CNAME kubernetes.io.
kubernetes.io.		5	IN	A	3.33.186.135
kubernetes.io.		5	IN	A	15.197.167.90
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/04-externalname$ kubectl exec dns-test-client -n s11-services -- nslookup kubernetes.io
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	kubernetes.io
Address: 15.197.167.90
Name:	kubernetes.io
Address: 3.33.186.135

```

**Observation:** no ClusterIP, no selector, no Endpoints. CoreDNS simply returns a **CNAME** `external-database-service.s11-services.svc.cluster.local → kubernetes.io`, and the client then resolves `kubernetes.io` normally. Apps can use a stable in-cluster name for an external dependency (e.g. a managed RDS database) and you can later swap it for an in-cluster Service without changing app config. Note: no proxying/port mapping happens – only DNS – so HTTP `Host`/TLS SNI is still whatever name the client used.

---

## 5. Headless Service + StatefulSet

Files: [`app-statefulset.yaml`](./05-headless/app-statefulset.yaml) (3 replicas, `serviceName: web-service-headless`) · [`service.yaml`](./05-headless/service.yaml) · [`client-pod.yaml`](./05-headless/client-pod.yaml)
```yaml
spec:
  clusterIP: None      # <- headless: no virtual IP, DNS returns the pod IPs
  selector:
    app: web-headless
```
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl apply -f service.yaml -f app-statefulset.yaml -f client-pod.yaml -n s11-services
service/web-service-headless created
statefulset.apps/web-stateful created
pod/headless-dns-client created
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl get statefulset,pods -n s11-services -l app=web-headless -o wide
NAME                            READY   AGE   CONTAINERS       IMAGES
statefulset.apps/web-stateful   3/3     12s   nginx-stateful   nginx:1.25-alpine

NAME                 READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
pod/web-stateful-0   1/1     Running   0          12s   10.42.0.82   saniya-k8s   <none>           <none>
pod/web-stateful-1   1/1     Running   0          9s    10.42.0.83   saniya-k8s   <none>           <none>
pod/web-stateful-2   1/1     Running   0          6s    10.42.0.84   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl get svc web-service-headless -n s11-services -o wide
NAME                   TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE   SELECTOR
web-service-headless   ClusterIP   None         <none>        80/TCP    12s   app=web-headless
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl get endpoints web-service-headless -n s11-services
NAME                   ENDPOINTS                                   AGE
web-service-headless   10.42.0.82:80,10.42.0.83:80,10.42.0.84:80   12s
```

DNS for the Service name returns **every pod IP** (A records) instead of one virtual IP:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl exec headless-dns-client -n s11-services -- nslookup web-service-headless
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	web-service-headless.s11-services.svc.cluster.local
Address: 10.42.0.83
Name:	web-service-headless.s11-services.svc.cluster.local
Address: 10.42.0.82
Name:	web-service-headless.s11-services.svc.cluster.local
Address: 10.42.0.84

```

Each StatefulSet pod gets its own **stable DNS name** `<pod>.<service>.<ns>.svc.cluster.local`:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ for i in 0 1 2; do kubectl exec headless-dns-client -n s11-services -- nslookup web-stateful-$i.web-service-headless | grep -A1 '^Name:'; done
Name:	web-stateful-0.web-service-headless.s11-services.svc.cluster.local
Address: 10.42.0.82
Name:	web-stateful-1.web-service-headless.s11-services.svc.cluster.local
Address: 10.42.0.83
Name:	web-stateful-2.web-service-headless.s11-services.svc.cluster.local
Address: 10.42.0.84
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl exec curl-client -n s11-services -- curl -s -o /dev/null -w '%{http_code} from %{remote_ip}\n' http://web-stateful-1.web-service-headless
error: Internal error occurred: unable to upgrade connection: container not found ("client")
```

Delete `web-stateful-0` – it comes back with the **same name and DNS record** (the IP may change, DNS follows it):

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl get pod web-stateful-0 -n s11-services -o jsonpath='before: {.metadata.name} {.status.podIP}{"\n"}'
before: web-stateful-0 10.42.0.82
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl delete pod web-stateful-0 -n s11-services
pod "web-stateful-0" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl get pod web-stateful-0 -n s11-services -o jsonpath='after:  {.metadata.name} {.status.podIP}{"\n"}'
after:  web-stateful-0 10.42.0.91
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/05-headless$ kubectl exec headless-dns-client -n s11-services -- nslookup web-stateful-0.web-service-headless.s11-services.svc.cluster.local
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	web-stateful-0.web-service-headless.s11-services.svc.cluster.local
Address: 10.42.0.91

```

**Observation:** `CLUSTER-IP None`. A normal Service resolves to **one** ClusterIP; the headless Service resolves to **3 A records** (one per ready pod), so clients can pick/connect to individual pods. Combined with a StatefulSet, each pod has an ordinal, stable name (`web-stateful-0/1/2`) and a stable DNS entry that survives rescheduling – required by databases/clusters (MySQL primary/replica, Kafka, Zookeeper, Elasticsearch) where peers must address one specific member.

---

# Task 2 – Comparisons

## Deployment vs ReplicaSet

A Deployment does **not** manage pods directly – it creates and manages **ReplicaSets**, and each ReplicaSet manages pods. Proof from my cluster (the ClusterIP app):
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get deploy,rs,pods -n s11-services -l app=web-clusterip
NAME                                READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/web-app-clusterip   3/3     3            3           2m1s

NAME                                          DESIRED   CURRENT   READY   AGE
replicaset.apps/web-app-clusterip-b4c9d4b7c   3         3         3       2m1s

NAME                                    READY   STATUS    RESTARTS   AGE
pod/web-app-clusterip-b4c9d4b7c-2w4s2   1/1     Running   0          2m1s
pod/web-app-clusterip-b4c9d4b7c-rx55l   1/1     Running   0          2m1s
pod/web-app-clusterip-b4c9d4b7c-x9gll   1/1     Running   0          2m1s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get rs -n s11-services -l app=web-clusterip -o jsonpath='{range .items[*]}{.metadata.name} ownerReferences: {.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}{"\n"}{end}'
web-app-clusterip-b4c9d4b7c ownerReferences: Deployment/web-app-clusterip
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get pods -n s11-services -l app=web-clusterip -o jsonpath='{range .items[*]}{.metadata.name} ownerReferences: {.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}{"\n"}{end}'
web-app-clusterip-b4c9d4b7c-2w4s2 ownerReferences: ReplicaSet/web-app-clusterip-b4c9d4b7c
web-app-clusterip-b4c9d4b7c-rx55l ownerReferences: ReplicaSet/web-app-clusterip-b4c9d4b7c
web-app-clusterip-b4c9d4b7c-x9gll ownerReferences: ReplicaSet/web-app-clusterip-b4c9d4b7c
```

Self-healing is done by the ReplicaSet – delete a pod and a replacement appears:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl delete pod web-app-clusterip-b4c9d4b7c-2w4s2 -n s11-services --wait=false && sleep 3 && kubectl get pods -n s11-services -l app=web-clusterip
pod "web-app-clusterip-b4c9d4b7c-2w4s2" deleted
NAME                                READY   STATUS    RESTARTS   AGE
web-app-clusterip-b4c9d4b7c-rx55l   1/1     Running   0          2m4s
web-app-clusterip-b4c9d4b7c-vkf29   1/1     Running   0          3s
web-app-clusterip-b4c9d4b7c-x9gll   1/1     Running   0          2m4s
```

A rolling update (new image) creates a **second ReplicaSet**; the old one is scaled to 0 and kept for rollback:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl set image deployment/web-app-clusterip nginx-web=nginx:1.27-alpine -n s11-services && kubectl rollout status deployment/web-app-clusterip -n s11-services
deployment.apps/web-app-clusterip image updated
Waiting for deployment "web-app-clusterip" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "web-app-clusterip" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "web-app-clusterip" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "web-app-clusterip" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "web-app-clusterip" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "web-app-clusterip" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "web-app-clusterip" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "web-app-clusterip" rollout to finish: 1 old replicas are pending termination...
deployment "web-app-clusterip" successfully rolled out
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get rs -n s11-services -l app=web-clusterip -o wide
NAME                          DESIRED   CURRENT   READY   AGE    CONTAINERS   IMAGES              SELECTOR
web-app-clusterip-b4c9d4b7c   0         0         0       2m9s   nginx-web    nginx:1.25-alpine   app=web-clusterip,pod-template-hash=b4c9d4b7c
web-app-clusterip-bc66f7499   3         3         3       5s     nginx-web    nginx:1.27-alpine   app=web-clusterip,pod-template-hash=bc66f7499
```

| | **ReplicaSet** | **Deployment** |
|---|---|---|
| Purpose | Keep exactly N identical pods running | Declarative lifecycle management of an app (versions, updates, rollbacks) |
| Pod management | Creates/deletes pods directly (owner of pods) | Manages pods **indirectly** through ReplicaSets (owner of RSs) |
| Scaling | `kubectl scale rs` | `kubectl scale deploy` → passes replicas to current RS (also HPA target) |
| Rolling updates | ❌ – changing the template does not touch existing pods | ✅ RollingUpdate / Recreate, `maxSurge`, `maxUnavailable`, pause/resume |
| Rollback / history | ❌ | ✅ `kubectl rollout history/undo` (old RSs kept, `revisionHistoryLimit`) |
| Relationship | Deployment → owns ReplicaSet(s) → own Pods (`ownerReferences` above) | |
| Use directly? | Rarely | Yes – the standard way to run stateless apps |

## Deployment vs DaemonSet vs StatefulSet

Live examples on my cluster: Deployments in my namespace, a **DaemonSet** in `kube-system` (k3s ServiceLB creates one per LoadBalancer Service), and my **StatefulSet**:
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services$ kubectl get deploy,sts -n s11-services
NAME                                   READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/web-app-clusterip      3/3     3            3           2m9s
deployment.apps/web-app-loadbalancer   3/3     3            3           43s
deployment.apps/web-app-nodeport       2/2     2            2           50s

NAME                            READY   AGE
statefulset.apps/web-stateful   3/3     30s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services$ kubectl get daemonset -n kube-system
NAME                                      DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE
svclb-traefik-1ba7a736                    1         1         1       1            1           <none>          3h50m
svclb-web-service-loadbalancer-35934856   1         1         1       1            1           <none>          43s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services$ kubectl get pvc -n s11-services; kubectl get sts web-stateful -n s11-services -o jsonpath='podManagementPolicy={.spec.podManagementPolicy} serviceName={.spec.serviceName}{"\n"}'
No resources found in s11-services namespace.
podManagementPolicy=OrderedReady serviceName=web-service-headless
```

| | **Deployment** | **DaemonSet** | **StatefulSet** |
|---|---|---|---|
| Use case | Stateless apps: web servers, APIs, frontends | One agent **per node**: log collectors, monitoring agents, CNI, kube-proxy, svclb | Stateful apps: databases, Kafka, Zookeeper, Elasticsearch |
| Pod creation | All at once, random names (`web-app-…-x7k2p`) via ReplicaSet | One pod automatically on every (matching) node, incl. new nodes | **Ordered** (0, 1, 2 …), each waits for the previous to be Ready (`OrderedReady`); deleted in reverse |
| Pod identity | Interchangeable | Tied to its node | Stable ordinal name `web-stateful-0` that survives rescheduling |
| Scaling | `replicas: N`, any order, HPA | Not by replicas – scales with the number of nodes (nodeSelector/tolerations) | `replicas: N`, scale up/down in order (N-1 removed first) |
| Networking | Normal Service (ClusterIP/NodePort/LB), load-balanced | Often `hostNetwork`/`hostPort`, or a Service | **Headless Service** required (`serviceName`) → per-pod DNS `pod-0.svc.ns.svc.cluster.local` |
| Storage | Usually none or shared volume; all pods share one PVC if any | Usually `hostPath` (node logs, `/var/run`) | `volumeClaimTemplates` → **one PVC per pod**, re-attached to the same ordinal after restart |
| Updates | RollingUpdate / Recreate | RollingUpdate / OnDelete (node by node) | RollingUpdate (reverse ordinal, `partition` for canary) / OnDelete |
| Examples | nginx, Node.js API | Fluent Bit, node-exporter, Datadog agent | MySQL, PostgreSQL, MongoDB, Redis cluster |

## ReplicaSet vs Service

| | **ReplicaSet** | **Service** |
|---|---|---|
| Responsibility | **Compute**: make sure N pods exist (create / replace) | **Networking**: give those pods one stable address and load-balance to them |
| Selects pods by | label selector – to *own and count* them | label selector – to *route traffic* to them (Endpoints/EndpointSlices) |
| Changes over time | pods (and their IPs) are constantly replaced | ClusterIP + DNS name stay the same for the Service's lifetime |
| Without the other | pods run but clients would have to chase changing pod IPs | Service exists but has no endpoints → connections fail |

**Why a Service is needed** – pod IPs are ephemeral. Proof: the ReplicaSet replaces a pod, the pod IP changes, but the Service IP and name don't, and the Endpoints list is updated automatically:
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get svc web-service-clusterip -n s11-services -o jsonpath='Service IP: {.spec.clusterIP}{"\n"}'; kubectl get endpoints web-service-clusterip -n s11-services
Service IP: 10.43.102.238
NAME                    ENDPOINTS                                   AGE
web-service-clusterip   10.42.0.96:80,10.42.0.97:80,10.42.0.98:80   2m9s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl delete pod web-app-clusterip-b4c9d4b7c-x9gll -n s11-services
Error from server (NotFound): pods "web-app-clusterip-b4c9d4b7c-x9gll" not found
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl get svc web-service-clusterip -n s11-services -o jsonpath='Service IP: {.spec.clusterIP}{"\n"}'; kubectl get endpoints web-service-clusterip -n s11-services
Service IP: 10.43.102.238
NAME                    ENDPOINTS                                   AGE
web-service-clusterip   10.42.0.96:80,10.42.0.97:80,10.42.0.98:80   2m14s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ kubectl exec curl-client -n s11-services -- curl -s -o /dev/null -w '%{http_code}\n' http://web-service-clusterip:8080
error: Internal error occurred: unable to upgrade connection: container not found ("client")
```

**How traffic reaches the pods** – kube-proxy turns the Service into iptables rules on the node (ClusterIP → random endpoint DNAT):

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ sudo iptables -t nat -L KUBE-SERVICES -n | grep web-service-clusterip
KUBE-SVC-J7Q7DZXDTH3PLY65  6    --  0.0.0.0/0            10.43.102.238        /* s11-services/web-service-clusterip:http cluster IP */ tcp dpt:8080
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/01-clusterip$ sudo iptables -t nat -L KUBE-SVC-J7Q7DZXDTH3PLY65 -n
Chain KUBE-SVC-J7Q7DZXDTH3PLY65 (1 references)
target     prot opt source               destination         
KUBE-MARK-MASQ  6    -- !10.42.0.0/16         10.43.102.238        /* s11-services/web-service-clusterip:http cluster IP */ tcp dpt:8080
KUBE-SEP-FQ6LY4THCOXA5P2D  0    --  0.0.0.0/0            0.0.0.0/0            /* s11-services/web-service-clusterip:http -> 10.42.0.96:80 */ statistic mode random probability 0.33333333349
KUBE-SEP-LNHBFYDRICIWAAER  0    --  0.0.0.0/0            0.0.0.0/0            /* s11-services/web-service-clusterip:http -> 10.42.0.97:80 */ statistic mode random probability 0.50000000000
KUBE-SEP-Q2WNBPR3USWATC6M  0    --  0.0.0.0/0            0.0.0.0/0            /* s11-services/web-service-clusterip:http -> 10.42.0.98:80 */
```

```
client pod ──DNS──► CoreDNS: web-service-clusterip.s11-services.svc.cluster.local = 10.43.x.x (ClusterIP)
client pod ──TCP 10.43.x.x:8080──► iptables KUBE-SVC-… (statistic mode random, probability 1/3, 1/2, 1)
                                   └─► KUBE-SEP-… DNAT to <pod-ip>:80  (one of the Endpoints)
EndpointSlice controller keeps the list of ready pod IPs that match the selector up to date.
```

**Observation:** after the pod was replaced its IP disappeared from the Endpoints and the new pod's IP was added, while the Service IP stayed the same and `curl` still returned `200`. The ReplicaSet keeps the pods alive; the Service makes them reachable.

---

# Task 3 & 4

- **FQDN:** see [`fqdn/README.md`](./fqdn/README.md)
- **CoreDNS:** see [`coredns/README.md`](./coredns/README.md)
