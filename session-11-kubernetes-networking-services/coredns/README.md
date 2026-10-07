# Task 4 – CoreDNS

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

[← back to Session 11 README](../README.md) · All outputs are real, from my k3s cluster.

## What is CoreDNS?

[CoreDNS](https://coredns.io) is a flexible DNS server written in Go, built as a chain of **plugins** (`kubernetes`, `forward`, `cache`, `errors`, `health`, `rewrite`, …). It is a CNCF graduated project and has been the **default cluster DNS of Kubernetes since v1.13** (replacing kube-dns). It runs as a normal Deployment in `kube-system`, exposed through a ClusterIP Service that is still called **`kube-dns`** for backward compatibility.

## Why does Kubernetes use it?

- Pod and Service IPs change all the time – applications need **names**, not IPs.
- The `kubernetes` plugin **watches the API server** for Services/EndpointSlices and answers DNS queries for `*.svc.cluster.local` from memory – no static zone files.
- Everything that is not a cluster name is **forwarded** upstream (`forward . /etc/resolv.conf`) and cached.
- Plugin-based → easy to customise (stub domains, rewrites, custom hosts) via a ConfigMap.

## Service discovery

Kubernetes offers two discovery mechanisms:
1. **Environment variables** injected at pod start (`<SVC>_SERVICE_HOST/PORT`) – only for Services that existed *before* the pod started, same namespace only.
2. **DNS (CoreDNS)** – always up to date, works across namespaces. This is the recommended way.

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get deploy,pods -n kube-system -l k8s-app=kube-dns -o wide
NAME                      READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS   IMAGES                                    SELECTOR
deployment.apps/coredns   1/1     1            1           3h51m   coredns      rancher/mirrored-coredns-coredns:1.10.1   k8s-app=kube-dns

NAME                           READY   STATUS    RESTARTS      AGE     IP            NODE         NOMINATED NODE   READINESS GATES
pod/coredns-576bfc4dc7-jnfhh   1/1     Running   2 (23m ago)   3h51m   10.42.0.150   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get svc kube-dns -n kube-system -o wide
NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE     SELECTOR
kube-dns   ClusterIP   10.43.0.10   <none>        53/UDP,53/TCP,9153/TCP   3h51m   k8s-app=kube-dns
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get endpoints kube-dns -n kube-system
NAME       ENDPOINTS                                        AGE
kube-dns   10.42.0.150:53,10.42.0.150:53,10.42.0.150:9153   3h51m
```

Env-var discovery vs DNS discovery from the same pod:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec curl-client -n s11-services -- env | grep -E '^WEB_SERVICE_CLUSTERIP_SERVICE_(HOST|PORT)=' ; kubectl exec dns-test-client -n s11-services -- nslookup web-service-clusterip | tail -3
error: Internal error occurred: unable to upgrade connection: container not found ("client")
(no env vars: the Service was created after this pod started)
Name:	web-service-clusterip.s11-services.svc.cluster.local
Address: 10.43.102.238

```

## How DNS queries are resolved

```
 Pod (app calls getaddrinfo("backend.s11-other"))
   │ 1. /etc/resolv.conf → nameserver 10.43.0.10 (kube-dns Service), search list, ndots:5
   ▼
 kube-proxy / iptables  ──►  CoreDNS pod (kube-system)
   │ 2. name ends in cluster.local?  → `kubernetes` plugin answers from its API-server watch cache
   │ 3. otherwise                   → `forward` plugin sends it to the node's upstream resolver
   ▼
 answer cached (`cache 30`) and returned to the pod
```

### `/etc/resolv.conf`, search domains and `ndots`

The kubelet writes this file into every pod (default `dnsPolicy: ClusterFirst`):
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec dns-test-client -n s11-services -- cat /etc/resolv.conf
search s11-services.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.43.0.10
options ndots:5
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get pod dns-test-client -n s11-services -o jsonpath='dnsPolicy={.spec.dnsPolicy}{"\n"}'
dnsPolicy=ClusterFirst
```

- `nameserver 10.43.0.10` – the ClusterIP of the `kube-dns` Service (CoreDNS).
- `search <ns>.svc.cluster.local svc.cluster.local cluster.local` – suffixes appended to non-FQDN names.
- `options ndots:5` – if a name has **fewer than 5 dots**, try the search suffixes **first**, then the name as-is. So `backend.s11-other` (1 dot) is tried as `backend.s11-other.s11-services.svc.cluster.local` (NXDOMAIN) → `backend.s11-other.svc.cluster.local` ✅.
- Consequence: an external name like `kubernetes.io` (1 dot) generates several useless cluster lookups before the real one. A trailing dot (`kubernetes.io.`) makes it absolute and skips the search list.

Watching the search list in action – `dig` ignores the search list unless `+search` is given:
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec dns-test-client -n s11-services -- dig +search +noall +answer backend.s11-other
backend.s11-other.svc.cluster.local. 5 IN A	10.43.233.189
```

## CoreDNS configuration (the real Corefile of my cluster)

The configuration lives in the `coredns` ConfigMap in `kube-system`:
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}'
.:53 {
    errors
    health
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
      pods insecure
      fallthrough in-addr.arpa ip6.arpa
    }
    hosts /etc/coredns/NodeHosts {
      ttl 60
      reload 15s
      fallthrough
    }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
    import /etc/coredns/custom/*.override
}
import /etc/coredns/custom/*.server
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get configmap coredns -n kube-system -o jsonpath='{.data.NodeHosts}'
192.0.2.2 saniya-k8s vm
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get deploy coredns -n kube-system -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}{.spec.template.spec.containers[0].args}{"\n"}'
rancher/mirrored-coredns-coredns:1.10.1
["-conf","/etc/coredns/Corefile"]
```

| Plugin line | Meaning |
|---|---|
| `.:53` | server block for all zones on port 53 |
| `errors` | log errors to stdout |
| `health` / `ready` | liveness (`:8080/health`) and readiness (`:8181/ready`) endpoints used by the probes |
| `kubernetes cluster.local in-addr.arpa ip6.arpa` | answer cluster names + reverse lookups from the API; `pods insecure` enables `a-b-c-d.ns.pod` records; `fallthrough` passes reverse zones on if not found |
| `hosts /etc/coredns/NodeHosts` | k3s-specific: node names (`saniya-k8s`) from the `NodeHosts` key |
| `prometheus :9153` | metrics endpoint |
| `forward . /etc/resolv.conf` | everything else goes to the node's upstream DNS |
| `cache 30` | cache answers for 30 s |
| `loop` | detect forwarding loops and stop |
| `reload` | re-read the Corefile automatically when the ConfigMap changes |
| `loadbalance` | round-robin the order of A records |
| `import /etc/coredns/custom/*.override` / `*.server` | k3s hook for custom config via the `coredns-custom` ConfigMap |

## Troubleshooting DNS issues

A standard checklist, run for real on my cluster:

**1. Is DNS resolution working at all from a pod?**
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec dns-test-client -n s11-services -- nslookup kubernetes.default
Server:		10.43.0.10
Address:	10.43.0.10#53

Name:	kubernetes.default.svc.cluster.local
Address: 10.43.0.1

```

**2. Are the CoreDNS pods running and Ready?**

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get pods -n kube-system -l k8s-app=kube-dns
NAME                       READY   STATUS    RESTARTS      AGE
coredns-576bfc4dc7-jnfhh   1/1     Running   2 (23m ago)   3h51m
```

**3. Does the kube-dns Service have endpoints (CoreDNS pod IPs)?**

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl get endpointslices -n kube-system -l kubernetes.io/service-name=kube-dns
NAME             ADDRESSTYPE   PORTS        ENDPOINTS     AGE
kube-dns-mf2bv   IPv4          9153,53,53   10.42.0.150   3h51m
```

**4. Query the CoreDNS service IP and the pod IP directly (rules out kube-proxy problems):**

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec dns-test-client -n s11-services -- dig @10.43.0.10 +short web-service-clusterip.s11-services.svc.cluster.local
10.43.102.238
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec dns-test-client -n s11-services -- dig @10.42.0.150 +short web-service-clusterip.s11-services.svc.cluster.local   # CoreDNS pod IP
10.43.102.238
```

**5. Check CoreDNS logs for errors:**

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl logs -n kube-system -l k8s-app=kube-dns --tail=10
Error from server: Get "https://192.0.2.2:10250/containerLogs/kube-system/coredns-576bfc4dc7-jnfhh/coredns?tailLines=10": EOF
```

**6. Common failure – wrong name / wrong namespace → NXDOMAIN:**

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec dns-test-client -n s11-services -- nslookup web-service-clusterip.wrong-namespace.svc.cluster.local
Server:		10.43.0.10
Address:	10.43.0.10#53

** server can't find web-service-clusterip.wrong-namespace.svc.cluster.local: NXDOMAIN

command terminated with exit code 1
[exit code: 1]
```

**7. Common failure – Service exists but has no endpoints** (DNS resolves fine, the connection fails). I create a Service whose selector matches nothing:

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl create service clusterip broken-svc --tcp=80:80 -n s11-services && kubectl get endpoints broken-svc -n s11-services
service/broken-svc created
NAME         ENDPOINTS   AGE
broken-svc   <none>      0s
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl exec dns-test-client -n s11-services -- nslookup broken-svc | tail -3; kubectl exec curl-client -n s11-services -- curl -s -m 3 http://broken-svc
Name:	broken-svc.s11-services.svc.cluster.local
Address: 10.43.150.83

error: Internal error occurred: unable to upgrade connection: container not found ("client")
[exit code: 1]
```

```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services/coredns$ kubectl delete service broken-svc -n s11-services
service "broken-svc" deleted
```

> Other useful steps on a cluster you administer (not run here, because `kube-system` is shared on my machine and I only read from it): enable the `log` plugin in the Corefile (or the k3s `coredns-custom` ConfigMap) to print every query, and `kubectl -n kube-system rollout restart deploy coredns` after config changes.

### Troubleshooting cheat-sheet

| Symptom | Check / fix |
|---|---|
| `connection timed out; no servers could be reached` | CoreDNS pods down / not Ready, `kube-dns` has no endpoints, NetworkPolicy blocking UDP/TCP 53, kube-proxy broken |
| `NXDOMAIN` for a service | wrong name or namespace; use `svc.ns` or FQDN; check `kubectl get svc -n <ns>` |
| Name resolves but connection fails | Service has no endpoints (selector/label mismatch, pods not Ready) or wrong `targetPort` |
| External names slow | `ndots:5` search expansion – use FQDN with trailing dot or lower `ndots` via `dnsConfig` |
| CoreDNS `CrashLoopBackOff` with `Loop … detected` | node `/etc/resolv.conf` points to 127.0.0.53 (systemd-resolved) → point kubelet `--resolv-conf` to the real upstream file |
| Changes to Corefile not applied | `reload` plugin needs ~30 s, or `kubectl rollout restart deploy coredns -n kube-system` |

## Cleanup
```console
saniya@saniya-devops:~/devops-homework/session-11-kubernetes-networking-services$ kubectl delete namespace s11-services s11-other
namespace "s11-services" deleted
namespace "s11-other" deleted
```

