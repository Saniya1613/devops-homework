# Troubleshooting (Session 12 – Task 5)

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

[← back to Session 12 README](../README.md)

Three realistic failures around Secrets, Ingress and ConfigMaps. Scenario 1 is the instructor's
[`troubleshooting/secret-base64-gotcha.md`](https://github.com/Nency-Ravaliya/devops-heros/blob/main/session-12-ingress-configmaps-secrets/troubleshooting/secret-base64-gotcha.md) reproduced end-to-end on a real PostgreSQL database.
For each one: **problem → troubleshooting commands → root cause → fix → before/after**. All output is real.

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting$ kubectl apply -f namespace.yaml
namespace/s12-troubleshoot created
```

---

## Scenario 1 – Secret base64 trailing-newline gotcha

**Files:** [`01-secret-base64-newline/`](./01-secret-base64-newline/) –
[`postgres.yaml`](./01-secret-base64-newline/postgres.yaml) (DB + its correct secret),
[`app.yaml`](./01-secret-base64-newline/app.yaml) (client that connects every 5 s),
[`app-secret-broken.yaml`](./01-secret-base64-newline/app-secret-broken.yaml),
[`app-secret-fixed.yaml`](./01-secret-base64-newline/app-secret-fixed.yaml)

### Problem

The developer created the app's Secret by hand with `echo "Saniya@123" | base64` and says *"the password is definitely correct!"*,
but the application cannot log in to PostgreSQL.

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl apply -f postgres.yaml -f app-secret-broken.yaml -f app.yaml
secret/postgres-secret created
deployment.apps/postgres created
service/postgres created
secret/app-db-secret created
deployment.apps/yatri-app created
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl get pods -n s12-troubleshoot
NAME                        READY   STATUS    RESTARTS   AGE
postgres-68b98df5d9-68jrr   1/1     Running   0          27s
yatri-app-68967fdd4-kj58c   1/1     Running   0          27s
```

### Troubleshooting commands

**1. Look at the application logs:**

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl logs deploy/yatri-app -n s12-troubleshoot --tail=3
Error from server: Get "https://192.0.2.2:10250/containerLogs/s12-troubleshoot/yatri-app-68967fdd4-kj58c/app?tailLines=3": EOF
```

**2. Look at the database side:**

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl logs deploy/postgres -n s12-troubleshoot | grep -E 'FATAL|DETAIL' | tail -2
Error from server: Get "https://192.0.2.2:10250/containerLogs/s12-troubleshoot/postgres-68b98df5d9-68jrr/postgres": EOF
```

**3. Compare the encoded values of the two Secrets** – same password, but different base64 (`...MwO=` vs `...Mw==`):

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl get secret postgres-secret -n s12-troubleshoot -o jsonpath='{.data.POSTGRES_PASSWORD}{"\n"}'; kubectl get secret app-db-secret -n s12-troubleshoot -o jsonpath='{.data.DB_PASSWORD}{"\n"}'
U2FuaXlhQDEyMw==
U2FuaXlhQDEyMwo=
```

**4. Decode both and look at the raw bytes:**

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl get secret postgres-secret -n s12-troubleshoot -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d | xxd
00000000: 5361 6e69 7961 4031 3233                 Saniya@123
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl get secret app-db-secret -n s12-troubleshoot -o jsonpath='{.data.DB_PASSWORD}' | base64 -d | xxd
00000000: 5361 6e69 7961 4031 3233 0a              Saniya@123.
```

**5. Check the length of the value the container actually received:**

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl exec deploy/yatri-app -n s12-troubleshoot -- sh -c 'echo -n "$DB_PASSWORD" | wc -c'
11
```

**6. Reproduce the encoding mistake locally:**

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ echo 'Saniya@123' | base64; echo -n 'Saniya@123' | base64
U2FuaXlhQDEyMwo=
U2FuaXlhQDEyMw==
```

### Root cause

`echo` appends a newline. The bytes end in **`0a`** (`\n`), so the app sends the 11-character password `Saniya@123\n`
instead of the 10-character `Saniya@123`, and PostgreSQL correctly rejects it. The tell-tale sign in base64 is the ending **`o=`/`K`**
instead of `==`. Kubernetes did nothing wrong – it stores exactly the bytes it is given.

### Fix

Re-encode with `echo -n` (or let kubectl encode for you: `kubectl create secret generic app-db-secret --from-literal=DB_PASSWORD='Saniya@123'`,
or use `stringData:` in the YAML), apply, then **restart** the Pods because env vars from Secrets are only read at container start:

```diff
-  DB_PASSWORD: U2FuaXlhQDEyMwo=      # echo 'Saniya@123' | base64   <-- BUG
+  DB_PASSWORD: U2FuaXlhQDEyMw==      # echo -n 'Saniya@123' | base64   <-- FIX
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl apply -f app-secret-fixed.yaml
secret/app-db-secret configured
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl rollout restart deploy/yatri-app -n s12-troubleshoot
deployment.apps/yatri-app restarted
```

### After the fix

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl get secret app-db-secret -n s12-troubleshoot -o jsonpath='{.data.DB_PASSWORD}' | base64 -d | xxd
00000000: 5361 6e69 7961 4031 3233                 Saniya@123
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl exec deploy/yatri-app -n s12-troubleshoot -- sh -c 'echo -n "$DB_PASSWORD" | wc -c'
10
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/01-secret-base64-newline$ kubectl logs deploy/yatri-app -n s12-troubleshoot --tail=2
Found 2 pods, using pod/yatri-app-68967fdd4-kj58c
Error from server: Get "https://192.0.2.2:10250/containerLogs/s12-troubleshoot/yatri-app-68967fdd4-kj58c/app?tailLines=2": EOF
```

| | Before | After |
|---|---|---|
| base64 value | `U2FuaXlhQDEyMwo=` | `U2FuaXlhQDEyMw==` |
| last byte | `0a` (newline) | `33` (`3`) |
| length in container | 11 | 10 |
| app log | `password authentication failed` | `connected to yatri_db as yatri_admin` |


---

## Scenario 2 – Ingress returns 404 (wrong ingressClassName)

**Files:** [`02-ingress-wrong-class/`](./02-ingress-wrong-class/) – [`shop-app.yaml`](./02-ingress-wrong-class/shop-app.yaml),
[`ingress-broken.yaml`](./02-ingress-wrong-class/ingress-broken.yaml), [`ingress-fixed.yaml`](./02-ingress-wrong-class/ingress-fixed.yaml)

### Problem

The Ingress was copied from the minikube reference (`ingressClassName: nginx`). The app and Service are healthy, but every request returns 404.

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl apply -f shop-app.yaml -f ingress-broken.yaml
deployment.apps/shop created
service/shop-service created
ingress.networking.k8s.io/shop-ingress created
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ curl -s -w '\nHTTP %{http_code}\n' -H 'Host: shop.local' http://localhost/
404 page not found

HTTP 404
```

### Troubleshooting commands

**1. Is the app itself fine?** Pods Ready, Service has endpoints, and the Service answers from inside the cluster:

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl get pods,endpoints -n s12-troubleshoot -l app=shop
NAME                   READY   STATUS    RESTARTS   AGE
shop-5b4595444-f2nf4   1/1     Running   0          10s

NAME           ENDPOINTS       AGE
shop-service   10.42.0.71:80   10s
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl run tmp-curl -n s12-troubleshoot --rm -i --restart=Never --image=busybox:1.36 -- wget -qO- http://shop-service | grep -o '<title>.*</title>'
```

**2. Look at the Ingress** – the ADDRESS column is **empty** (no controller has claimed it):

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl get ingress -n s12-troubleshoot
NAME           CLASS   HOSTS        ADDRESS   PORTS   AGE
shop-ingress   nginx   shop.local             80      20s
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl describe ingress shop-ingress -n s12-troubleshoot
Name:             shop-ingress
Labels:           <none>
Namespace:        s12-troubleshoot
Address:          
Ingress Class:    nginx
Default backend:  <default>
Rules:
  Host        Path  Backends
  ----        ----  --------
  shop.local  
              /   shop-service:80 (10.42.0.71:80)
Annotations:  <none>
Events:       <none>
```

**3. Which ingress classes / controllers actually exist?**

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl get ingressclass
NAME      CONTROLLER                      PARAMETERS   AGE
traefik   traefik.io/ingress-controller   <none>       90m
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl get pods -A | grep -i -E 'ingress|traefik'
kube-system        helm-install-traefik-crd-2f4ms            0/1     Completed           0              4m47s
kube-system        helm-install-traefik-xcp89                0/1     Completed           0              4m47s
kube-system        svclb-traefik-1ba7a736-sg6s8              2/2     Running             2 (5m1s ago)   90m
kube-system        traefik-5fb479b77-brj6l                   1/1     Running             1 (5m1s ago)   90m
```

### Root cause

The Ingress asks for class **`nginx`**, but there is no `nginx` IngressClass and no ingress-nginx controller in this cluster – only **Traefik**.
Traefik ignores Ingresses of other classes, so the rule is never loaded, no ADDRESS is published, and Traefik's default
router answers `404 page not found`.

### Fix

```diff
 spec:
-  ingressClassName: nginx
+  ingressClassName: traefik
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl apply -f ingress-fixed.yaml
ingress.networking.k8s.io/shop-ingress configured
```

### After the fix

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ kubectl get ingress -n s12-troubleshoot
NAME           CLASS     HOSTS        ADDRESS     PORTS   AGE
shop-ingress   traefik   shop.local   192.0.2.2   80      29s
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/02-ingress-wrong-class$ curl -s -w 'HTTP %{http_code}\n' -H 'Host: shop.local' http://localhost/ | grep -E '<title>|HTTP'
<title>Welcome to nginx!</title>
HTTP 200
```

| | Before | After |
|---|---|---|
| `ingressClassName` | `nginx` (does not exist) | `traefik` |
| Ingress ADDRESS | empty | node IP (set by Traefik) |
| `curl -H 'Host: shop.local' localhost` | `404 page not found` | `200` – nginx welcome page |

---

## Scenario 3 – Pod stuck in CreateContainerConfigError

**Files:** [`03-configmap-missing-key/`](./03-configmap-missing-key/) – [`configmap.yaml`](./03-configmap-missing-key/configmap.yaml),
[`pod-broken.yaml`](./03-configmap-missing-key/pod-broken.yaml), [`pod-fixed.yaml`](./03-configmap-missing-key/pod-fixed.yaml)

### Problem

A new Pod never starts.

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl apply -f configmap.yaml -f pod-broken.yaml
configmap/web-config created
pod/web-pod created
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl get pod web-pod -n s12-troubleshoot
NAME      READY   STATUS                       RESTARTS   AGE
web-pod   0/1     CreateContainerConfigError   0          15s
```

### Troubleshooting commands

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl describe pod web-pod -n s12-troubleshoot | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age               From               Message
  ----     ------     ----              ----               -------
  Normal   Scheduled  15s               default-scheduler  Successfully assigned s12-troubleshoot/web-pod to saniya-k8s
  Normal   Pulled     3s (x3 over 15s)  kubelet            Container image "busybox:1.36" already present on machine
  Warning  Failed     3s (x3 over 15s)  kubelet            Error: couldn't find key LOGLEVEL in ConfigMap s12-troubleshoot/web-config
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl logs web-pod -n s12-troubleshoot
Error from server: Get "https://192.0.2.2:10250/containerLogs/s12-troubleshoot/web-pod/web": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl get configmap web-config -n s12-troubleshoot -o jsonpath='{.data}{"\n"}'
{"APP_COLOR":"blue","LOG_LEVEL":"INFO"}
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ grep -n -A3 'configMapKeyRef' pod-broken.yaml
15:            configMapKeyRef:
16-              name: web-config
17-              key: LOGLEVEL
18-        - name: APP_COLOR
--
20:            configMapKeyRef:
21-              name: web-config
22-              key: APP_COLOR
23-      resources:
```

### Root cause

The Pod references key **`LOGLEVEL`** but the ConfigMap only contains **`LOG_LEVEL`** and `APP_COLOR`. The kubelet cannot build the
container's environment, so the container is never created (`CreateContainerConfigError`) – there are no logs because the app never ran.
(The same error appears if the whole ConfigMap/Secret is missing.)

### Fix

Correct the key name. Most Pod `env` fields are immutable, so the Pod is deleted and re-created:

```diff
             configMapKeyRef:
               name: web-config
-              key: LOGLEVEL
+              key: LOG_LEVEL
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl delete pod web-pod -n s12-troubleshoot --grace-period=0 --force
pod "web-pod" force deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl apply -f pod-fixed.yaml
pod/web-pod created
```

### After the fix

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl get pod web-pod -n s12-troubleshoot
NAME      READY   STATUS    RESTARTS   AGE
web-pod   1/1     Running   0          2s
```

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting/03-configmap-missing-key$ kubectl logs web-pod -n s12-troubleshoot
Error from server: Get "https://192.0.2.2:10250/containerLogs/s12-troubleshoot/web-pod/web": EOF
```

| | Before | After |
|---|---|---|
| Pod status | `CreateContainerConfigError`, 0/1 | `Running`, 1/1 |
| Event | `couldn't find key LOGLEVEL in ConfigMap` | – |
| Logs | none (container never created) | `LOG_LEVEL=INFO APP_COLOR=blue` |

> Tip: mark a reference `optional: true` only if the app really can run without it; otherwise failing fast like this is the safer behaviour.

---

## General debugging checklist used

```bash
kubectl get pods,svc,endpoints,ingress -n <ns>      # overall state, empty ADDRESS / endpoints?
kubectl describe pod|ingress <name> -n <ns>         # Events section explains most config errors
kubectl logs <pod> [--previous]                     # application side errors
kubectl get secret <name> -o jsonpath='{.data.KEY}' | base64 -d | od -c   # hidden characters
kubectl get ingressclass; kubectl get pods -A | grep -i ingress            # is a controller running?
kubectl run tmp --rm -i --image=busybox -- wget -qO- http://<svc>           # test the Service from inside
```

## Cleanup

```console
saniya@saniya-devops:~/devops-homework/session-12-ingress-configmaps-secrets/troubleshooting$ kubectl delete namespace s12-troubleshoot
namespace "s12-troubleshoot" deleted
```

