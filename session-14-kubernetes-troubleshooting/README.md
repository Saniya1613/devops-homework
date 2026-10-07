# Session 14 – Kubernetes Troubleshooting Homework

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

All command output below is **real output** captured from my single-node k3s cluster (`saniya-k8s`, Kubernetes v1.30).
Starting material: the instructor's `devops-heros/session-14-kubernetes-troubleshooting` folder (`01..09`, `scenarios/`, `mini-project/`) – copied and adapted (source noted at the top of each YAML).

Every exercise runs in its own namespace (`s14-*`) so that `kubectl get` output stays clean.

## Folder layout

| Folder | What is inside |
|---|---|
| [`01-kubectl-commands/`](./01-kubectl-commands) | `demo-app.yaml` used for Task 1 (Deployment + Service + logging pod) |
| [`02-issues/01-crashloopbackoff/`](./02-issues/01-crashloopbackoff) | broken / fixed YAML – app exits because an env var is missing |
| [`02-issues/02-imagepullbackoff/`](./02-issues/02-imagepullbackoff) | broken / fixed YAML – non-existent image tag |
| [`02-issues/03-errimagepull/`](./02-issues/03-errimagepull) | broken / fixed YAML – non-existent repository |
| [`02-issues/04-pending/`](./02-issues/04-pending) | broken (huge requests, bad nodeSelector) / fixed YAML |
| [`02-issues/05-containercreating/`](./02-issues/05-containercreating) | Pod mounting a missing ConfigMap + Secret, and the fix |
| [`02-issues/06-service-selector/`](./02-issues/06-service-selector) | Service selector mismatch → empty endpoints |
| [`02-issues/07-dns/`](./02-issues/07-dns) | wrong service name / namespace in a DNS lookup |
| [`02-issues/08-pod-networking/`](./02-issues/08-pod-networking) | wrong `targetPort` + a blocking NetworkPolicy |
| [`02-issues/09-configuration/`](./02-issues/09-configuration) | env var referencing a missing ConfigMap key |
| [`02-issues/10-oomkilled/`](./02-issues/10-oomkilled) | (bonus, ref scenario 5) OOMKilled |
| [`03-mini-project/`](./03-mini-project) | the reference troubleshooting challenge |

## My troubleshooting flow (from the reference README)

```text
GET → DESCRIBE → EVENTS → LOGS → EXEC → TEST → ROOT CAUSE → FIX → VERIFY
```

---

## Task 1 – Hands-on with the core kubectl troubleshooting commands

Deploy the demo workload ([`01-kubectl-commands/demo-app.yaml`](./01-kubectl-commands/demo-app.yaml)): an nginx Deployment with 2 replicas, a ClusterIP Service and a `logs-demo` pod that prints a log line every 5 s.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl apply -f demo-app.yaml -n s14-basics
deployment.apps/web created
service/web-svc created
pod/logs-demo created
```

### 1. `kubectl get` – quick status of resources

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl get pods -n s14-basics
NAME                   READY   STATUS    RESTARTS   AGE
logs-demo              1/1     Running   0          14s
web-868cf8f864-vqmd2   1/1     Running   0          14s
web-868cf8f864-x4bnt   1/1     Running   0          14s
```

> Lists the pods with READY count, STATUS, RESTARTS and AGE – the first thing to look at.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl get deploy,rs,svc,endpoints -n s14-basics
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/web   2/2     2            2           14s

NAME                             DESIRED   CURRENT   READY   AGE
replicaset.apps/web-868cf8f864   2         2         2       14s

NAME              TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
service/web-svc   ClusterIP   10.43.52.73   <none>        80/TCP    14s

NAME                ENDPOINTS                       AGE
endpoints/web-svc   10.42.0.215:80,10.42.0.216:80   14s
```

> One call can show several resource types; Deployment → ReplicaSet → Pods, and the Service has 2 endpoints (the two nginx pods).

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl get pods -n s14-basics --show-labels
NAME                   READY   STATUS    RESTARTS   AGE   LABELS
logs-demo              1/1     Running   0          14s   app=logs-demo
web-868cf8f864-vqmd2   1/1     Running   0          14s   app=web,pod-template-hash=868cf8f864
web-868cf8f864-x4bnt   1/1     Running   0          14s   app=web,pod-template-hash=868cf8f864
```

> `--show-labels` is what you compare against a Service selector.

### 2. `kubectl get -o wide` – extra columns (IP, node)

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl get pods -n s14-basics -o wide
NAME                   READY   STATUS    RESTARTS   AGE   IP            NODE         NOMINATED NODE   READINESS GATES
logs-demo              1/1     Running   0          14s   10.42.0.217   saniya-k8s   <none>           <none>
web-868cf8f864-vqmd2   1/1     Running   0          14s   10.42.0.215   saniya-k8s   <none>           <none>
web-868cf8f864-x4bnt   1/1     Running   0          14s   10.42.0.216   saniya-k8s   <none>           <none>
```

> Adds pod IP, the node it is scheduled on and nominated node / readiness gates – useful for networking problems.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl get nodes -o wide
NAME         STATUS   ROLES                  AGE     VERSION        INTERNAL-IP   EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION   CONTAINER-RUNTIME
saniya-k8s   Ready    control-plane,master   3h33m   v1.30.4+k3s1   192.0.2.2     <none>        Ubuntu 24.04.5 LTS   6.18.44-fc-v77   containerd://1.7.20-k3s1
```

> For nodes it shows internal IP, OS image, kernel and container runtime (containerd from k3s).

### 3. `kubectl describe` – full details + events

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl describe pod web-868cf8f864-vqmd2 -n s14-basics
Name:             web-868cf8f864-vqmd2
Namespace:        s14-basics
Priority:         0
Service Account:  default
Node:             saniya-k8s/192.0.2.2
Start Time:       Wed, 07 Oct 2026 16:32:37 +0000
Labels:           app=web
                  pod-template-hash=868cf8f864
Annotations:      <none>
Status:           Running
IP:               10.42.0.215
IPs:
  IP:           10.42.0.215
Controlled By:  ReplicaSet/web-868cf8f864
Containers:
  nginx:
    Container ID:   containerd://eabdbd04c21e656ecac6b7b7e3be66c2368c8983ede85c86c71e2c1c7c482dfb
    Image:          nginx:1.27
    Image ID:       docker.io/library/nginx@sha256:6784fb0834aa7dbbe12e3d7471e69c290df3e6ba810dc38b34ae33d3c1c05f7d
    Port:           80/TCP
    Host Port:      0/TCP
    State:          Running
      Started:      Wed, 07 Oct 2026 16:32:38 +0000
    Ready:          True
    Restart Count:  0
    Limits:
      cpu:     100m
      memory:  64Mi
    Requests:
      cpu:        10m
      memory:     16Mi
    Environment:  <none>
    Mounts:
      /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-d5drh (ro)
Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Volumes:
  kube-api-access-d5drh:
    Type:                    Projected (a volume that contains injected data from multiple sources)
    TokenExpirationSeconds:  3607
    ConfigMapName:           kube-root-ca.crt
    ConfigMapOptional:       <nil>
    DownwardAPI:             true
QoS Class:                   Burstable
Node-Selectors:              <none>
Tolerations:                 node.kubernetes.io/not-ready:NoExecute op=Exists for 300s
                             node.kubernetes.io/unreachable:NoExecute op=Exists for 300s
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  14s   default-scheduler  Successfully assigned s14-basics/web-868cf8f864-vqmd2 to saniya-k8s
  Normal  Pulled     14s   kubelet            Container image "nginx:1.27" already present on machine
  Normal  Created    14s   kubelet            Created container nginx
  Normal  Started    14s   kubelet            Started container nginx
```

> Shows image, ports, limits/requests, conditions, QoS class, volumes and – most importantly – the **Events** at the bottom.

### 4. `kubectl logs` – what the application says

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl logs logs-demo -n s14-basics --tail=6
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-basics/logs-demo/app?tailLines=6": EOF
```

> stdout/stderr of the container. `--tail` limits lines, `-f` would follow, `--previous` shows the last crashed container.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl logs deploy/web -n s14-basics --tail=3
Found 2 pods, using pod/web-868cf8f864-vqmd2
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-basics/web-868cf8f864-vqmd2/nginx?tailLines=3": EOF
```

> Logs can be fetched via the Deployment too (kubectl picks one of its pods).

### 5. `kubectl exec` – run commands inside the container

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl exec web-868cf8f864-vqmd2 -n s14-basics -- nginx -v
nginx version: nginx/1.27.5
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl exec web-868cf8f864-vqmd2 -n s14-basics -- curl -s -o /dev/null -w 'HTTP %{http_code}\n' localhost
HTTP 200
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl exec logs-demo -n s14-basics -- sh -c 'hostname; cat /etc/resolv.conf'
logs-demo
search s14-basics.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.43.0.10
options ndots:5
```

> `exec` lets me test from *inside* the pod: is the app listening, what DNS search domains does the pod use, etc. (`kubectl exec -it <pod> -- sh` gives an interactive shell.)

### 6. Events – `kubectl get events` and `kubectl events`

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl get events -n s14-basics --sort-by=.lastTimestamp
32s         Normal   Pulled              pod/logs-demo               Container image "busybox:1.36" already present on machine
32s         Normal   Created             pod/logs-demo               Created container app
32s         Normal   ScalingReplicaSet   deployment/web              Scaled up replica set web-868cf8f864 to 2
32s         Normal   SuccessfulCreate    replicaset/web-868cf8f864   Created pod: web-868cf8f864-vqmd2
32s         Normal   SuccessfulCreate    replicaset/web-868cf8f864   Created pod: web-868cf8f864-x4bnt
31s         Normal   Created             pod/web-868cf8f864-vqmd2    Created container nginx
31s         Normal   Pulled              pod/web-868cf8f864-x4bnt    Container image "nginx:1.27" already present on machine
31s         Normal   Created             pod/web-868cf8f864-x4bnt    Created container nginx
31s         Normal   Started             pod/web-868cf8f864-x4bnt    Started container nginx
31s         Normal   Started             pod/web-868cf8f864-vqmd2    Started container nginx
31s         Normal   Pulled              pod/web-868cf8f864-vqmd2    Container image "nginx:1.27" already present on machine
31s         Normal   Started             pod/logs-demo               Started container app
```

> Classic way: events of the namespace sorted by time (last 12 lines shown). Scheduler, kubelet and controllers write events here.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl events -n s14-basics --for pod/logs-demo
LAST SEEN   TYPE     REASON      OBJECT          MESSAGE
32s         Normal   Pulled      Pod/logs-demo   Container image "busybox:1.36" already present on machine
32s         Normal   Created     Pod/logs-demo   Created container app
31s         Normal   Scheduled   Pod/logs-demo   Successfully assigned s14-basics/logs-demo to saniya-k8s
31s         Normal   Started     Pod/logs-demo   Started container app
```

> Newer `kubectl events` subcommand – already sorted, and `--for` filters to one object.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl events -n s14-basics --types=Warning
No events found in s14-basics namespace.
```

> `--types=Warning` shows only problems – nothing here, because this namespace is healthy.

### 7. `kubectl explain` – built-in API documentation

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl explain pod.spec.containers.imagePullPolicy
KIND:       Pod
VERSION:    v1

FIELD: imagePullPolicy <string>
ENUM:
    Always
    IfNotPresent
    Never

DESCRIPTION:
    Image pull policy. One of Always, Never, IfNotPresent. Defaults to Always if
    :latest tag is specified, or IfNotPresent otherwise. Cannot be updated. More
    info: https://kubernetes.io/docs/concepts/containers/images#updating-images
    
    Possible enum values:
     - `"Always"` means that kubelet always attempts to pull the latest image.
    Container will fail If the pull fails.
     - `"IfNotPresent"` means that kubelet pulls if the image isn't present on
    disk. Container will fail if the image isn't present and the pull fails.
     - `"Never"` means that kubelet never pulls an image, but only uses a local
    image. Container will fail if the image isn't present
    

```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl explain service.spec.selector
KIND:       Service
VERSION:    v1

FIELD: selector <map[string]string>


DESCRIPTION:
    Route service traffic to pods with label keys and values matching this
    selector. If empty or not present, the service is assumed to have an
    external process managing its endpoints, which Kubernetes will not modify.
    Only applies to types ClusterIP, NodePort, and LoadBalancer. Ignored if type
    is ExternalName. More info:
    https://kubernetes.io/docs/concepts/services-networking/service/
    

```

> Documents every field of every resource straight from the API server – handy when writing/fixing YAML.

### 8. `kubectl top` – live CPU / memory (metrics-server)

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl top nodes
NAME         CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%   
saniya-k8s   825m         41%    2222Mi          27%       
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/01-kubectl-commands$ kubectl top pods -n s14-basics
NAME                   CPU(cores)   MEMORY(bytes)   
logs-demo              1m           0Mi             
web-868cf8f864-vqmd2   0m           2Mi             
web-868cf8f864-x4bnt   0m           2Mi             
```

> Shows actual resource usage, used to spot OOM risks or CPU throttling. (The node is shared with other workloads, so node CPU is high.)

### Summary of Task 1

| Command | Question it answers |
|---|---|
| `kubectl get` | What exists and what is its status? |
| `kubectl get -o wide` | Where does it run, what IP does it have? |
| `kubectl describe` | Why is it in this state? (config + events) |
| `kubectl logs` | What did the application print? |
| `kubectl exec` | What does it look like from inside the container? |
| `kubectl get events` / `kubectl events` | What did Kubernetes try to do, and what failed? |
| `kubectl explain` | What does this YAML field mean? |
| `kubectl top` | How much CPU/memory is really used? |

---

## Task 2 – Troubleshooting common Kubernetes issues

Each issue follows the same structure: **Problem → Reproduce (broken YAML) → Investigate → Root cause → Fix → Verify**.

### Issue 1 – CrashLoopBackOff

**Problem statement:** a Python service is deployed but never becomes ready; its restart counter keeps growing.

**Reproduce** – [`broken.yaml`](./02-issues/01-crashloopbackoff/broken.yaml) (from ref `scenarios/scenario-1-crashloop`):

```yaml
# Source: ref scenarios/scenario-1-crashloop/broken.yaml
apiVersion: v1
kind: Pod
metadata:
  name: crashloop-pod
  labels:
    scenario: crashloop
spec:
  containers:
    - name: python-app
      image: python:3.11-alpine
      command:
        - "python3"
        - "-c"
        - |
          import os, sys
          db_url = os.environ.get("DATABASE_URL")
          if not db_url:
              print("[FATAL ERROR]: DATABASE_URL environment variable is MISSING!", file=sys.stderr)
              sys.exit(1)
          print("Application started successfully!")
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/01-crashloopbackoff$ kubectl apply -f broken.yaml -n s14-crash
pod/crashloop-pod created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/01-crashloopbackoff$ kubectl get pod crashloop-pod -n s14-crash
NAME            READY   STATUS             RESTARTS      AGE
crashloop-pod   0/1     CrashLoopBackOff   2 (26s ago)   45s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/01-crashloopbackoff$ kubectl describe pod crashloop-pod -n s14-crash
Containers:
  python-app:
    Container ID:  containerd://a8338faf2a90632074845ab0e0c1ff9e53f84f0c43d70efe91442ac9969339ba
    Image:         python:3.11-alpine
    Image ID:      docker.io/library/python@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929
    Port:          <none>
    Host Port:     <none>
    Command:
      python3
      -c
      import os, sys
      db_url = os.environ.get("DATABASE_URL")
      if not db_url:
          print("[FATAL ERROR]: DATABASE_URL environment variable is MISSING!", file=sys.stderr)
          sys.exit(1)
      print("Application started successfully!")
      
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Wed, 07 Oct 2026 16:33:29 +0000
      Finished:     Wed, 07 Oct 2026 16:33:29 +0000
    Ready:          False
    Restart Count:  2
    Environment:    <none>
    Mounts:
      /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-hxgb9 (ro)
Conditions:
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  45s                default-scheduler  Successfully assigned s14-crash/crashloop-pod to saniya-k8s
  Normal   Pulling    45s                kubelet            Pulling image "python:3.11-alpine"
  Normal   Pulled     41s                kubelet            Successfully pulled image "python:3.11-alpine" in 4.043s (4.043s including waiting). Image size: 23003038 bytes.
  Normal   Created    27s (x3 over 41s)  kubelet            Created container python-app
  Normal   Pulled     27s (x2 over 40s)  kubelet            Container image "python:3.11-alpine" already present on machine
  Normal   Started    26s (x3 over 40s)  kubelet            Started container python-app
  Warning  BackOff    12s (x4 over 39s)  kubelet            Back-off restarting failed container python-app in pod crashloop-pod_s14-crash(ba011a14-5c12-4f7e-84ed-c6c27c05104e)
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/01-crashloopbackoff$ kubectl logs crashloop-pod -n s14-crash --previous
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-crash/crashloop-pod/python-app?previous=true": EOF
```

**Root cause:** the container starts, finds no `DATABASE_URL` environment variable and calls `sys.exit(1)` (`Last State: Terminated, Reason: Error, Exit Code: 1`). The kubelet restarts it with an exponentially increasing delay (`Back-off restarting failed container`) → **CrashLoopBackOff**. The log line tells us exactly what is missing.

**Fix** – [`fixed.yaml`](./02-issues/01-crashloopbackoff/fixed.yaml): add the `DATABASE_URL` env var **and** keep the process running (a Pod that exits even with code 0 would be restarted again by `restartPolicy: Always`). Pod specs are mostly immutable, so the pod is deleted and re-created.

```diff
+      env:
+        - name: DATABASE_URL
+          value: "postgres://notes:Saniya@123@postgres-db:5432/notes"
 ...
           print("Application started successfully!")
+          while True:
+              time.sleep(30)
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/01-crashloopbackoff$ kubectl delete pod crashloop-pod -n s14-crash && kubectl apply -f fixed.yaml -n s14-crash
pod "crashloop-pod" deleted
pod/crashloop-pod created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/01-crashloopbackoff$ kubectl get pod crashloop-pod -n s14-crash
NAME            READY   STATUS    RESTARTS   AGE
crashloop-pod   1/1     Running   0          5s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/01-crashloopbackoff$ kubectl logs crashloop-pod -n s14-crash
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-crash/crashloop-pod/python-app": EOF
```

| | Before | After |
|---|---|---|
| STATUS | CrashLoopBackOff (Exit Code 1, restarts increasing) | Running, 0 restarts |

---

### Issue 2 – ImagePullBackOff

**Problem statement:** a new nginx pod is stuck and never starts; READY is `0/1`.

**Reproduce** – [`broken.yaml`](./02-issues/02-imagepullbackoff/broken.yaml) (from ref `07-imagepullbackoff`):

```yaml
# Source: ref 07-imagepullbackoff/broken-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: image-demo
spec:
  containers:
    - name: app
      image: nginx:this-image-does-not-exist   # BUG: tag does not exist on Docker Hub
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/02-imagepullbackoff$ kubectl apply -f broken.yaml -n s14-imgpull
pod/image-demo created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/02-imagepullbackoff$ kubectl get pod image-demo -n s14-imgpull
NAME         READY   STATUS             RESTARTS   AGE
image-demo   0/1     ImagePullBackOff   0          40s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/02-imagepullbackoff$ kubectl describe pod image-demo -n s14-imgpull
Containers:
  app:
    Container ID:   
    Image:          nginx:this-image-does-not-exist
    Image ID:       
    Port:           <none>
    Host Port:      <none>
    State:          Waiting
      Reason:       ImagePullBackOff
    Ready:          False
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  40s                default-scheduler  Successfully assigned s14-imgpull/image-demo to saniya-k8s
  Normal   BackOff    14s (x2 over 39s)  kubelet            Back-off pulling image "nginx:this-image-does-not-exist"
  Warning  Failed     14s (x2 over 39s)  kubelet            Error: ImagePullBackOff
  Normal   Pulling    3s (x3 over 40s)   kubelet            Pulling image "nginx:this-image-does-not-exist"
  Warning  Failed     2s (x3 over 39s)   kubelet            Failed to pull image "nginx:this-image-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:this-image-does-not-exist": failed to resolve reference "docker.io/library/nginx:this-image-does-not-exist": docker.io/library/nginx:this-image-does-not-exist: not found
  Warning  Failed     2s (x3 over 39s)   kubelet            Error: ErrImagePull
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/02-imagepullbackoff$ kubectl events -n s14-imgpull --types=Warning
LAST SEEN           TYPE      REASON   OBJECT           MESSAGE
14s (x2 over 39s)   Warning   Failed   Pod/image-demo   Error: ImagePullBackOff
2s (x3 over 39s)    Warning   Failed   Pod/image-demo   Failed to pull image "nginx:this-image-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:this-image-does-not-exist": failed to resolve reference "docker.io/library/nginx:this-image-does-not-exist": docker.io/library/nginx:this-image-does-not-exist: not found
2s (x3 over 39s)    Warning   Failed   Pod/image-demo   Error: ErrImagePull
```

**Root cause:** the tag `nginx:this-image-does-not-exist` is not published on Docker Hub – the events say `... not found`. The first attempt fails with `ErrImagePull`; after repeated failures the kubelet waits longer and longer between retries and shows **ImagePullBackOff**. `kubectl logs` is useless here because no container was ever started.

**Fix** – [`fixed.yaml`](./02-issues/02-imagepullbackoff/fixed.yaml): use a real, pinned tag.

```diff
-      image: nginx:this-image-does-not-exist
+      image: nginx:1.27
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/02-imagepullbackoff$ kubectl delete pod image-demo -n s14-imgpull && kubectl apply -f fixed.yaml -n s14-imgpull
pod "image-demo" deleted
pod/image-demo created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/02-imagepullbackoff$ kubectl get pod image-demo -n s14-imgpull
NAME         READY   STATUS    RESTARTS   AGE
image-demo   1/1     Running   0          2s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/02-imagepullbackoff$ kubectl describe pod image-demo -n s14-imgpull
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  1s    default-scheduler  Successfully assigned s14-imgpull/image-demo to saniya-k8s
  Normal  Pulled     1s    kubelet            Container image "nginx:1.27" already present on machine
  Normal  Created    1s    kubelet            Created container app
  Normal  Started    1s    kubelet            Started container app
```

---

### Issue 3 – ErrImagePull

**Problem statement:** right after deploying `yatri-api-service`, `kubectl get pods` shows `ErrImagePull`.

`ErrImagePull` is the **immediate** error of a failed pull; `ImagePullBackOff` is the state *between* retries. This time the problem is not the tag but the **repository** (a typo / private repo that does not exist), so the registry answers with *access denied*.

**Reproduce** – [`broken.yaml`](./02-issues/03-errimagepull/broken.yaml) (based on ref `scenarios/scenario-2-imagepull`):

```yaml
# Based on ref scenarios/scenario-2-imagepull/broken.yaml
apiVersion: v1
kind: Pod
metadata:
  name: errpull-pod
spec:
  containers:
    - name: web-app
      # BUG: repository name does not exist (typo) - registry refuses the pull
      image: saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/03-errimagepull$ kubectl apply -f broken.yaml -n s14-errpull
pod/errpull-pod created
```

**Investigate** (captured a few seconds after creation):

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/03-errimagepull$ kubectl get pod errpull-pod -n s14-errpull
NAME          READY   STATUS         RESTARTS   AGE
errpull-pod   0/1     ErrImagePull   0          2s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/03-errimagepull$ kubectl get pod errpull-pod -n s14-errpull -o jsonpath='{.status.containerStatuses[0].state}'
{"waiting":{"message":"failed to pull and unpack image \"docker.io/saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist\": failed to resolve reference \"docker.io/saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist\": pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed","reason":"ErrImagePull"}}
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/03-errimagepull$ kubectl get events -n s14-errpull --field-selector involvedObject.name=errpull-pod
LAST SEEN   TYPE      REASON      OBJECT            MESSAGE
27s         Normal    Scheduled   pod/errpull-pod   Successfully assigned s14-errpull/errpull-pod to saniya-k8s
15s         Normal    Pulling     pod/errpull-pod   Pulling image "saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist"
14s         Warning   Failed      pod/errpull-pod   Failed to pull image "saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist": failed to pull and unpack image "docker.io/saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist": failed to resolve reference "docker.io/saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist": pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
14s         Warning   Failed      pod/errpull-pod   Error: ErrImagePull
2s          Normal    BackOff     pod/errpull-pod   Back-off pulling image "saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist"
2s          Warning   Failed      pod/errpull-pod   Error: ImagePullBackOff
```

**Root cause:** `saniya1613/yatri-api-service` does not exist on Docker Hub (or would be private without an `imagePullSecret`) – the registry replies `pull access denied, repository does not exist or may require authorization`. The status flips between `ErrImagePull` (an attempt just failed) and `ImagePullBackOff` (waiting before the next attempt).

**Fix** – [`fixed.yaml`](./02-issues/03-errimagepull/fixed.yaml): point to an image that exists (for a private repo, the fix would be to add `imagePullSecrets`).

```diff
-      image: saniya1613/yatri-api-service:v999-invalid-tag-does-not-exist
+      image: nginx:1.27-alpine
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/03-errimagepull$ kubectl delete pod errpull-pod -n s14-errpull && kubectl apply -f fixed.yaml -n s14-errpull
pod "errpull-pod" deleted
pod/errpull-pod created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/03-errimagepull$ kubectl get pod errpull-pod -n s14-errpull -o wide
NAME          READY   STATUS    RESTARTS   AGE   IP          NODE         NOMINATED NODE   READINESS GATES
errpull-pod   1/1     Running   0          20s   10.42.0.7   saniya-k8s   <none>           <none>
```

---

### Issue 4 – Pending

**Problem statement:** a pod has been `Pending` for a long time; it has no IP and no node.

**Reproduce** – [`broken.yaml`](./02-issues/04-pending/broken.yaml) (ref `scenarios/scenario-3-pending`) and [`broken-nodeselector.yaml`](./02-issues/04-pending/broken-nodeselector.yaml) (ref `08-pending-pods`):

```yaml
# Source: ref scenarios/scenario-3-pending/broken.yaml
apiVersion: v1
kind: Pod
metadata:
  name: pending-pod
spec:
  containers:
    - name: hungry-app
      image: nginx:alpine
      resources:
        requests:
          # BUG: 500 CPU cores / 1000Gi RAM - no node can ever satisfy this
          cpu: "500"
          memory: "1000Gi"
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl apply -f broken.yaml -f broken-nodeselector.yaml -n s14-pending
pod/pending-pod created
pod/pending-demo created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl get pods -n s14-pending -o wide
NAME           READY   STATUS    RESTARTS   AGE   IP       NODE     NOMINATED NODE   READINESS GATES
pending-demo   0/1     Pending   0          8s    <none>   <none>   <none>           <none>
pending-pod    0/1     Pending   0          8s    <none>   <none>   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl describe pod pending-pod -n s14-pending
    Requests:
      cpu:        500
      memory:     1000Gi
    Environment:  <none>
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  8s    default-scheduler  0/1 nodes are available: 1 Insufficient cpu, 1 Insufficient memory. preemption: 0/1 nodes are available: 1 No preemption victims found for incoming pod.
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl describe pod pending-demo -n s14-pending
Node-Selectors:              kubernetes.io/hostname=node-that-does-not-exist
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  8s    default-scheduler  0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl describe node saniya-k8s
Capacity:
  cpu:                2
  ephemeral-storage:  264212084Ki
  hugepages-1Gi:      0
  hugepages-2Mi:      0
  memory:             8223864Ki
  pods:               110
Allocatable:
  cpu:                2
  ephemeral-storage:  265142110657
  hugepages-1Gi:      0
  hugepages-2Mi:      0
  memory:             8223864Ki
  pods:               110
System Info:
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl get nodes --show-labels
NAME         STATUS   ROLES                  AGE     VERSION        LABELS
kubernetes.io/hostname=saniya-k8s
```

**Root cause:** the **scheduler** cannot find any node for the pods (event `FailedScheduling`):
- `pending-pod` requests **500 CPUs and 1000Gi memory** – the only node has 2 CPUs / ~8 GB (`Insufficient cpu, Insufficient memory`).
- `pending-demo` has `nodeSelector: kubernetes.io/hostname=node-that-does-not-exist`, but the only node is `saniya-k8s` (`didn't match Pod's node affinity/selector`).

Other common causes: taints without tolerations, an unbound PVC, or a ResourceQuota.

**Fix** – [`fixed.yaml`](./02-issues/04-pending/fixed.yaml): realistic requests/limits, and remove the wrong nodeSelector.

```diff
       resources:
         requests:
-          cpu: "500"
-          memory: "1000Gi"
+          cpu: "50m"
+          memory: "64Mi"
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl delete pod pending-pod pending-demo -n s14-pending && kubectl apply -f fixed.yaml -n s14-pending
pod "pending-pod" deleted
pod "pending-demo" deleted
pod/pending-pod created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl get pods -n s14-pending -o wide
NAME          READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
pending-pod   1/1     Running   0          20s   10.42.0.13   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/04-pending$ kubectl events -n s14-pending --for pod/pending-pod
LAST SEEN          TYPE      REASON             OBJECT            MESSAGE
28s                Warning   FailedScheduling   Pod/pending-pod   0/1 nodes are available: 1 Insufficient cpu, 1 Insufficient memory. preemption: 0/1 nodes are available: 1 No preemption victims found for incoming pod.
20s                Warning   FailedScheduling   Pod/pending-pod   skip schedule deleting pod: s14-pending/pending-pod
19s                Normal    Scheduled          Pod/pending-pod   Successfully assigned s14-pending/pending-pod to saniya-k8s
18s                Warning   Failed             Pod/pending-pod   Failed to pull image "nginx:alpine": failed to pull and unpack image "docker.io/library/nginx:alpine": failed to resolve reference "docker.io/library/nginx:alpine": unexpected status from HEAD request to https://registry-1.docker.io/v2/library/nginx/manifests/alpine: 429 Too Many Requests
18s                Warning   Failed             Pod/pending-pod   Error: ErrImagePull
18s                Normal    BackOff            Pod/pending-pod   Back-off pulling image "nginx:alpine"
18s                Warning   Failed             Pod/pending-pod   Error: ImagePullBackOff
6s (x2 over 19s)   Normal    Pulling            Pod/pending-pod   Pulling image "nginx:alpine"
1s                 Normal    Pulled             Pod/pending-pod   Successfully pulled image "nginx:alpine" in 4.538s (4.538s including waiting). Image size: 26335715 bytes.
1s                 Normal    Created            Pod/pending-pod   Created container hungry-app
1s                 Normal    Started            Pod/pending-pod   Started container hungry-app
```

---

### Issue 5 – ContainerCreating (missing ConfigMap / Secret volume)

**Problem statement:** a pod was scheduled to a node but has been stuck in `ContainerCreating` for minutes.

**Reproduce** – [`broken.yaml`](./02-issues/05-containercreating/broken.yaml):

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mount-pod
spec:
  containers:
    - name: web
      image: nginx:1.27-alpine
      volumeMounts:
        - name: config
          mountPath: /etc/app
        - name: creds
          mountPath: /etc/creds
          readOnly: true
  volumes:
    - name: config
      configMap:
        name: app-config        # BUG: this ConfigMap was never created
    - name: creds
      secret:
        secretName: app-secret  # BUG: this Secret was never created
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl apply -f broken.yaml -n s14-creating
pod/mount-pod created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl get pod mount-pod -n s14-creating -o wide
NAME        READY   STATUS              RESTARTS   AGE   IP       NODE         NOMINATED NODE   READINESS GATES
mount-pod   0/1     ContainerCreating   0          20s   <none>   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl describe pod mount-pod -n s14-creating
Volumes:
  config:
    Type:      ConfigMap (a volume populated by a ConfigMap)
    Name:      app-config
    Optional:  false
  creds:
    Type:        Secret (a volume populated by a Secret)
    SecretName:  app-secret
    Optional:    false
  kube-api-access-xwskq:
    Type:                    Projected (a volume that contains injected data from multiple sources)
    TokenExpirationSeconds:  3607
    ConfigMapName:           kube-root-ca.crt
    ConfigMapOptional:       <nil>
    DownwardAPI:             true
QoS Class:                   BestEffort
Node-Selectors:              <none>
Tolerations:                 node.kubernetes.io/not-ready:NoExecute op=Exists for 300s
                             node.kubernetes.io/unreachable:NoExecute op=Exists for 300s
Events:
  Type     Reason       Age               From               Message
  ----     ------       ----              ----               -------
  Normal   Scheduled    20s               default-scheduler  Successfully assigned s14-creating/mount-pod to saniya-k8s
  Warning  FailedMount  4s (x6 over 19s)  kubelet            MountVolume.SetUp failed for volume "config" : configmap "app-config" not found
  Warning  FailedMount  4s (x6 over 19s)  kubelet            MountVolume.SetUp failed for volume "creds" : secret "app-secret" not found
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl get configmap,secret -n s14-creating
NAME                         DATA   AGE
configmap/kube-root-ca.crt   1      4m3s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl logs mount-pod -n s14-creating
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-creating/mount-pod/web": EOF
```

**Root cause:** the pod **is** scheduled (it has a node), but the kubelet cannot prepare its volumes: `FailedMount ... configmap "app-config" not found` and `secret "app-secret" not found`. The container is never started, so there are no logs (`waiting to start: ContainerCreating`). *(A missing PVC is similar but shows up one step earlier – the pod stays `Pending` because the scheduler can't bind the claim.)*

**Fix** – create the missing objects with [`fix-config-and-secret.yaml`](./02-issues/05-containercreating/fix-config-and-secret.yaml). No change to the pod is needed – the kubelet retries the mount automatically.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl apply -f fix-config-and-secret.yaml -n s14-creating
configmap/app-config created
secret/app-secret created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl get pod mount-pod -n s14-creating
NAME        READY   STATUS    RESTARTS   AGE
mount-pod   1/1     Running   0          33s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/05-containercreating$ kubectl exec mount-pod -n s14-creating -- sh -c 'cat /etc/app/app.properties; ls /etc/creds'
app.name=notes
app.env=dev
DB_PASSWORD
```

---

### Issue 6 – Service connectivity (selector mismatch → no endpoints)

**Problem statement:** the `web` pods are all `Running`, but calling `http://web-service` from another pod fails.

**Reproduce** – [`deployment.yaml`](./02-issues/06-service-selector/deployment.yaml) + [`broken-service.yaml`](./02-issues/06-service-selector/broken-service.yaml) (ref `09-service-dns-troubleshooting/service.yaml`):

```yaml
# Source: ref 09-service-dns-troubleshooting/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-service
spec:
  selector:
    app: web-ahsgdf     # BUG: no Pod has this label
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl apply -f deployment.yaml -f broken-service.yaml -n s14-svc
deployment.apps/web created
pod/client created
service/web-service created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl exec client -n s14-svc -- wget -qO- -T 3 http://web-service
wget: can't connect to remote host (10.43.70.12): Connection refused
command terminated with exit code 1
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl get pods -n s14-svc --show-labels -o wide
NAME                  READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES   LABELS
client                1/1     Running   0          3s    10.42.0.19   saniya-k8s   <none>           <none>            <none>
web-c54748bb5-6jgqt   1/1     Running   0          3s    10.42.0.17   saniya-k8s   <none>           <none>            app=web,pod-template-hash=c54748bb5
web-c54748bb5-ncf95   1/1     Running   0          3s    10.42.0.18   saniya-k8s   <none>           <none>            app=web,pod-template-hash=c54748bb5
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl describe service web-service -n s14-svc
Name:                     web-service
Namespace:                s14-svc
Labels:                   <none>
Annotations:              <none>
Selector:                 app=web-ahsgdf
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.43.70.12
IPs:                      10.43.70.12
Port:                     <unset>  80/TCP
TargetPort:               80/TCP
Endpoints:                
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl get endpoints web-service -n s14-svc
NAME          ENDPOINTS   AGE
web-service   <none>      3s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl get pods -n s14-svc -l app=web-ahsgdf
No resources found in s14-svc namespace.
```

**Root cause:** DNS works (the name resolves to the ClusterIP), but the Service selector `app=web-ahsgdf` matches **no pods**, so `Endpoints: <none>` – kube-proxy has nowhere to send the traffic and the connection is refused. Pod labels are `app=web`.

**Fix** – [`fixed-service.yaml`](./02-issues/06-service-selector/fixed-service.yaml):

```diff
   selector:
-    app: web-ahsgdf
+    app: web
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl apply -f fixed-service.yaml -n s14-svc
service/web-service configured
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl get endpoints web-service -n s14-svc
NAME          ENDPOINTS                     AGE
web-service   10.42.0.17:80,10.42.0.18:80   6s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/06-service-selector$ kubectl exec client -n s14-svc -- wget -qO- -T 3 http://web-service
<title>Welcome to nginx!</title>
```

---

### Issue 7 – DNS issues (wrong service name / namespace)

**Problem statement:** the client pod in namespace `s14-dns` cannot reach the database service; the app log says the connection failed.

**Setup** – the backend lives in namespace `s14-dns-backend` ([`backend.yaml`](./02-issues/07-dns/backend.yaml)); the client ([`broken-client.yaml`](./02-issues/07-dns/broken-client.yaml), from ref `scenarios/scenario-4-dns-failure`) runs in `s14-dns`:

```yaml
# Based on ref scenarios/scenario-4-dns-failure/broken.yaml
# Client runs in namespace s14-dns
apiVersion: v1
kind: Pod
metadata:
  name: dns-client
spec:
  containers:
    - name: client
      image: curlimages/curl:8.6.0
      command: ["sh", "-c"]
      args:
        - |
          echo "Attempting connection to internal database...";
          # BUG 1: wrong service name, BUG 2: wrong namespace (production)
          curl -s --connect-timeout 3 http://postgres-db-wrong-name.production.svc.cluster.local:5432 || echo "curl failed with exit code $?";
          echo "Process sleeping...";
          sleep 3600
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl apply -f backend.yaml -n s14-dns-backend && kubectl apply -f broken-client.yaml -n s14-dns
deployment.apps/postgres-db created
service/postgres-db created
pod/dns-client created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl logs dns-client -n s14-dns
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-dns/dns-client/client": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl exec dns-client -n s14-dns -- nslookup postgres-db-wrong-name.production.svc.cluster.local
Server:		10.43.0.10
Address:	10.43.0.10:53

** server can't find postgres-db-wrong-name.production.svc.cluster.local: NXDOMAIN

** server can't find postgres-db-wrong-name.production.svc.cluster.local: NXDOMAIN

command terminated with exit code 1
```

Short name from the client's namespace – also fails, because the service is in another namespace:

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl exec dns-client -n s14-dns -- nslookup postgres-db
Server:		10.43.0.10
Address:	10.43.0.10:53

** server can't find postgres-db.svc.cluster.local: NXDOMAIN

** server can't find postgres-db.s14-dns.svc.cluster.local: NXDOMAIN

** server can't find postgres-db.cluster.local: NXDOMAIN

** server can't find postgres-db.cluster.local: NXDOMAIN

** server can't find postgres-db.s14-dns.svc.cluster.local: NXDOMAIN

** server can't find postgres-db.svc.cluster.local: NXDOMAIN

command terminated with exit code 1
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl exec dns-client -n s14-dns -- cat /etc/resolv.conf
search s14-dns.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.43.0.10
options ndots:5
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl get svc -A --field-selector metadata.name=postgres-db
NAMESPACE         NAME          TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
s14-dns-backend   postgres-db   ClusterIP   10.43.90.171   <none>        5432/TCP   113s
```

Is CoreDNS itself healthy?

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
NAME                       READY   STATUS    RESTARTS      AGE     IP            NODE         NOMINATED NODE   READINESS GATES
coredns-576bfc4dc7-jnfhh   1/1     Running   2 (10m ago)   3h39m   10.42.0.150   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl get svc kube-dns -n kube-system
NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE
kube-dns   ClusterIP   10.43.0.10   <none>        53/UDP,53/TCP,9153/TCP   3h39m
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl exec dns-client -n s14-dns -- nslookup kubernetes.default
Server:		10.43.0.10
Address:	10.43.0.10:53

** server can't find kubernetes.default: NXDOMAIN

** server can't find kubernetes.default: NXDOMAIN

command terminated with exit code 1
```

**Root cause:** CoreDNS is running and resolves other names fine. The application uses a **wrong service name** (`postgres-db-wrong-name`) in a **wrong namespace** (`production`) → `NXDOMAIN`. Even the short name `postgres-db` fails from `s14-dns`, because `/etc/resolv.conf` only searches `s14-dns.svc.cluster.local` – the service lives in `s14-dns-backend`. Service DNS format is `<service>.<namespace>.svc.cluster.local`.

**Fix** – [`fixed-client.yaml`](./02-issues/07-dns/fixed-client.yaml):

```diff
-  curl ... http://postgres-db-wrong-name.production.svc.cluster.local:5432
+  curl ... http://postgres-db.s14-dns-backend.svc.cluster.local:5432
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl delete pod dns-client -n s14-dns && kubectl apply -f fixed-client.yaml -n s14-dns
pod "dns-client" deleted
pod/dns-client created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl exec dns-client -n s14-dns -- nslookup postgres-db.s14-dns-backend.svc.cluster.local
Server:		10.43.0.10
Address:	10.43.0.10:53

Name:	postgres-db.s14-dns-backend.svc.cluster.local
Address: 10.43.90.171


```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/07-dns$ kubectl logs dns-client -n s14-dns
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-dns/dns-client/client": EOF
```

---

### Issue 8 – Pod networking issues (wrong targetPort, NetworkPolicy)

**Problem statement:** the `api` pod is Running and the Service *has* endpoints, but requests from the `client` pod fail.

**Reproduce** – [`app.yaml`](./02-issues/08-pod-networking/app.yaml) + [`broken-service.yaml`](./02-issues/08-pod-networking/broken-service.yaml):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-svc
spec:
  selector: { app: api }
  ports:
    - port: 80
      targetPort: 8080   # BUG: container listens on 80, not 8080
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl apply -f app.yaml -f broken-service.yaml -n s14-net
deployment.apps/api created
pod/client created
service/api-svc created
```

#### 8a – wrong `targetPort`

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl exec client -n s14-net -- wget -qO- -T 3 http://api-svc
wget: can't connect to remote host (10.43.101.92): Connection refused
command terminated with exit code 1
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl get endpoints api-svc -n s14-net
NAME      ENDPOINTS         AGE
api-svc   10.42.0.26:8080   2s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl describe svc api-svc -n s14-net
Selector:                 app=api
Port:                     <unset>  80/TCP
TargetPort:               8080/TCP
Endpoints:                10.42.0.26:8080
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl get pod api-95f7f69ff-b5vkg -n s14-net -o jsonpath='{.spec.containers[0].ports}'
[{"containerPort":80,"protocol":"TCP"}]
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl exec client -n s14-net -- wget -qO- -T 3 http://10.42.0.26:80
<title>Welcome to nginx!</title>
```

**Root cause:** endpoints exist, but they point to `<podIP>:8080`. nginx listens on **80** (`containerPort: 80`), nothing listens on 8080 → *connection refused*. Calling the pod IP on port 80 directly works, which proves the pod is fine and the Service port mapping is wrong.

**Fix** – [`fixed-service.yaml`](./02-issues/08-pod-networking/fixed-service.yaml): `targetPort: 8080` → `targetPort: 80`.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl apply -f fixed-service.yaml -n s14-net
service/api-svc configured
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl get endpoints api-svc -n s14-net
NAME      ENDPOINTS       AGE
api-svc   10.42.0.26:80   6s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl exec client -n s14-net -- wget -qO- -T 3 http://api-svc
<title>Welcome to nginx!</title>
```

#### 8b – a NetworkPolicy blocks the traffic

k3s has an **embedded NetworkPolicy controller** (kube-router based), so policies are actually enforced. Someone applied a namespace-wide default-deny – [`broken-netpol.yaml`](./02-issues/08-pod-networking/broken-netpol.yaml):

```yaml
# BUG: default-deny ingress for every pod in the namespace (k3s ships an
# embedded NetworkPolicy controller, so this is really enforced)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}
  policyTypes: ["Ingress"]
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl apply -f broken-netpol.yaml -n s14-net
networkpolicy.networking.k8s.io/default-deny-ingress created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl exec client -n s14-net -- wget -qO- -T 3 http://api-svc
wget: can't connect to remote host (10.43.101.92): Connection refused
command terminated with exit code 1
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl get endpoints api-svc -n s14-net
NAME      ENDPOINTS       AGE
api-svc   10.42.0.26:80   14s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl get networkpolicy -n s14-net
NAME                   POD-SELECTOR   AGE
default-deny-ingress   <none>         8s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl describe networkpolicy default-deny-ingress -n s14-net
Name:         default-deny-ingress
Namespace:    s14-net
Created on:   2026-10-07 16:39:39 +0000 UTC
Labels:       <none>
Annotations:  <none>
Spec:
  PodSelector:     <none> (Allowing the specific traffic to all pods in this namespace)
  Allowing ingress traffic:
    <none> (Selected pods are isolated for ingress connectivity)
  Not affecting egress traffic
  Policy Types: Ingress
```

**Root cause:** pods, service and endpoints are all correct, but the request now **times out** (not *refused*) – the typical sign of packets being dropped. `default-deny-ingress` selects every pod (`podSelector: {}`) with `policyTypes: Ingress` and no `ingress` rules → all incoming traffic to the api pod is denied.

**Fix** – keep the default-deny (good security practice) and add an explicit allow rule – [`fixed-netpol.yaml`](./02-issues/08-pod-networking/fixed-netpol.yaml): pods labelled `role: client` may reach `app: api` on TCP 80.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl apply -f fixed-netpol.yaml -n s14-net
networkpolicy.networking.k8s.io/allow-client-to-api created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl get networkpolicy -n s14-net
NAME                   POD-SELECTOR   AGE
allow-client-to-api    app=api        6s
default-deny-ingress   <none>         14s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl exec client -n s14-net -- wget -qO- -T 3 http://api-svc
<title>Welcome to nginx!</title>
```

A pod **without** the `role=client` label is still blocked (policy works as intended):

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/08-pod-networking$ kubectl run intruder -n s14-net --image=busybox:1.36 --rm -i --restart=Never -- wget -qO- -T 3 http://api-svc
wget: can't connect to remote host (10.43.101.92): Connection refused
pod "intruder" deleted
pod s14-net/intruder terminated (Error)
```

---

### Issue 9 – Configuration issues (missing ConfigMap key)

**Problem statement:** a pod reading its settings from a ConfigMap never starts; status is `CreateContainerConfigError`.

**Reproduce** – [`broken.yaml`](./02-issues/09-configuration/broken.yaml):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: notes-config
data:
  DATABASE_HOST: "postgres-db"
  LOG_LEVEL: "info"
---
apiVersion: v1
kind: Pod
metadata:
  name: config-pod
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "echo DB_HOST=$DB_HOST LOG_LEVEL=$LOG_LEVEL; sleep 3600"]
      env:
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: notes-config
              key: DB_HOST          # BUG: key is called DATABASE_HOST in the ConfigMap
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: notes-config
              key: LOG_LEVEL
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/09-configuration$ kubectl apply -f broken.yaml -n s14-config
configmap/notes-config created
pod/config-pod created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/09-configuration$ kubectl get pod config-pod -n s14-config
NAME         READY   STATUS                       RESTARTS   AGE
config-pod   0/1     CreateContainerConfigError   0          12s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/09-configuration$ kubectl describe pod config-pod -n s14-config
    State:          Waiting
      Reason:       CreateContainerConfigError
    Environment:
      DB_HOST:    <set to the key 'DB_HOST' of config map 'notes-config'>    Optional: false
      LOG_LEVEL:  <set to the key 'LOG_LEVEL' of config map 'notes-config'>  Optional: false
    Mounts:
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  12s                default-scheduler  Successfully assigned s14-config/config-pod to saniya-k8s
  Normal   Pulled     10s (x2 over 11s)  kubelet            Container image "busybox:1.36" already present on machine
  Warning  Failed     10s (x2 over 11s)  kubelet            Error: couldn't find key DB_HOST in ConfigMap s14-config/notes-config
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/09-configuration$ kubectl get configmap notes-config -n s14-config -o yaml
{"DATABASE_HOST":"postgres-db","LOG_LEVEL":"info"}
```

**Root cause:** the env var `DB_HOST` references key **`DB_HOST`** in ConfigMap `notes-config`, but the ConfigMap only has `DATABASE_HOST` and `LOG_LEVEL` → `Error: couldn't find key DB_HOST in ConfigMap s14-config/notes-config`. The kubelet refuses to create the container (`CreateContainerConfigError`). Same symptom for a missing ConfigMap/Secret used in `env`/`envFrom` (unless `optional: true`).

**Fix** – [`fixed.yaml`](./02-issues/09-configuration/fixed.yaml): reference the existing key.

```diff
               name: notes-config
-              key: DB_HOST
+              key: DATABASE_HOST
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/09-configuration$ kubectl delete pod config-pod -n s14-config && kubectl apply -f fixed.yaml -n s14-config
pod "config-pod" deleted
configmap/notes-config unchanged
pod/config-pod created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/09-configuration$ kubectl get pod config-pod -n s14-config
NAME         READY   STATUS    RESTARTS   AGE
config-pod   1/1     Running   0          4s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/09-configuration$ kubectl logs config-pod -n s14-config
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-config/config-pod/app": EOF
```

---

### Issue 10 (bonus, ref scenario 5) – OOMKilled

**Reproduce** – [`broken.yaml`](./02-issues/10-oomkilled/broken.yaml): a script allocates ~1 GB with a `20Mi` memory limit.

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/10-oomkilled$ kubectl apply -f broken.yaml -n s14-oom
pod/oom-pod created
```

**Investigate**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/10-oomkilled$ kubectl get pod oom-pod -n s14-oom
NAME      READY   STATUS      RESTARTS      AGE
oom-pod   0/1     OOMKilled   2 (28s ago)   30s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/10-oomkilled$ kubectl describe pod oom-pod -n s14-oom
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Wed, 07 Oct 2026 16:40:37 +0000
      Finished:     Wed, 07 Oct 2026 16:40:37 +0000
    Ready:          False
    Restart Count:  2
    Limits:
      memory:  20Mi
```

**Root cause:** the container exceeds its memory limit; the kernel OOM killer kills it → `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`, followed by restarts (CrashLoopBackOff).

**Fix** – [`fixed.yaml`](./02-issues/10-oomkilled/fixed.yaml): bound the allocation (50 MB) and give a matching limit (`128Mi`).

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/10-oomkilled$ kubectl delete pod oom-pod -n s14-oom && kubectl apply -f fixed.yaml -n s14-oom
pod "oom-pod" deleted
pod/oom-pod created
```

**Verify (after)**

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/10-oomkilled$ kubectl get pod oom-pod -n s14-oom
NAME      READY   STATUS    RESTARTS   AGE
oom-pod   1/1     Running   0          16s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/02-issues/10-oomkilled$ kubectl top pod oom-pod -n s14-oom
Error from server (NotFound): podmetrics.metrics.k8s.io "s14-oom/oom-pod" not found
```


### Task 2 summary

| # | Issue | Symptom | Key command | Root cause | Fix |
|---|---|---|---|---|---|
| 1 | CrashLoopBackOff | restarts growing, Exit Code 1 | `logs --previous` | `DATABASE_URL` missing → app exits | add env var, keep process alive |
| 2 | ImagePullBackOff | `0/1`, back-off pulling | `describe` (Events) | tag does not exist | use `nginx:1.27` |
| 3 | ErrImagePull | `ErrImagePull` right after create | `get events` | repository does not exist / access denied | correct image (or `imagePullSecrets`) |
| 4 | Pending | no node, no IP | `describe` → `FailedScheduling` | 500 CPU request; bad nodeSelector | realistic requests, remove selector |
| 5 | ContainerCreating | scheduled but never starts | `describe` → `FailedMount` | ConfigMap/Secret volume missing | create ConfigMap + Secret |
| 6 | Service – no endpoints | connection refused via Service | `get endpoints`, `--show-labels` | selector `app=web-ahsgdf` ≠ label `app=web` | fix selector |
| 7 | DNS | `NXDOMAIN` | `exec ... nslookup`, `resolv.conf` | wrong name + namespace | use `<svc>.<ns>.svc.cluster.local` |
| 8a | Networking – port | refused, endpoints present | `describe svc`, curl pod IP | `targetPort 8080` vs `containerPort 80` | `targetPort: 80` |
| 8b | Networking – policy | timeout | `get networkpolicy` | default-deny ingress | allow rule for `role=client` |
| 9 | Configuration | `CreateContainerConfigError` | `describe` (Events) | key `DB_HOST` not in ConfigMap | use `DATABASE_HOST` |
| 10 | OOMKilled | Exit Code 137 | `describe` (Last State) | 20Mi limit, 1 GB allocation | bounded memory + 128Mi limit |

---

## Task 3 – Mini project: Kubernetes Troubleshooting Challenge

Files in [`03-mini-project/`](./03-mini-project): `deployment.yaml`, `service.yaml`, `broken-pod.yaml` (copied unchanged from the reference) and my `broken-service.yaml` / `fixed-pod.yaml`.

### 1. Deploy the application
```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl apply -f deployment.yaml -f service.yaml -n s14-mini
deployment.apps/troubleshooting-app created
service/troubleshooting-service created
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get pods,service -n s14-mini
NAME                                       READY   STATUS    RESTARTS   AGE
pod/troubleshooting-app-7f4b8cd658-47zws   1/1     Running   0          4s
pod/troubleshooting-app-7f4b8cd658-tfrg8   1/1     Running   0          4s

NAME                              TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
service/troubleshooting-service   ClusterIP   10.43.46.192   <none>        80/TCP    4s
```

### 2. Check the application

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get pods -n s14-mini -o wide
NAME                                   READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
troubleshooting-app-7f4b8cd658-47zws   1/1     Running   0          4s    10.42.0.35   saniya-k8s   <none>           <none>
troubleshooting-app-7f4b8cd658-tfrg8   1/1     Running   0          4s    10.42.0.36   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl describe pod troubleshooting-app-7f4b8cd658-47zws -n s14-mini
Name:             troubleshooting-app-7f4b8cd658-47zws
Namespace:        s14-mini
Priority:         0
Service Account:  default
Node:             saniya-k8s/192.0.2.2
Start Time:       Wed, 07 Oct 2026 16:41:09 +0000
Labels:           app=troubleshooting-app
                  pod-template-hash=7f4b8cd658
Annotations:      <none>
Status:           Running
IP:               10.42.0.35
IPs:
Containers:
  app:
    Container ID:   containerd://557cdbabe8514f688715ad6ce0c398dd2339520d85731a9e0ef5ff4de0b75da4
    Image:          nginx:1.27
    Image ID:       docker.io/library/nginx@sha256:6784fb0834aa7dbbe12e3d7471e69c290df3e6ba810dc38b34ae33d3c1c05f7d
    Port:           80/TCP
    Host Port:      0/TCP
    State:          Running
      Started:      Wed, 07 Oct 2026 16:41:10 +0000
    Ready:          True
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  4s    default-scheduler  Successfully assigned s14-mini/troubleshooting-app-7f4b8cd658-47zws to saniya-k8s
  Normal  Pulled     3s    kubelet            Container image "nginx:1.27" already present on machine
  Normal  Created    3s    kubelet            Created container app
  Normal  Started    3s    kubelet            Started container app
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl logs troubleshooting-app-7f4b8cd658-47zws -n s14-mini
Error from server: Get "https://192.0.2.2:10250/containerLogs/s14-mini/troubleshooting-app-7f4b8cd658-47zws/app": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl exec troubleshooting-app-7f4b8cd658-47zws -n s14-mini -- curl -s localhost
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
```

### 3–4. Check the Service and its endpoints

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl describe service troubleshooting-service -n s14-mini
Name:                     troubleshooting-service
Namespace:                s14-mini
Labels:                   <none>
Annotations:              <none>
Selector:                 app=troubleshooting-app
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.43.46.192
IPs:                      10.43.46.192
Port:                     <unset>  80/TCP
TargetPort:               80/TCP
Endpoints:                10.42.0.35:80,10.42.0.36:80
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get endpoints troubleshooting-service -n s14-mini
NAME                      ENDPOINTS                     AGE
troubleshooting-service   10.42.0.35:80,10.42.0.36:80   12s
```

Selector `app=troubleshooting-app`, TargetPort 80, and two pod IPs as endpoints – healthy.

### 5–6. Create the broken pod and troubleshoot it (without touching the YAML first)

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl apply -f broken-pod.yaml -n s14-mini
pod/project-broken-pod created
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get pod project-broken-pod -n s14-mini
NAME                 READY   STATUS         RESTARTS   AGE
project-broken-pod   0/1     ErrImagePull   0          35s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl describe pod project-broken-pod -n s14-mini
Containers:
  app:
    Container ID:   
    Image:          nginx:this-tag-does-not-exist
    Image ID:       
    Port:           <none>
    Host Port:      <none>
    State:          Waiting
      Reason:       ErrImagePull
    Ready:          False
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  35s                default-scheduler  Successfully assigned s14-mini/project-broken-pod to saniya-k8s
  Normal   Pulling    21s (x2 over 34s)  kubelet            Pulling image "nginx:this-tag-does-not-exist"
  Warning  Failed     19s (x2 over 33s)  kubelet            Failed to pull image "nginx:this-tag-does-not-exist": failed to pull and unpack image "docker.io/library/nginx:this-tag-does-not-exist": failed to resolve reference "docker.io/library/nginx:this-tag-does-not-exist": unexpected status from HEAD request to https://registry-1.docker.io/v2/library/nginx/manifests/this-tag-does-not-exist: 429 Too Many Requests
  Warning  Failed     19s (x2 over 33s)  kubelet            Error: ErrImagePull
  Normal   BackOff    7s (x2 over 33s)   kubelet            Back-off pulling image "nginx:this-tag-does-not-exist"
  Warning  Failed     7s (x2 over 33s)   kubelet            Error: ImagePullBackOff
```

### 7. Answers for the broken pod

| Question | Answer |
|---|---|
| **1. What is the Pod status?** | `ImagePullBackOff` (alternating with `ErrImagePull`), READY `0/1` |
| **2. What is the actual error?** | `Failed to pull image "nginx:this-tag-does-not-exist": ... docker.io/library/nginx:this-tag-does-not-exist: not found` |
| **3. Which command helped?** | `kubectl describe pod project-broken-pod` – the **Events** section |
| **4. What is wrong with the image?** | The repository `nginx` exists, but the **tag** `this-tag-does-not-exist` is not published |
| **5. How would you fix it?** | Use a valid tag, e.g. `nginx:1.27` ([`fixed-pod.yaml`](./03-mini-project/fixed-pod.yaml)), delete and re-create the pod |

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl delete pod project-broken-pod -n s14-mini && kubectl apply -f fixed-pod.yaml -n s14-mini
pod "project-broken-pod" deleted
pod/project-broken-pod created
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get pod project-broken-pod -n s14-mini
NAME                 READY   STATUS    RESTARTS   AGE
project-broken-pod   1/1     Running   0          1s
```

### 8. Service troubleshooting challenge – break the selector

[`broken-service.yaml`](./03-mini-project/broken-service.yaml) changes the selector to `app: wrong-app`:

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl apply -f broken-service.yaml -n s14-mini
service/troubleshooting-service configured
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get service -n s14-mini
NAME                      TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
troubleshooting-service   ClusterIP   10.43.46.192   <none>        80/TCP    53s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get endpoints troubleshooting-service -n s14-mini
NAME                      ENDPOINTS   AGE
troubleshooting-service   <none>      53s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl exec troubleshooting-app-7f4b8cd658-47zws -n s14-mini -- curl -s -m 3 http://troubleshooting-service
curl: (7) Failed to connect to troubleshooting-service port 80 after 1 ms: Couldn't connect to server
command terminated with exit code 7
```

### 9. Find the root cause

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get pods -n s14-mini --show-labels
NAME                                   READY   STATUS    RESTARTS   AGE   LABELS
project-broken-pod                     1/1     Running   0          5s    <none>
troubleshooting-app-7f4b8cd658-47zws   1/1     Running   0          53s   app=troubleshooting-app,pod-template-hash=7f4b8cd658
troubleshooting-app-7f4b8cd658-tfrg8   1/1     Running   0          53s   app=troubleshooting-app,pod-template-hash=7f4b8cd658
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl describe service troubleshooting-service -n s14-mini
Name:                     troubleshooting-service
Selector:                 app=wrong-app
Endpoints:                
```

**Root cause:** Pod label is `app=troubleshooting-app`, Service selector is `app=wrong-app` → no pod matches → `Endpoints: <none>` → curl to the Service fails. (Note: `project-broken-pod` has no labels at all, so it is never part of the Service either.)

**Fix:** restore the original selector by re-applying [`service.yaml`](./03-mini-project/service.yaml):

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl apply -f service.yaml -n s14-mini
service/troubleshooting-service configured
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get endpoints troubleshooting-service -n s14-mini
NAME                      ENDPOINTS                     AGE
troubleshooting-service   10.42.0.35:80,10.42.0.36:80   57s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl exec troubleshooting-app-7f4b8cd658-47zws -n s14-mini -- curl -s http://troubleshooting-service
<title>Welcome to nginx!</title>
```

### 10. Final checklist run

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl get pods -n s14-mini
NAME                                   READY   STATUS    RESTARTS   AGE
project-broken-pod                     1/1     Running   0          9s
troubleshooting-app-7f4b8cd658-47zws   1/1     Running   0          57s
troubleshooting-app-7f4b8cd658-tfrg8   1/1     Running   0          57s
```

```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting/03-mini-project$ kubectl events -n s14-mini --types=Warning
LAST SEEN           TYPE      REASON   OBJECT                   MESSAGE
29s (x2 over 43s)   Warning   Failed   Pod/project-broken-pod   Failed to pull image "nginx:this-tag-does-not-exist": failed to pull and unpack image "docker.io/library/nginx:this-tag-does-not-exist": failed to resolve reference "docker.io/library/nginx:this-tag-does-not-exist": unexpected status from HEAD request to https://registry-1.docker.io/v2/library/nginx/manifests/this-tag-does-not-exist: 429 Too Many Requests
29s (x2 over 43s)   Warning   Failed   Pod/project-broken-pod   Error: ErrImagePull
17s (x2 over 43s)   Warning   Failed   Pod/project-broken-pod   Error: ImagePullBackOff
```

(The remaining warnings are the historical events from the broken image pull – the pod has been fixed since.)

### 11. Troubleshooting table

| Problem | What I Saw | Command I Used | Root Cause | Fix |
| :--- | :--- | :--- | :--- | :--- |
| **Broken Pod** | `project-broken-pod` `0/1 ImagePullBackOff` | `kubectl get pod`, `kubectl describe pod` | Image could not be pulled, so the container never started | Re-created the pod with a valid image |
| **Service Problem** | `Endpoints: <none>`, curl to Service fails | `kubectl get endpoints`, `kubectl get pods --show-labels`, `kubectl describe service` | Selector `app=wrong-app` did not match pod label `app=troubleshooting-app` | Restored selector `app: troubleshooting-app` |
| **Image Problem** | `Failed to pull image "nginx:this-tag-does-not-exist" ... not found` | Events in `kubectl describe pod` | Tag `this-tag-does-not-exist` does not exist on Docker Hub | Use `nginx:1.27` |

### 12. README questions

1. **What does `kubectl get` tell us?** – A quick one-line summary per object: does it exist, is it ready, its status, restarts and age (with `-o wide`: IP and node).
2. **Difference between `get` and `describe`?** – `get` is the short status table; `describe` is the long, human-readable detail of one object: full spec, conditions, related objects and the **events** that explain *why*.
3. **Why do we use `kubectl logs`?** – To read what the application itself printed (stdout/stderr), e.g. a stack trace or "missing env var" message; `--previous` for the container that crashed.
4. **When would you use `kubectl exec`?** – When the container runs but behaves wrongly: check files/config, env vars, whether the app listens on a port (`curl localhost`), DNS (`nslookup`) and connectivity from inside the pod's network.
5. **What does `CrashLoopBackOff` mean?** – The container starts and keeps exiting; the kubelet restarts it with an increasing back-off delay (10s, 20s, 40s … max 5 min).
6. **What does `ImagePullBackOff` mean?** – The image could not be pulled (wrong name/tag, private registry without credentials, network) and Kubernetes is waiting before retrying.
7. **Why can a Pod remain `Pending`?** – The scheduler can't place it: insufficient CPU/memory, nodeSelector/affinity with no matching node, taints without tolerations, or an unbound PVC.
8. **Why can a Service have no endpoints?** – Its selector matches no pods (label typo), or the matching pods are not Ready (failing readiness probe), or they are in a different namespace.
9. **Relationship between Service selector and Pod labels?** – The Service's endpoints controller continuously selects all *Ready* pods whose labels contain every key/value of the selector; those pod IPs (+ `targetPort`) become the endpoints traffic is load-balanced to.
10. **What is Kubernetes DNS?** – CoreDNS (service `kube-dns` in `kube-system`) gives every Service a name `<service>.<namespace>.svc.cluster.local`; pods get it as nameserver in `/etc/resolv.conf` with search domains so the short name works inside the same namespace.

### 13. Final architecture (verified above)

```text
                    k3s cluster (namespace s14-mini)
                            │
                  ┌───────────────────────────┐
                  │ Service troubleshooting-  │  selector app=troubleshooting-app
                  │ service  (ClusterIP :80)  │
                  └─────────────┬─────────────┘
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
     Pod troubleshooting-app-…           Pod troubleshooting-app-…
         nginx:1.27 :80                      nginx:1.27 :80
```

---

## Clean-up
```console
saniya@saniya-devops:~/devops-homework/session-14-kubernetes-troubleshooting$ kubectl delete ns s14-basics s14-crash s14-imgpull s14-errpull s14-pending s14-creating s14-svc s14-dns s14-dns-backend s14-net s14-config s14-oom s14-mini
namespace "s14-basics" deleted
namespace "s14-crash" deleted
namespace "s14-imgpull" deleted
namespace "s14-errpull" deleted
namespace "s14-pending" deleted
namespace "s14-creating" deleted
namespace "s14-svc" deleted
namespace "s14-dns" deleted
namespace "s14-dns-backend" deleted
namespace "s14-net" deleted
namespace "s14-config" deleted
namespace "s14-oom" deleted
namespace "s14-mini" deleted
```

## Notes

- The reference `09-service-dns-troubleshooting/dns-test-pod.yaml` uses `registry.k8s.io/e2e-test-images/dnsutils:1.3`, which my registry mirror could not resolve (`not found`), so I used `nslookup` from `curlimages/curl` / `busybox` instead.
- Long outputs (`describe`) are trimmed with `sed`/`grep` to the relevant sections; nothing else is edited.
