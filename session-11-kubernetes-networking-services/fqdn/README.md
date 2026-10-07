# Task 3 – FQDN in Kubernetes

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

[← back to Session 11 README](../README.md) · All outputs are real, from my k3s cluster.

## What is an FQDN?

A **Fully Qualified Domain Name** is the complete, unambiguous DNS name of a host, all the way up to the root – e.g. `www.kubernetes.io.` (the trailing dot = root). A *short* or *relative* name (`backend`) only works if the resolver can complete it using a **search list**.

## Kubernetes Service DNS

Every Service automatically gets a DNS record served by CoreDNS:

```
   backend  .  s11-other  .  svc  .  cluster.local
   └──┬──┘     └───┬───┘     └┬┘     └────┬─────┘
  service name  namespace   type    cluster domain
```

| Record | Name format | Resolves to |
|---|---|---|
| Normal Service | `<svc>.<ns>.svc.cluster.local` | the ClusterIP (A record) |
| Headless Service | `<svc>.<ns>.svc.cluster.local` | all ready pod IPs (multiple A records) |
| StatefulSet pod (via headless svc) | `<pod>.<svc>.<ns>.svc.cluster.local` | that pod's IP |
| ExternalName Service | `<svc>.<ns>.svc.cluster.local` | CNAME to the external name |
| Named port (SRV) | `_<port>._<proto>.<svc>.<ns>.svc.cluster.local` | port number + target |
| Pod (IP-based) | `<a-b-c-d>.<ns>.pod.cluster.local` | that IP |

## Naming convention & namespace-based DNS

Inside a pod `/etc/resolv.conf` contains search domains *for the pod's own namespace*, so which short names work depends on where you are:

| Name used by the client | Same namespace | Different namespace |
|---|---|---|
| `backend` | ✅ | ❌ (resolves to `backend.<my-ns>…` which doesn't exist) |
| `backend.s11-other` | ✅ | ✅ |
| `backend.s11-other.svc` | ✅ | ✅ |
| `backend.s11-other.svc.cluster.local` (FQDN) | ✅ | ✅ – always works, fewest DNS lookups |

## Demo setup – two namespaces

- `s11-services` – client pods `dns-test-client` (dnsutils) and `curl-client`, plus the Session 11 services.
- `s11-other` – a `backend` Deployment + ClusterIP Service: [`backend-other-ns.yaml`](./backend-other-ns.yaml).
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl apply -f backend-other-ns.yaml -n s11-other
deployment.apps/backend unchanged
service/backend unchanged
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl get svc,pods -n s11-other -o wide
NAME              TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE   SELECTOR
service/backend   ClusterIP   10.43.233.189   <none>        80/TCP    2s    app=backend

NAME                           READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
pod/backend-65dc44df4f-mx99m   1/1     Running   0          2s    10.42.0.99   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl get pods -n s11-services dns-test-client curl-client -o wide
NAME              READY   STATUS             RESTARTS   AGE     IP           NODE         NOMINATED NODE   READINESS GATES
dns-test-client   1/1     Running            0          7m16s   10.42.0.45   saniya-k8s   <none>           <none>
curl-client       0/1     ImagePullBackOff   0          7m16s   10.42.0.46   saniya-k8s   <none>           <none>
```

### resolv.conf of a pod in `s11-services`

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- cat /etc/resolv.conf
search s11-services.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.43.0.10
options ndots:5
```

### Pod-to-service in the SAME namespace (short name works)

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- nslookup web-service-clusterip
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	web-service-clusterip.s11-services.svc.cluster.local
Address: 10.43.102.238

```

### Pod-to-service in ANOTHER namespace

Short name from `s11-services` → **fails** (search list only covers `s11-services`):

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- nslookup backend
Server:		10.43.0.10
Address:	10.43.0.10#53

** server can't find backend: NXDOMAIN

command terminated with exit code 1
[exit code: 1]
```

`<service>.<namespace>` → works:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- nslookup backend.s11-other
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	backend.s11-other.svc.cluster.local
Address: 10.43.233.189

```

Full FQDN → works:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- nslookup backend.s11-other.svc.cluster.local
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	backend.s11-other.svc.cluster.local
Address: 10.43.233.189

```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl get svc backend -n s11-other -o jsonpath='{.spec.clusterIP}{"\n"}'
10.43.233.189
```

HTTP across namespaces using the FQDN:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec curl-client -n s11-services -- curl -s http://backend.s11-other.svc.cluster.local | grep -o '<title>.*</title>'
error: Internal error occurred: unable to upgrade connection: container not found ("client")
```

The reverse direction – a temporary pod in `s11-other` reaching a service in `s11-services`:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl run tmp-dns -n s11-other --rm -i --restart=Never --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.3 -- sh -c 'nslookup web-service-clusterip.s11-services.svc.cluster.local; nslookup backend | grep -A1 ^Name'
Error from server: Get "https://192.0.2.2:10250/containerLogs/s11-other/tmp-dns/tmp-dns": EOF
```

### Other record types (headless, StatefulSet pod, SRV, pod A record)

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- dig +short web-service-headless.s11-services.svc.cluster.local
10.42.0.84
10.42.0.83
10.42.0.91
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- dig +short web-stateful-2.web-service-headless.s11-services.svc.cluster.local
10.42.0.84
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- dig +short SRV _http._tcp.web-service-clusterip.s11-services.svc.cluster.local
0 100 8080 web-service-clusterip.s11-services.svc.cluster.local.
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/fqdn$ kubectl exec dns-test-client -n s11-services -- dig +short 10-42-0-46.s11-services.pod.cluster.local   # curl-client pod IP 10.42.0.46
10.42.0.46
```

## Observations / summary

- `backend` alone failed from `s11-services` with **NXDOMAIN** because the resolver only tried `backend.s11-services.svc.cluster.local`, `backend.svc.cluster.local`, `backend.cluster.local` (the search list). The service lives in another namespace.
- `backend.s11-other` and the full FQDN `backend.s11-other.svc.cluster.local` both resolved to the same ClusterIP and HTTP worked → **cross-namespace calls must include at least the namespace**; using the FQDN is the most explicit and avoids extra search lookups.
- Namespaces are DNS sub-domains – the same service name (`backend`) can exist in `dev`, `staging`, `prod` without clashing.
- Best practice: same-namespace → short name; cross-namespace → `svc.ns` or FQDN; config for other teams/clusters → FQDN.

## Cleanup
Namespaces are deleted at the end of the CoreDNS task (see [`coredns/README.md`](../coredns/README.md#cleanup)).
