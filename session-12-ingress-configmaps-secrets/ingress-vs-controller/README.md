# Ingress vs Ingress Controller (Session 12 – Task 4)

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

[← back to Session 12 README](../README.md)

All output below is real, captured read-only from my k3s cluster while the Task 3 demo was running.

## 1. What is an Ingress?

An **Ingress** is a Kubernetes **API object** (`networking.k8s.io/v1`, kind `Ingress`) that describes **HTTP/HTTPS routing rules**
from outside the cluster to Services inside it:

- **host-based** rules (`yatri.local` vs `api.yatri.local`)
- **path-based** rules (`/` vs `/api`)
- optional **TLS** termination (certificate stored in a Secret)
- the class of controller that should implement it (`spec.ingressClassName`)

It is *only data* stored in etcd – it does not open any port and does not proxy a single packet by itself.

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get ingress -A
NAMESPACE   NAME            CLASS     HOSTS                         ADDRESS     PORTS   AGE
s12-demo    yatri-ingress   traefik   yatri.local,api.yatri.local   192.0.2.2   80      14s
s21-final   taskboard       traefik   taskboard.local               192.0.2.2   80      117s
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get ingress yatri-ingress -n s12-demo -o jsonpath='{.spec}' | python3 -m json.tool
{
    "ingressClassName": "traefik",
    "rules": [
        {
            "host": "yatri.local",
            "http": {
                "paths": [
                    {
                        "backend": {
                            "service": {
                                "name": "yatri-backend-service",
                                "port": {
                                    "number": 80
                                }
                            }
                        },
                        "path": "/api",
                        "pathType": "Prefix"
                    },
                    {
                        "backend": {
                            "service": {
                                "name": "yatri-frontend-service",
                                "port": {
                                    "number": 80
                                }
                            }
                        },
                        "path": "/",
                        "pathType": "Prefix"
                    }
                ]
            }
        },
        {
            "host": "api.yatri.local",
            "http": {
                "paths": [
                    {
                        "backend": {
                            "service": {
                                "name": "yatri-backend-service",
                                "port": {
                                    "number": 80
                                }
                            }
                        },
                        "path": "/",
                        "pathType": "Prefix"
                    }
                ]
            }
        }
    ]
}
```

## 2. What is an Ingress Controller?

An **Ingress Controller** is a **running application** (a Deployment/DaemonSet of reverse-proxy Pods) that:

1. **watches** the Kubernetes API for Ingress objects (and Services/Endpoints),
2. **translates** the rules into its own proxy configuration (Traefik routers, nginx.conf, HAProxy config, cloud ALB rules …),
3. **receives** the real external traffic (here on port 80/443 of the node through a `LoadBalancer` Service) and forwards it to the Pod IPs.

Kubernetes does **not** ship a controller in `kube-controller-manager` – one must be installed. k3s installs **Traefik** by default:

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get ingressclass
NAME      CONTROLLER                      PARAMETERS   AGE
traefik   traefik.io/ingress-controller   <none>       88m
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get ingressclass traefik -o yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"
    meta.helm.sh/release-name: traefik
    meta.helm.sh/release-namespace: kube-system
  generation: 1
  labels:
    app.kubernetes.io/instance: traefik-kube-system
    app.kubernetes.io/managed-by: Helm
    app.kubernetes.io/name: traefik
    helm.sh/chart: traefik-25.0.3_up25.0.0
  name: traefik
spec:
  controller: traefik.io/ingress-controller
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get deploy,pods -n kube-system -l app.kubernetes.io/name=traefik -o wide
NAME                      READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES                                    SELECTOR
deployment.apps/traefik   1/1     1            1           88m   traefik      rancher/mirrored-library-traefik:2.10.7   app.kubernetes.io/instance=traefik-kube-system,app.kubernetes.io/name=traefik

NAME                          READY   STATUS    RESTARTS        AGE   IP           NODE
pod/traefik-5fb479b77-brj6l   1/1     Running   1 (3m27s ago)   88m   10.42.0.17   saniya-k8s
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get deploy traefik -n kube-system -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
rancher/mirrored-library-traefik:2.10.7
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get svc traefik -n kube-system
NAME      TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)                      AGE
traefik   LoadBalancer   10.43.159.152   192.0.2.2     80:30804/TCP,443:31526/TCP   88m
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get deploy traefik -n kube-system -o jsonpath='{range .spec.template.spec.containers[0].args[*]}{@}{"\n"}{end}'
--entrypoints.metrics.address=:9100/tcp
--entrypoints.traefik.address=:9000/tcp
--entrypoints.web.address=:8000/tcp
--entrypoints.websecure.address=:8443/tcp
--providers.kubernetescrd
--providers.kubernetesingress
--providers.kubernetesingress.ingressendpoint.publishedservice=kube-system/traefik
--entrypoints.websecure.http.tls=true
```

The ADDRESS shown on my Ingress is filled in **by the controller** (Traefik publishes its LoadBalancer IP into `status.loadBalancer`) –
proof that a controller has picked the Ingress up:

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl get ingress yatri-ingress -n s12-demo -o jsonpath='{.status}{"\n"}'
{"loadBalancer":{"ingress":[{"ip":"192.0.2.2"}]}}
```

The request path is therefore: **client → node:80 → `svc/traefik` (kube-system) → Traefik pod → reads rule from `yatri-ingress` → Pod IP of `yatri-backend`**:

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ curl -s -o /dev/null -w 'HTTP %{http_code} from %{remote_ip}:%{remote_port}\n' -H 'Host: api.yatri.local' http://localhost/
HTTP 200 from 127.0.0.1:80
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/ingress-vs-controller$ kubectl logs -n kube-system deploy/traefik --tail=200 | grep -i -m3 -E 's12-demo|yatri' || echo '(no s12 entries in recent Traefik logs – access log is disabled by default)'
Error from server: Get "https://192.0.2.2:10250/containerLogs/kube-system/traefik-5fb479b77-brj6l/traefik?tailLines=200": EOF
(no s12 entries in recent Traefik logs – access log is disabled by default)
```

## 3. Difference

| | Ingress | Ingress Controller |
|---|---|---|
| Kind | API **resource** (YAML object) | **Software** running in Pods |
| Role | *What* should be routed *where* (rules) | *Does* the routing (reverse proxy / LB) |
| Lives in | Your app's namespace (`s12-demo`) | Usually its own namespace (`kube-system`, `ingress-nginx`) |
| Created by | App developer, one per app/team | Cluster admin, once per cluster |
| Handles traffic? | No | Yes – owns ports 80/443 |
| Without the other | Ingress is ignored (no ADDRESS, nothing listens) | Controller has no rules → 404 for every request |
| Examples | `yatri-ingress`, `shop-ingress` | Traefik (k3s), ingress-nginx (minikube addon), HAProxy, Contour, Kong, AWS Load Balancer Controller, GKE Ingress |
| Connected through | `spec.ingressClassName: traefik` | `IngressClass traefik` → `spec.controller: traefik.io/ingress-controller` |

## 4. Why both are required

- Kubernetes deliberately separates **intent** (Ingress) from **implementation** (controller). The same Ingress YAML can be served by
  Traefik on k3s, ingress-nginx on minikube or an AWS ALB in EKS – only `ingressClassName` (and controller-specific annotations) change.
- The **Ingress alone** is just a record in etcd: no process reads it → no port is opened → requests never reach the app.
- The **controller alone** is a proxy without routes: it accepts connections on 80/443 but has nowhere to send them (Traefik returns `404 page not found`).
- Together they give **one** external entry point (one IP / LoadBalancer) for **many** Services, with host/path routing and TLS, instead of one
  `LoadBalancer`/`NodePort` per Service.

Analogy: the Ingress is the **signboard at a junction** ("/api → backend, / → frontend"); the controller is the **traffic police officer**
who reads the signboard and actually directs every car.

Real demonstration: in [troubleshooting scenario 2](../troubleshooting/README.md#scenario-2--ingress-returns-404-wrong-ingressclassname) an Ingress with
`ingressClassName: nginx` (a controller that does not exist in this cluster) gets no ADDRESS and requests return 404 – changing it to
`traefik` makes it work immediately.
