# Session 10 – Pods, ReplicaSets & Deployments Homework

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

All command output below is real output from my terminal, captured on a single-node Kubernetes cluster (k3s v1.30, node `saniya-k8s`, IP `192.0.2.2`).
YAML files are adapted from the instructor's repo (`session10-k8s-core-objects/01-rolling-update … 04-recreate`, `pod-lifecycle/`). My changes: NodePorts moved to my range `31010–31040`, change-cause annotations added for rollout history, canary ratio changed to **4 stable : 1 canary**.

## Contents
- [Task 1 – Deployment strategies](#task-1--deployment-strategies)
  - [1. Rolling Update](#1-rolling-update) · [2. Blue-Green](#2-blue-green) · [3. Canary](#3-canary) · [4. Recreate](#4-recreate) · [Comparison](#strategy-comparison)
- [Task 2 – Pod lifecycle](#task-2--pod-lifecycle) (12 scenarios)

## Folder structure
```
session-10-pods-replicasets-deployments/
├── 01-rolling-update/   deployment-v1.yaml  deployment-v2.yaml  service.yaml
├── 02-blue-green/       deployment-blue.yaml  deployment-green.yaml  service-blue.yaml  service-green.yaml
├── 03-canary/           deployment-stable.yaml  deployment-canary.yaml  service.yaml
├── 04-recreate/         deployment-v1.yaml  deployment-v2.yaml  service.yaml
└── pod-lifecycle/       01-running.yaml … 12-termination.yaml
```

---

# Task 1 – Deployment strategies

Every app is nginx; a `postStart` hook writes an `index.html` that prints the version, so `curl` tells us which version answered.

## 1. Rolling Update

Files: [`deployment-v1.yaml`](./01-rolling-update/deployment-v1.yaml) · [`deployment-v2.yaml`](./01-rolling-update/deployment-v2.yaml) · [`service.yaml`](./01-rolling-update/service.yaml) — namespace `s10-rolling`.

Key part of the spec – replace pods one at a time and never drop below 4 ready pods:
```yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # at most 4+1 = 5 pods during the update
      maxUnavailable: 0  # never fewer than 4 ready pods -> zero downtime
```
A `readinessProbe` makes sure a new pod only receives traffic (and the rollout only continues) once nginx answers.

### Create v1
```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl create namespace s10-rolling
namespace/s10-rolling created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl apply -f deployment-v1.yaml -f service.yaml -n s10-rolling
deployment.apps/app-rolling created
service/app-rolling-service created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl get deploy,rs,pods -n s10-rolling -L version
NAME                          READY   UP-TO-DATE   AVAILABLE   AGE   VERSION
deployment.apps/app-rolling   4/4     4            4           9s    

NAME                                     DESIRED   CURRENT   READY   AGE   VERSION
replicaset.apps/app-rolling-774f47b6c6   4         4         4       9s    v1

NAME                               READY   STATUS    RESTARTS   AGE   VERSION
pod/app-rolling-774f47b6c6-64zmk   1/1     Running   0          9s    v1
pod/app-rolling-774f47b6c6-9ngpx   1/1     Running   0          9s    v1
pod/app-rolling-774f47b6c6-czlg4   1/1     Running   0          9s    v1
pod/app-rolling-774f47b6c6-nnm74   1/1     Running   0          9s    v1
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl describe deploy app-rolling -n s10-rolling | grep -E 'StrategyType|RollingUpdateStrategy|Image'
StrategyType:           RollingUpdate
RollingUpdateStrategy:  0 max unavailable, 1 max surge
    Image:      nginx:1.24-alpine
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ curl -s http://192.0.2.2:31010 | grep -o 'VERSION: v[0-9]'
VERSION: v1
```

### Update to v2 and watch the rollout
I start `kubectl get pods -w` in the background (with a timeout) and then apply v2, so the watch records every pod transition:
```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ (timeout 75 kubectl get pods -n s10-rolling -L version -w --output-watch-events &) ; sleep 2; kubectl apply -f deployment-v2.yaml -n s10-rolling; sleep 75
EVENT      NAME                           READY   STATUS    RESTARTS   AGE   VERSION
ADDED      app-rolling-774f47b6c6-64zmk   1/1     Running   0          9s    v1
ADDED      app-rolling-774f47b6c6-9ngpx   1/1     Running   0          9s    v1
ADDED      app-rolling-774f47b6c6-czlg4   1/1     Running   0          9s    v1
ADDED      app-rolling-774f47b6c6-nnm74   1/1     Running   0          9s    v1
deployment.apps/app-rolling configured
ADDED      app-rolling-5578d688d5-5ttnf   0/1     Pending   0          0s    v2
MODIFIED   app-rolling-5578d688d5-5ttnf   0/1     Pending   0          0s    v2
MODIFIED   app-rolling-5578d688d5-5ttnf   0/1     ContainerCreating   0          0s    v2
MODIFIED   app-rolling-5578d688d5-5ttnf   0/1     Running             0          1s    v2
MODIFIED   app-rolling-5578d688d5-5ttnf   1/1     Running             0          5s    v2
MODIFIED   app-rolling-774f47b6c6-nnm74   1/1     Terminating         0          17s   v1
ADDED      app-rolling-5578d688d5-bmx9b   0/1     Pending             0          0s    v2
MODIFIED   app-rolling-5578d688d5-bmx9b   0/1     Pending             0          0s    v2
MODIFIED   app-rolling-5578d688d5-bmx9b   0/1     ContainerCreating   0          0s    v2
MODIFIED   app-rolling-774f47b6c6-nnm74   0/1     Terminating         0          18s   v1
MODIFIED   app-rolling-774f47b6c6-nnm74   0/1     Terminating         0          18s   v1
DELETED    app-rolling-774f47b6c6-nnm74   0/1     Terminating         0          18s   v1
MODIFIED   app-rolling-5578d688d5-bmx9b   0/1     Running             0          1s    v2
MODIFIED   app-rolling-5578d688d5-bmx9b   1/1     Running             0          5s    v2
MODIFIED   app-rolling-774f47b6c6-64zmk   1/1     Terminating         0          23s   v1
ADDED      app-rolling-5578d688d5-qwdxh   0/1     Pending             0          0s    v2
MODIFIED   app-rolling-5578d688d5-qwdxh   0/1     Pending             0          0s    v2
MODIFIED   app-rolling-5578d688d5-qwdxh   0/1     ContainerCreating   0          0s    v2
MODIFIED   app-rolling-774f47b6c6-64zmk   0/1     Terminating         0          24s   v1
MODIFIED   app-rolling-5578d688d5-qwdxh   0/1     Running             0          2s    v2
MODIFIED   app-rolling-774f47b6c6-64zmk   0/1     Terminating         0          25s   v1
DELETED    app-rolling-774f47b6c6-64zmk   0/1     Terminating         0          25s   v1
MODIFIED   app-rolling-5578d688d5-qwdxh   1/1     Running             0          5s    v2
MODIFIED   app-rolling-774f47b6c6-czlg4   1/1     Terminating         0          29s   v1
ADDED      app-rolling-5578d688d5-vbxds   0/1     Pending             0          0s    v2
MODIFIED   app-rolling-5578d688d5-vbxds   0/1     Pending             0          0s    v2
MODIFIED   app-rolling-5578d688d5-vbxds   0/1     ContainerCreating   0          0s    v2
MODIFIED   app-rolling-774f47b6c6-czlg4   0/1     Terminating         0          30s   v1
MODIFIED   app-rolling-774f47b6c6-czlg4   0/1     Terminating         0          31s   v1
DELETED    app-rolling-774f47b6c6-czlg4   0/1     Terminating         0          31s   v1
MODIFIED   app-rolling-5578d688d5-vbxds   0/1     Running             0          2s    v2
MODIFIED   app-rolling-5578d688d5-vbxds   1/1     Running             0          5s    v2
MODIFIED   app-rolling-774f47b6c6-9ngpx   1/1     Terminating         0          34s   v1
MODIFIED   app-rolling-774f47b6c6-9ngpx   0/1     Terminating         0          35s   v1
MODIFIED   app-rolling-774f47b6c6-9ngpx   0/1     Terminating         0          36s   v1
DELETED    app-rolling-774f47b6c6-9ngpx   0/1     Terminating         0          36s   v1
```

Old and new pods at the same time (I paused the rollout halfway to show it clearly, then resumed):

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl apply -f deployment-v2.yaml -n s10-rolling && sleep 12 && kubectl rollout pause deployment/app-rolling -n s10-rolling
deployment.apps/app-rolling configured
deployment.apps/app-rolling paused
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl get pods -n s10-rolling -L version
NAME                           READY   STATUS              RESTARTS   AGE   VERSION
app-rolling-5578d688d5-4g2jn   1/1     Running             0          12s   v2
app-rolling-5578d688d5-k8k9f   0/1     ContainerCreating   0          1s    v2
app-rolling-5578d688d5-mqrf2   1/1     Running             0          7s    v2
app-rolling-774f47b6c6-4f6dm   1/1     Running             0          25s   v1
app-rolling-774f47b6c6-l8w7w   1/1     Running             0          36s   v1
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl get rs -n s10-rolling -o wide
NAME                     DESIRED   CURRENT   READY   AGE    CONTAINERS   IMAGES              SELECTOR
app-rolling-5578d688d5   3         3         2       111s   web          nginx:1.25-alpine   app=app-rolling,pod-template-hash=5578d688d5
app-rolling-774f47b6c6   2         2         2       2m3s   web          nginx:1.24-alpine   app=app-rolling,pod-template-hash=774f47b6c6
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ for i in $(seq 1 10); do curl -s http://192.0.2.2:31010 | grep -o 'VERSION: v[0-9]'; done | sort | uniq -c
      8 VERSION: v1
      2 VERSION: v2
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl rollout resume deployment/app-rolling -n s10-rolling && kubectl rollout status deployment/app-rolling -n s10-rolling
deployment.apps/app-rolling resumed
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
deployment "app-rolling" successfully rolled out
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl get rs,pods -n s10-rolling -L version
NAME                                     DESIRED   CURRENT   READY   AGE     VERSION
replicaset.apps/app-rolling-5578d688d5   4         4         4       2m1s    v2
replicaset.apps/app-rolling-774f47b6c6   0         0         0       2m13s   v1

NAME                               READY   STATUS        RESTARTS   AGE   VERSION
pod/app-rolling-5578d688d5-4g2jn   1/1     Running       0          22s   v2
pod/app-rolling-5578d688d5-k8k9f   1/1     Running       0          11s   v2
pod/app-rolling-5578d688d5-mlmq4   1/1     Running       0          6s    v2
pod/app-rolling-5578d688d5-mqrf2   1/1     Running       0          17s   v2
pod/app-rolling-774f47b6c6-l8w7w   1/1     Terminating   0          46s   v1
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ curl -s http://192.0.2.2:31010 | grep -o 'VERSION: v[0-9]'
VERSION: v2
```

### Rollout history and rollback

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl rollout history deployment/app-rolling -n s10-rolling
deployment.apps/app-rolling 
REVISION  CHANGE-CAUSE
3         v1 - image nginx:1.24-alpine
4         v2 - image nginx:1.25-alpine

```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl rollout history deployment/app-rolling -n s10-rolling --revision=$(kubectl get deploy app-rolling -n s10-rolling -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}') | grep -E 'revision|change-cause|Image|version='
deployment.apps/app-rolling with revision #4
	version=v2
  Annotations:	kubernetes.io/change-cause: v2 - image nginx:1.25-alpine
    Image:	nginx:1.25-alpine
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl describe deploy app-rolling -n s10-rolling | sed -n '/Events:/,$p'
Events:
  Type    Reason             Age                From                   Message
  ----    ------             ----               ----                   -------
  Normal  ScalingReplicaSet  2m13s              deployment-controller  Scaled up replica set app-rolling-774f47b6c6 to 4
  Normal  ScalingReplicaSet  2m1s               deployment-controller  Scaled up replica set app-rolling-5578d688d5 to 1
  Normal  ScalingReplicaSet  116s               deployment-controller  Scaled down replica set app-rolling-774f47b6c6 to 3 from 4
  Normal  ScalingReplicaSet  115s               deployment-controller  Scaled up replica set app-rolling-5578d688d5 to 2 from 1
  Normal  ScalingReplicaSet  110s               deployment-controller  Scaled down replica set app-rolling-774f47b6c6 to 2 from 3
  Normal  ScalingReplicaSet  110s               deployment-controller  Scaled up replica set app-rolling-5578d688d5 to 3 from 2
  Normal  ScalingReplicaSet  104s               deployment-controller  Scaled down replica set app-rolling-774f47b6c6 to 1 from 2
  Normal  ScalingReplicaSet  104s               deployment-controller  Scaled up replica set app-rolling-5578d688d5 to 4 from 3
  Normal  ScalingReplicaSet  6s (x15 over 46s)  deployment-controller  (combined from similar events): Scaled up replica set app-rolling-5578d688d5 to 4 from 3
  Normal  ScalingReplicaSet  0s (x2 over 99s)   deployment-controller  Scaled down replica set app-rolling-774f47b6c6 to 0 from 1
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ kubectl rollout undo deployment/app-rolling -n s10-rolling && kubectl rollout status deployment/app-rolling -n s10-rolling
deployment.apps/app-rolling rolled back
Waiting for deployment "app-rolling" rollout to finish: 0 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
deployment "app-rolling" successfully rolled out
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/01-rolling-update$ curl -s http://192.0.2.2:31010 | grep -o 'VERSION: v[0-9]'
VERSION: v1
```

**Observation:**
- The watch shows the pattern dictated by `maxSurge: 1 / maxUnavailable: 0`: one new v2 pod is `ADDED`, becomes `1/1 Ready`, and only **then** one v1 pod is terminated – repeated 4 times. The number of ready pods never dropped below 4.
- While paused, both ReplicaSets have pods (old RS + new RS) and the Service load-balances across **both versions** – this is the defining property (and risk) of a rolling update: two versions live side-by-side for a while.
- Each template change creates a new ReplicaSet (a new `pod-template-hash`); old RSs are kept at 0 replicas, which is what `rollout history`/`rollout undo` use.

---

## 2. Blue-Green

Files: [`deployment-blue.yaml`](./02-blue-green/deployment-blue.yaml) · [`deployment-green.yaml`](./02-blue-green/deployment-green.yaml) · [`service-blue.yaml`](./02-blue-green/service-blue.yaml) · [`service-green.yaml`](./02-blue-green/service-green.yaml) — namespace `s10-bluegreen`.

Two complete environments run at the same time; the Service selector (`slot: blue` ↔ `slot: green`) is the switch:
```yaml
  selector:
    app: myapp
    slot: blue     # change to green to switch ALL traffic at once
```
```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl create namespace s10-bluegreen
namespace/s10-bluegreen created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl apply -f deployment-blue.yaml -f service-blue.yaml -n s10-bluegreen
deployment.apps/app-blue created
service/myapp-service created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ curl -s http://192.0.2.2:31020 | grep -oE '(BLUE|GREEN) ENVIRONMENT|Version: v[0-9]'
BLUE ENVIRONMENT
Version: v1
```

Deploy **green** (v2) next to blue – it gets no user traffic yet:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl apply -f deployment-green.yaml -n s10-bluegreen
deployment.apps/app-green created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl get deploy,pods -n s10-bluegreen -L slot,version
NAME                        READY   UP-TO-DATE   AVAILABLE   AGE   SLOT    VERSION
deployment.apps/app-blue    3/3     3            3           16s   blue    v1
deployment.apps/app-green   3/3     3            3           8s    green   v2

NAME                            READY   STATUS    RESTARTS   AGE   SLOT    VERSION
pod/app-blue-7f58f86f99-c9mtb   1/1     Running   0          16s   blue    v1
pod/app-blue-7f58f86f99-ddshr   1/1     Running   0          16s   blue    v1
pod/app-blue-7f58f86f99-dvfhm   1/1     Running   0          16s   blue    v1
pod/app-green-666c4cc64-8zchj   1/1     Running   0          8s    green   v2
pod/app-green-666c4cc64-dswcr   1/1     Running   0          8s    green   v2
pod/app-green-666c4cc64-nms82   1/1     Running   0          8s    green   v2
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl get svc myapp-service -n s10-bluegreen -o jsonpath='{.spec.selector}{"\n"}'
{"app":"myapp","slot":"blue"}
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl get endpoints myapp-service -n s10-bluegreen
NAME            ENDPOINTS                                      AGE
myapp-service   10.42.0.230:80,10.42.0.231:80,10.42.0.232:80   16s
```

Test green internally before switching (directly to a green pod IP):

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl get pod -n s10-bluegreen -l slot=green -o jsonpath='{.items[0].status.podIP}{"\n"}'
10.42.0.235
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ curl -s http://10.42.0.235 | grep -oE '(BLUE|GREEN) ENVIRONMENT'
GREEN ENVIRONMENT
```

### Switch the Service selector to green

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl apply -f service-green.yaml -n s10-bluegreen
service/myapp-service configured
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl get svc myapp-service -n s10-bluegreen -o jsonpath='{.spec.selector}{"\n"}'
{"app":"myapp","slot":"green"}
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl get endpoints myapp-service -n s10-bluegreen
NAME            ENDPOINTS                                      AGE
myapp-service   10.42.0.234:80,10.42.0.235:80,10.42.0.236:80   17s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ for i in $(seq 1 6); do curl -s http://192.0.2.2:31020 | grep -oE '(BLUE|GREEN) ENVIRONMENT'; done
GREEN ENVIRONMENT
GREEN ENVIRONMENT
GREEN ENVIRONMENT
GREEN ENVIRONMENT
GREEN ENVIRONMENT
GREEN ENVIRONMENT
```

### Instant rollback = switch back to blue

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl patch svc myapp-service -n s10-bluegreen -p '{"spec":{"selector":{"app":"myapp","slot":"blue"}}}'
service/myapp-service patched
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ for i in $(seq 1 3); do curl -s http://192.0.2.2:31020 | grep -oE '(BLUE|GREEN) ENVIRONMENT'; done
BLUE ENVIRONMENT
BLUE ENVIRONMENT
BLUE ENVIRONMENT
```

Promote green for good and retire blue:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl apply -f service-green.yaml -n s10-bluegreen && kubectl scale deployment app-blue --replicas=0 -n s10-bluegreen
service/myapp-service unchanged
deployment.apps/app-blue scaled
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/02-blue-green$ kubectl get deploy -n s10-bluegreen && curl -s http://192.0.2.2:31020 | grep -oE '(BLUE|GREEN) ENVIRONMENT'
NAME        READY   UP-TO-DATE   AVAILABLE   AGE
app-blue    0/0     0            0           24s
app-green   3/3     3            3           16s
GREEN ENVIRONMENT
```

**Observation:** before the switch the Service endpoints were the 3 blue pod IPs; after changing only the selector they became the 3 green pod IPs and **every** request returned `GREEN ENVIRONMENT` – an atomic cut-over with no mixed versions. Rollback is just flipping the selector back. Cost: double the resources while both environments run.

---

## 3. Canary

Files: [`deployment-stable.yaml`](./03-canary/deployment-stable.yaml) (4 replicas, `track: stable`) · [`deployment-canary.yaml`](./03-canary/deployment-canary.yaml) (1 replica, `track: canary`) · [`service.yaml`](./03-canary/service.yaml) — namespace `s10-canary`.

Both Deployments share the label `app: myapp-canary`; the Service selects **only** that common label, so it load-balances over all 5 pods → about **4/5 = 80 % stable, 1/5 = 20 % canary**.
```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ kubectl create namespace s10-canary
namespace/s10-canary created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ kubectl apply -f deployment-stable.yaml -f deployment-canary.yaml -f service.yaml -n s10-canary
deployment.apps/app-stable created
deployment.apps/app-canary created
service/myapp-canary-service created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ kubectl get deploy,pods -n s10-canary -L track,version
NAME                         READY   UP-TO-DATE   AVAILABLE   AGE   TRACK    VERSION
deployment.apps/app-canary   1/1     1            1           9s    canary   v2
deployment.apps/app-stable   4/4     4            4           9s    stable   v1

NAME                              READY   STATUS    RESTARTS   AGE   TRACK    VERSION
pod/app-canary-7c755c5f84-pj782   1/1     Running   0          9s    canary   v2
pod/app-stable-897cb4d45-chrjh    1/1     Running   0          9s    stable   v1
pod/app-stable-897cb4d45-ckrzq    1/1     Running   0          9s    stable   v1
pod/app-stable-897cb4d45-jsn4t    1/1     Running   0          9s    stable   v1
pod/app-stable-897cb4d45-pt6hl    1/1     Running   0          9s    stable   v1
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ kubectl get svc myapp-canary-service -n s10-canary -o wide
NAME                   TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
myapp-canary-service   NodePort   10.43.38.101   <none>        80:31030/TCP   9s    app=myapp-canary
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ kubectl get endpoints myapp-canary-service -n s10-canary
NAME                   ENDPOINTS                                                  AGE
myapp-canary-service   10.42.0.237:80,10.42.0.238:80,10.42.0.239:80 + 2 more...   8s
```

Send 20 requests and count which version answered:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ for i in $(seq 1 20); do curl -s http://192.0.2.2:31030 | grep -oE 'STABLE v1|CANARY v2'; done | sort | uniq -c
      4 CANARY v2
     16 STABLE v1
```

With a bigger sample (100 requests) the split gets closer to the 80/20 pod ratio:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ for i in $(seq 1 100); do curl -s http://192.0.2.2:31030 | grep -oE 'STABLE v1|CANARY v2'; done | sort | uniq -c
     24 CANARY v2
     76 STABLE v1
```

Canary looks healthy → shift more traffic (2 canary : 3 stable ≈ 40 %):

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ kubectl scale deploy app-canary --replicas=2 -n s10-canary && kubectl scale deploy app-stable --replicas=3 -n s10-canary
deployment.apps/app-canary scaled
deployment.apps/app-stable scaled
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ kubectl get pods -n s10-canary -L track
NAME                          READY   STATUS    RESTARTS   AGE   TRACK
app-canary-7c755c5f84-862d4   1/1     Running   0          14s   canary
app-canary-7c755c5f84-pj782   1/1     Running   0          24s   canary
app-stable-897cb4d45-ckrzq    1/1     Running   0          24s   stable
app-stable-897cb4d45-jsn4t    1/1     Running   0          24s   stable
app-stable-897cb4d45-pt6hl    1/1     Running   0          24s   stable
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/03-canary$ for i in $(seq 1 100); do curl -s http://192.0.2.2:31030 | grep -oE 'STABLE v1|CANARY v2'; done | sort | uniq -c
     38 CANARY v2
     62 STABLE v1
```

**Observation:** with 4 stable + 1 canary pods roughly a fifth of the requests hit the canary (kube-proxy picks a backend randomly per connection, so small samples vary around 20 %). Scaling the two Deployments changes the ratio. The traffic split is only as fine-grained as the pod count – for exact percentages (e.g. 1 %) you need an ingress/service-mesh (NGINX Ingress canary annotations, Istio, Argo Rollouts).

---

## 4. Recreate

Files: [`deployment-v1.yaml`](./04-recreate/deployment-v1.yaml) · [`deployment-v2.yaml`](./04-recreate/deployment-v2.yaml) · [`service.yaml`](./04-recreate/service.yaml) — namespace `s10-recreate`.
```yaml
  strategy:
    type: Recreate   # kill ALL old pods first, then create new ones
```
```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ kubectl create namespace s10-recreate
namespace/s10-recreate created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ kubectl apply -f deployment-v1.yaml -f service.yaml -n s10-recreate
deployment.apps/app-recreate created
service/app-recreate-service created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ kubectl get pods -n s10-recreate -L version
NAME                            READY   STATUS    RESTARTS   AGE   VERSION
app-recreate-68dd974499-rrk4k   1/1     Running   0          6s    v1
app-recreate-68dd974499-sfp2s   1/1     Running   0          6s    v1
app-recreate-68dd974499-vhn2j   1/1     Running   0          6s    v1
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ curl -s http://192.0.2.2:31040 | grep -oE 'VERSION: v[0-9]'
VERSION: v1
```

Watch the pods while applying v2, and probe the Service every second at the same time:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ (timeout 45 kubectl get pods -n s10-recreate -L version -w --output-watch-events &) ; sleep 2; kubectl apply -f deployment-v2.yaml -n s10-recreate; sleep 45
EVENT      NAME                            READY   STATUS    RESTARTS   AGE   VERSION
ADDED      app-recreate-68dd974499-rrk4k   1/1     Running   0          6s    v1
ADDED      app-recreate-68dd974499-sfp2s   1/1     Running   0          6s    v1
ADDED      app-recreate-68dd974499-vhn2j   1/1     Running   0          6s    v1
deployment.apps/app-recreate configured
MODIFIED   app-recreate-68dd974499-vhn2j   1/1     Terminating   0          8s    v1
MODIFIED   app-recreate-68dd974499-rrk4k   1/1     Terminating   0          8s    v1
MODIFIED   app-recreate-68dd974499-sfp2s   1/1     Terminating   0          8s    v1
MODIFIED   app-recreate-68dd974499-sfp2s   0/1     Terminating   0          9s    v1
MODIFIED   app-recreate-68dd974499-rrk4k   0/1     Terminating   0          9s    v1
MODIFIED   app-recreate-68dd974499-vhn2j   0/1     Terminating   0          9s    v1
MODIFIED   app-recreate-68dd974499-sfp2s   0/1     Terminating   0          9s    v1
DELETED    app-recreate-68dd974499-sfp2s   0/1     Terminating   0          9s    v1
MODIFIED   app-recreate-68dd974499-rrk4k   0/1     Terminating   0          9s    v1
DELETED    app-recreate-68dd974499-rrk4k   0/1     Terminating   0          9s    v1
MODIFIED   app-recreate-68dd974499-vhn2j   0/1     Terminating   0          9s    v1
DELETED    app-recreate-68dd974499-vhn2j   0/1     Terminating   0          9s    v1
ADDED      app-recreate-76c68fb685-5z5m5   0/1     Pending       0          0s    v2
ADDED      app-recreate-76c68fb685-nvxwf   0/1     Pending       0          0s    v2
ADDED      app-recreate-76c68fb685-jlr9x   0/1     Pending       0          0s    v2
MODIFIED   app-recreate-76c68fb685-5z5m5   0/1     Pending       0          0s    v2
MODIFIED   app-recreate-76c68fb685-nvxwf   0/1     Pending       0          1s    v2
MODIFIED   app-recreate-76c68fb685-jlr9x   0/1     Pending       0          1s    v2
MODIFIED   app-recreate-76c68fb685-5z5m5   0/1     ContainerCreating   0          1s    v2
MODIFIED   app-recreate-76c68fb685-jlr9x   0/1     ContainerCreating   0          1s    v2
MODIFIED   app-recreate-76c68fb685-nvxwf   0/1     ContainerCreating   0          1s    v2
MODIFIED   app-recreate-76c68fb685-nvxwf   1/1     Running             0          2s    v2
MODIFIED   app-recreate-76c68fb685-5z5m5   1/1     Running             0          2s    v2
MODIFIED   app-recreate-76c68fb685-jlr9x   1/1     Running             0          2s    v2
```

Same update again (v1 → v2) while curling the Service once per second – note the gap:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ kubectl apply -f deployment-v2.yaml -n s10-recreate; for i in $(seq 1 15); do echo "$(date +%T) $(curl -s -m 1 http://192.0.2.2:31040 | grep -oE 'VERSION: v[0-9]' || echo 'NO RESPONSE (downtime)')"; sleep 1; done
deployment.apps/app-recreate configured
16:35:27 VERSION: v1
16:35:28 NO RESPONSE (downtime)
16:35:29 NO RESPONSE (downtime)
16:35:31 VERSION: v2
16:35:32 VERSION: v2
16:35:33 VERSION: v2
16:35:34 VERSION: v2
16:35:35 VERSION: v2
16:35:36 VERSION: v2
16:35:37 VERSION: v2
16:35:38 VERSION: v2
16:35:39 VERSION: v2
16:35:40 VERSION: v2
16:35:41 VERSION: v2
16:35:42 VERSION: v2
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ kubectl describe deploy app-recreate -n s10-recreate | sed -n '/Events:/,$p'
Events:
  Type    Reason             Age                From                   Message
  ----    ------             ----               ----                   -------
  Normal  ScalingReplicaSet  76s                deployment-controller  Scaled up replica set app-recreate-68dd974499 to 3
  Normal  ScalingReplicaSet  67s                deployment-controller  Scaled up replica set app-recreate-76c68fb685 to 3
  Normal  ScalingReplicaSet  23s                deployment-controller  Scaled down replica set app-recreate-76c68fb685 to 0 from 3
  Normal  ScalingReplicaSet  21s                deployment-controller  Scaled up replica set app-recreate-68dd974499 to 3 from 0
  Normal  ScalingReplicaSet  16s (x2 over 68s)  deployment-controller  Scaled down replica set app-recreate-68dd974499 to 0 from 3
  Normal  ScalingReplicaSet  14s                deployment-controller  Scaled up replica set app-recreate-76c68fb685 to 3 from 0
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/04-recreate$ kubectl get rs,pods -n s10-recreate -L version
NAME                                      DESIRED   CURRENT   READY   AGE   VERSION
replicaset.apps/app-recreate-68dd974499   0         0         0       77s   v1
replicaset.apps/app-recreate-76c68fb685   3         3         3       68s   v2

NAME                                READY   STATUS    RESTARTS   AGE   VERSION
pod/app-recreate-76c68fb685-lxtkx   1/1     Running   0          15s   v2
pod/app-recreate-76c68fb685-pn75f   1/1     Running   0          15s   v2
pod/app-recreate-76c68fb685-wnbb8   1/1     Running   0          15s   v2
```

**Observation:** in the watch every v1 pod goes `Terminating` → `DELETED` **before** the first v2 pod is `ADDED` (`Pending` → `ContainerCreating` → `Running`). The events confirm the order: *Scaled down replica set …(v1) to 0* and only then *Scaled up replica set …(v2) to 3*. The curl loop shows a short window with **no response** – Recreate always causes downtime, but guarantees two versions never run together (useful for DB schema changes, singleton apps, RWO volumes).

## Strategy comparison

| Strategy | How | Downtime | Both versions live together? | Rollback | Extra resources |
|---|---|---|---|---|---|
| **Rolling Update** | replace pods gradually (`maxSurge`/`maxUnavailable`) | none | yes, during rollout | `rollout undo` (gradual) | small (surge) |
| **Recreate** | kill all old, then start new | **yes** | never | redeploy old | none |
| **Blue-Green** | 2 full environments, switch Service selector | none | no (atomic switch) | instant (flip selector) | 2× |
| **Canary** | small % of pods on new version behind same Service | none | yes, on purpose | scale canary to 0 | small |

---

# Task 2 – Pod lifecycle

For each YAML in [`pod-lifecycle/`](./pod-lifecycle) (from the instructor's repo, images already pinned: `nginx:1.27`, `busybox:1.36`): apply → check status → check details (`describe`, trimmed to the container **State**, pod **Conditions** and **Events**) → explanation. Namespace `s10-lifecycle`.

Pod **phases**: `Pending` → `Running` → `Succeeded` / `Failed` (+ `Unknown`). Values like `CrashLoopBackOff`, `ImagePullBackOff`, `Init:0/1`, `Terminating` in the STATUS column are *container states/reasons*, not phases.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl create namespace s10-lifecycle
namespace/s10-lifecycle created
```

## 01 – Running

[`01-running.yaml`](./pod-lifecycle/01-running.yaml) – a plain nginx pod.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 01-running.yaml -n s10-lifecycle
pod/lifecycle-running created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-running -n s10-lifecycle -o wide
NAME                READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
lifecycle-running   1/1     Running   0          2s    10.42.0.11   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-running -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Running
      Started:      Wed, 07 Oct 2026 16:35:45 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  2s    default-scheduler  Successfully assigned s10-lifecycle/lifecycle-running to saniya-k8s
  Normal  Pulled     2s    kubelet            Container image "nginx:1.27" already present on machine
  Normal  Created    2s    kubelet            Created container nginx
  Normal  Started    2s    kubelet            Started container nginx
```

**Observation:** phase `Running`, container state `Running`, all conditions (`PodScheduled → Initialized → ContainersReady → Ready`) are `True`. Events show the normal path: *Scheduled → Pulling/Pulled → Created → Started*.

## 02 – Pending

[`02-pending.yaml`](./pod-lifecycle/02-pending.yaml) – requests `cpu: 1` and `memory: 9Gi`; my node only has ~8 GiB.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 02-pending.yaml -n s10-lifecycle
pod/lifecycle-pending created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-pending -n s10-lifecycle
NAME                READY   STATUS    RESTARTS   AGE
lifecycle-pending   0/1     Pending   0          6s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-pending -n s10-lifecycle   # trimmed to State / Conditions / Events

Conditions:
  Type           Status
  PodScheduled   False 
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  6s    default-scheduler  0/1 nodes are available: 1 Insufficient cpu, 1 Insufficient memory. preemption: 0/1 nodes are available: 1 No preemption victims found for incoming pod.
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get node saniya-k8s -o jsonpath='allocatable memory: {.status.allocatable.memory}{"\n"}'
allocatable memory: 8223864Ki
```

**Observation:** the pod stays `Pending` forever: `PodScheduled=False` with reason `Unschedulable` and a `FailedScheduling … Insufficient memory` event from the scheduler. No container was ever created (no State section). Fix: lower the request or add a bigger node.

## 03 – Succeeded

[`03-succeeded.yaml`](./pod-lifecycle/03-succeeded.yaml) – `restartPolicy: Never`, script exits 0 after 5 s.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 03-succeeded.yaml -n s10-lifecycle
pod/lifecycle-succeeded created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-succeeded -n s10-lifecycle
NAME                  READY   STATUS    RESTARTS   AGE
lifecycle-succeeded   1/1     Running   0          3s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-succeeded -n s10-lifecycle   # ~15 s later
NAME                  READY   STATUS      RESTARTS   AGE
lifecycle-succeeded   0/1     Completed   0          15s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl logs lifecycle-succeeded -n s10-lifecycle
Error from server: Get "https://192.0.2.2:10250/containerLogs/s10-lifecycle/lifecycle-succeeded/task": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-succeeded -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Terminated
      Reason:       Completed
      Exit Code:    0
      Started:      Wed, 07 Oct 2026 16:35:54 +0000
      Finished:     Wed, 07 Oct 2026 16:35:59 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   False 
  Initialized                 True 
  Ready                       False 
  ContainersReady             False 
  PodScheduled                True 
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  23s   default-scheduler  Successfully assigned s10-lifecycle/lifecycle-succeeded to saniya-k8s
  Normal  Pulled     23s   kubelet            Container image "busybox:1.36" already present on machine
  Normal  Created    23s   kubelet            Created container task
  Normal  Started    23s   kubelet            Started container task
```

**Observation:** `Running` → `Completed` (phase `Succeeded`). Container state `Terminated`, reason `Completed`, **exit code 0**. `Ready` is now `False` because no container is running – normal for a finished batch task (Jobs use this).

## 04 – Failed

[`04-failed.yaml`](./pod-lifecycle/04-failed.yaml) – `restartPolicy: Never`, script exits 1.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 04-failed.yaml -n s10-lifecycle
pod/lifecycle-failed created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-failed -n s10-lifecycle
NAME               READY   STATUS   RESTARTS   AGE
lifecycle-failed   0/1     Error    0          14s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl logs lifecycle-failed -n s10-lifecycle
Error from server: Get "https://192.0.2.2:10250/containerLogs/s10-lifecycle/lifecycle-failed/task": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-failed -n s10-lifecycle -o jsonpath='phase={.status.phase} exitCode={.status.containerStatuses[0].state.terminated.exitCode} reason={.status.containerStatuses[0].state.terminated.reason}{"\n"}'
phase=Failed exitCode=1 reason=Error
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-failed -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Wed, 07 Oct 2026 16:36:18 +0000
      Finished:     Wed, 07 Oct 2026 16:36:23 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   False 
  Initialized                 True 
  Ready                       False 
  ContainersReady             False 
  PodScheduled                True 
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  21s   default-scheduler  Successfully assigned s10-lifecycle/lifecycle-failed to saniya-k8s
  Normal  Pulled     21s   kubelet            Container image "busybox:1.36" already present on machine
  Normal  Created    21s   kubelet            Created container task
  Normal  Started    21s   kubelet            Started container task
```

**Observation:** phase `Failed` (STATUS `Error`), state `Terminated` with **exit code 1**. Because `restartPolicy: Never`, Kubernetes does not restart it – compare with the next case.

## 05 – CrashLoopBackOff

[`05-crashloopbackoff.yaml`](./pod-lifecycle/05-crashloopbackoff.yaml) – same failing command but default `restartPolicy: Always`.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 05-crashloopbackoff.yaml -n s10-lifecycle
pod/lifecycle-crashloop created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-crashloop -n s10-lifecycle -w   # watched for 60 s
NAME                  READY   STATUS              RESTARTS   AGE
lifecycle-crashloop   0/1     ContainerCreating   0          0s
lifecycle-crashloop   1/1     Running             0          1s
lifecycle-crashloop   0/1     Error               0          5s
lifecycle-crashloop   1/1     Running             1 (2s ago)   6s
lifecycle-crashloop   0/1     Error               1 (5s ago)   9s
lifecycle-crashloop   0/1     CrashLoopBackOff    1 (14s ago)   22s
lifecycle-crashloop   1/1     Running             2 (15s ago)   23s
lifecycle-crashloop   0/1     Error               2 (18s ago)   26s
lifecycle-crashloop   0/1     CrashLoopBackOff    2 (11s ago)   37s
lifecycle-crashloop   1/1     Running             3 (26s ago)   52s
lifecycle-crashloop   0/1     Error               3 (29s ago)   55s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl logs lifecycle-crashloop -n s10-lifecycle --previous
Error from server: Get "https://192.0.2.2:10250/containerLogs/s10-lifecycle/lifecycle-crashloop/crashing-app?previous=true": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-crashloop -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Wed, 07 Oct 2026 16:37:31 +0000
      Finished:     Wed, 07 Oct 2026 16:37:34 +0000
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Wed, 07 Oct 2026 16:37:02 +0000
      Finished:     Wed, 07 Oct 2026 16:37:05 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       False 
  ContainersReady             False 
  PodScheduled                True 
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  67s                default-scheduler  Successfully assigned s10-lifecycle/lifecycle-crashloop to saniya-k8s
  Normal   Pulled     17s (x4 over 67s)  kubelet            Container image "busybox:1.36" already present on machine
  Normal   Created    17s (x4 over 67s)  kubelet            Created container crashing-app
  Normal   Started    16s (x4 over 67s)  kubelet            Started container crashing-app
  Warning  BackOff    1s (x5 over 59s)   kubelet            Back-off restarting failed container crashing-app in pod lifecycle-crashloop_s10-lifecycle(77fdb13c-6142-4c3d-ae19-ae65ca8a0849)
```

**Observation:** the container exits with code 1, kubelet restarts it, it crashes again… After each crash kubelet waits longer (exponential back-off 10 s, 20 s, 40 s … max 5 min) – during the wait the status is `CrashLoopBackOff` and the RESTARTS counter climbs. `State: Waiting (CrashLoopBackOff)`, `Last State: Terminated (Error, exit 1)`, event *Back-off restarting failed container*. `kubectl logs --previous` shows the crashed run's output. The phase stays `Running`.

## 06 – ImagePullBackOff

[`06-imagepullbackoff.yaml`](./pod-lifecycle/06-imagepullbackoff.yaml) – image `jakwehrgkaejw:kahsdfgkhj` does not exist.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 06-imagepullbackoff.yaml -n s10-lifecycle
pod/lifecycle-image-error created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-image-error -n s10-lifecycle -w   # watched for 40 s
NAME                    READY   STATUS              RESTARTS   AGE
lifecycle-image-error   0/1     ContainerCreating   0          0s
lifecycle-image-error   0/1     ErrImagePull        0          1s
lifecycle-image-error   0/1     ImagePullBackOff    0          16s
lifecycle-image-error   0/1     ErrImagePull        0          29s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-image-error -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Waiting
      Reason:       ErrImagePull

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       False 
  ContainersReady             False 
  PodScheduled                True 
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  40s                default-scheduler  Successfully assigned s10-lifecycle/lifecycle-image-error to saniya-k8s
  Normal   Pulling    24s (x2 over 40s)  kubelet            Pulling image "jakwehrgkaejw:kahsdfgkhj"
  Warning  Failed     23s (x2 over 39s)  kubelet            Failed to pull image "jakwehrgkaejw:kahsdfgkhj": failed to pull and unpack image "docker.io/library/jakwehrgkaejw:kahsdfgkhj": failed to resolve reference "docker.io/library/jakwehrgkaejw:kahsdfgkhj": pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
  Warning  Failed     23s (x2 over 39s)  kubelet            Error: ErrImagePull
  Normal   BackOff    11s (x2 over 39s)  kubelet            Back-off pulling image "jakwehrgkaejw:kahsdfgkhj"
  Warning  Failed     11s (x2 over 39s)  kubelet            Error: ImagePullBackOff
```

**Observation:** `ErrImagePull` (first failed pull) → `ImagePullBackOff` (kubelet backs off between retries). Phase is `Pending` because no container could ever be created. Events show *Failed to pull image … pull access denied / repository does not exist*. Fix: correct image name/tag or add an `imagePullSecret` for a private registry.

## 07 – Readiness probe

[`07-readiness.yaml`](./pod-lifecycle/07-readiness.yaml) – `httpGet /` on port 80, `initialDelaySeconds: 5`, `periodSeconds: 5`.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 07-readiness.yaml -n s10-lifecycle && kubectl get pod lifecycle-readiness -n s10-lifecycle -w   # watched for 20 s
pod/lifecycle-readiness created
NAME                  READY   STATUS              RESTARTS   AGE
lifecycle-readiness   0/1     ContainerCreating   0          1s
lifecycle-readiness   0/1     Running             0          1s
lifecycle-readiness   1/1     Running             0          6s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-readiness -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Running
      Started:      Wed, 07 Oct 2026 16:38:28 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  20s   default-scheduler  Successfully assigned s10-lifecycle/lifecycle-readiness to saniya-k8s
  Normal  Pulled     20s   kubelet            Container image "nginx:1.27" already present on machine
  Normal  Created    20s   kubelet            Created container nginx
  Normal  Started    20s   kubelet            Started container nginx
```

Breaking readiness on purpose (delete the page nginx serves → probe gets 403):

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl exec lifecycle-readiness -n s10-lifecycle -- rm /usr/share/nginx/html/index.html; sleep 12; kubectl get pod lifecycle-readiness -n s10-lifecycle
NAME                  READY   STATUS    RESTARTS   AGE
lifecycle-readiness   1/1     Running   0          33s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-readiness -n s10-lifecycle | sed -n '/^Conditions:/,/^Volumes:/p;/Readiness probe failed/p'
Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
  Warning  Unhealthy  2s (x2 over 7s)  kubelet            Readiness probe failed: HTTP probe failed with statuscode: 403
```

**Observation:** the container is `Running` immediately but READY stays `0/1` until the first successful probe after the 5 s delay, then `1/1` (`Ready=True`). When the probe started failing the pod went back to `0/1` and `Ready=False` – but it was **not restarted** (RESTARTS 0). A not-ready pod is just removed from Service endpoints. Readiness = *should I get traffic?*

## 08 – Liveness probe

[`08-liveness.yaml`](./pod-lifecycle/08-liveness.yaml) – app deletes `/tmp/healthy` after 20 s; probe `test -f /tmp/healthy` every 5 s, `failureThreshold: 2`.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 08-liveness.yaml -n s10-lifecycle && kubectl get pod lifecycle-liveness -n s10-lifecycle -w   # watched for 75 s
pod/lifecycle-liveness created
NAME                 READY   STATUS              RESTARTS   AGE
lifecycle-liveness   0/1     ContainerCreating   0          0s
lifecycle-liveness   1/1     Running             0          2s
lifecycle-liveness   1/1     Running             1 (1s ago)   62s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-liveness -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Running
      Started:      Wed, 07 Oct 2026 16:40:01 +0000
    Last State:     Terminated
      Reason:       Error
      Exit Code:    137
      Started:      Wed, 07 Oct 2026 16:39:01 +0000
      Finished:     Wed, 07 Oct 2026 16:40:01 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  75s                default-scheduler  Successfully assigned s10-lifecycle/lifecycle-liveness to saniya-k8s
  Warning  Unhealthy  45s (x2 over 50s)  kubelet            Liveness probe failed:
  Normal   Killing    45s                kubelet            Container app failed liveness probe, will be restarted
  Normal   Pulled     15s (x2 over 75s)  kubelet            Container image "busybox:1.36" already present on machine
  Normal   Created    15s (x2 over 75s)  kubelet            Created container app
  Normal   Started    15s (x2 over 75s)  kubelet            Started container app
```

**Observation:** after ~20 s the health file disappears, the liveness probe fails twice in a row (`failureThreshold: 2`), kubelet logs *Container app failed liveness probe, will be restarted* and **kills and restarts** the container (RESTARTS increments, `Last State: Terminated, exit 137` = SIGKILL after the grace period/stop). Liveness = *is the app still alive? if not, restart it*.

## 09 – Startup probe

[`09-startup.yaml`](./pod-lifecycle/09-startup.yaml) – slow app creates `/tmp/started` after 30 s; startup probe allows `10 × 5 s = 50 s`.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 09-startup.yaml -n s10-lifecycle && kubectl get pod lifecycle-startup -n s10-lifecycle -w   # watched for 45 s
pod/lifecycle-startup created
NAME                READY   STATUS              RESTARTS   AGE
lifecycle-startup   0/1     ContainerCreating   0          0s
lifecycle-startup   0/1     Running             0          1s
lifecycle-startup   1/1     Running             0          35s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl logs lifecycle-startup -n s10-lifecycle
Error from server: Get "https://192.0.2.2:10250/containerLogs/s10-lifecycle/lifecycle-startup/slow-app": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-startup -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Running
      Started:      Wed, 07 Oct 2026 16:40:16 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  52s                default-scheduler  Successfully assigned s10-lifecycle/lifecycle-startup to saniya-k8s
  Normal   Pulled     52s                kubelet            Container image "busybox:1.36" already present on machine
  Normal   Created    52s                kubelet            Created container slow-app
  Normal   Started    52s                kubelet            Started container slow-app
  Warning  Unhealthy  22s (x6 over 47s)  kubelet            Startup probe failed:
```

**Observation:** for ~30 s the pod is `Running` but `0/1` and the events show *Startup probe failed* (expected – app still booting). Once `/tmp/started` exists the probe succeeds, the container is marked `Started: True` and the pod becomes `1/1`, with **0 restarts**. A startup probe protects slow-starting apps: liveness/readiness probes are disabled until it succeeds, and only if it fails `failureThreshold` times is the container restarted.

## 10 – Init container

[`10-init-container.yaml`](./pod-lifecycle/10-init-container.yaml) – init container `setup` sleeps 10 s before the nginx app container may start.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 10-init-container.yaml -n s10-lifecycle && kubectl get pod lifecycle-init -n s10-lifecycle -w   # watched for 25 s
pod/lifecycle-init created
NAME             READY   STATUS     RESTARTS   AGE
lifecycle-init   0/1     Init:0/1   0          1s
lifecycle-init   0/1     Init:0/1   0          2s
lifecycle-init   0/1     PodInitializing   0          12s
lifecycle-init   1/1     Running           0          13s
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl logs lifecycle-init -n s10-lifecycle -c setup
Error from server: Get "https://192.0.2.2:10250/containerLogs/s10-lifecycle/lifecycle-init/setup": EOF
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-init -n s10-lifecycle | sed -n '/^Init Containers:/,/^Containers:/p' | grep -E '^  [a-z]|State:|Reason:|Exit Code:'; kubectl describe pod lifecycle-init -n s10-lifecycle | sed -n '/^Conditions:/,/^Volumes:/p' | grep -v '^Volumes:'; kubectl describe pod lifecycle-init -n s10-lifecycle | sed -n '/^Events:/,$p'
  setup:
    State:          Terminated
      Reason:       Completed
      Exit Code:    0
Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  32s   default-scheduler  Successfully assigned s10-lifecycle/lifecycle-init to saniya-k8s
  Normal  Pulled     32s   kubelet            Container image "busybox:1.36" already present on machine
  Normal  Created    32s   kubelet            Created container setup
  Normal  Started    32s   kubelet            Started container setup
  Normal  Pulled     21s   kubelet            Container image "nginx:1.27" already present on machine
  Normal  Created    21s   kubelet            Created container app
  Normal  Started    21s   kubelet            Started container app
```

**Observation:** STATUS goes `Init:0/1` → `PodInitializing` → `Running`. Events show the init container `setup` created/started first; the `app` container image is only pulled/started after `setup` exited with code 0 (`Terminated / Completed`). Init containers run sequentially to completion – used for waiting on dependencies, migrations, fetching config.

## 11 – Multi-container (sidecar)

[`11-multi-container.yaml`](./pod-lifecycle/11-multi-container.yaml) – nginx `app` + busybox `sidecar` in one pod.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 11-multi-container.yaml -n s10-lifecycle
pod/lifecycle-multi-container created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-multi-container -n s10-lifecycle -o wide
NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE         NOMINATED NODE   READINESS GATES
lifecycle-multi-container   2/2     Running   0          13s   10.42.0.38   saniya-k8s   <none>           <none>
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pod lifecycle-multi-container -n s10-lifecycle -o jsonpath='{range .status.containerStatuses[*]}{.name}{"\t"}{.image}{"\tready="}{.ready}{"\n"}{end}'
app	docker.io/library/nginx:1.27	ready=true
sidecar	docker.io/library/busybox:1.36	ready=true
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl logs lifecycle-multi-container -n s10-lifecycle -c sidecar
Error from server: Get "https://192.0.2.2:10250/containerLogs/s10-lifecycle/lifecycle-multi-container/sidecar": EOF
```

Containers in a pod share the network namespace – the sidecar reaches nginx on `localhost`:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl exec lifecycle-multi-container -n s10-lifecycle -c sidecar -- wget -qO- localhost:80 | grep -o '<title>.*</title>'
<title>Welcome to nginx!</title>
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-multi-container -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Running
      Started:      Wed, 07 Oct 2026 16:41:42 +0000
--
    State:          Running
      Started:      Wed, 07 Oct 2026 16:41:42 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  21s   default-scheduler  Successfully assigned s10-lifecycle/lifecycle-multi-container to saniya-k8s
  Normal  Pulled     20s   kubelet            Container image "nginx:1.27" already present on machine
  Normal  Created    20s   kubelet            Created container app
  Normal  Started    20s   kubelet            Started container app
  Normal  Pulled     20s   kubelet            Container image "busybox:1.36" already present on machine
  Normal  Created    20s   kubelet            Created container sidecar
  Normal  Started    20s   kubelet            Started container sidecar
```

**Observation:** READY `2/2` – the pod is `Ready` only when **all** its containers are ready. Each container has its own state, image and logs (`-c <name>`), but they share one IP and can talk over `localhost`.

## 12 – Graceful termination

[`12-termination.yaml`](./pod-lifecycle/12-termination.yaml) – traps `SIGTERM`, needs 10 s to clean up; `terminationGracePeriodSeconds: 20`.

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl apply -f 12-termination.yaml -n s10-lifecycle
pod/lifecycle-termination created
```

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl describe pod lifecycle-termination -n s10-lifecycle   # trimmed to State / Conditions / Events
    State:          Running
      Started:      Wed, 07 Oct 2026 16:42:03 +0000

Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  3s    default-scheduler  Successfully assigned s10-lifecycle/lifecycle-termination to saniya-k8s
  Normal  Pulled     3s    kubelet            Container image "busybox:1.36" already present on machine
  Normal  Created    3s    kubelet            Created container graceful-app
  Normal  Started    3s    kubelet            Started container graceful-app
```

Follow the logs in the background, then delete the pod and time it:

```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ (kubectl logs -f lifecycle-termination -n s10-lifecycle &) ; sleep 1; (sleep 4; kubectl get pod lifecycle-termination -n s10-lifecycle) & time kubectl delete pod lifecycle-termination -n s10-lifecycle
pod "lifecycle-termination" deleted
NAME                    READY   STATUS        RESTARTS   AGE
lifecycle-termination   1/1     Terminating   0          9s
Error from server: Get "https://192.0.2.2:10250/containerLogs/s10-lifecycle/lifecycle-termination/graceful-app?follow=true": EOF

real	0m11.231s
user	0m0.111s
sys	0m0.034s
```

**Observation:** on `kubectl delete` the pod becomes `Terminating`, kubelet sends **SIGTERM**; the trap prints *SIGTERM received; cleaning up…*, finishes in ~10 s and exits 0, so deletion took ~10 s (well under the 20 s grace period). If the app had not exited within `terminationGracePeriodSeconds`, kubelet would have sent **SIGKILL**. (A `preStop` hook, if defined, runs before SIGTERM.)

### All lifecycle pods at the end
```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments/pod-lifecycle$ kubectl get pods -n s10-lifecycle
NAME                        READY   STATUS             RESTARTS        AGE
lifecycle-crashloop         0/1     CrashLoopBackOff   5 (2m19s ago)   5m40s
lifecycle-failed            0/1     Error              0               6m2s
lifecycle-image-error       0/1     ImagePullBackOff   0               4m32s
lifecycle-init              1/1     Running            0               71s
lifecycle-liveness          1/1     Running            3 (18s ago)     3m19s
lifecycle-multi-container   2/2     Running            0               38s
lifecycle-pending           0/1     Pending            0               6m32s
lifecycle-readiness         0/1     Running            0               3m52s
lifecycle-running           1/1     Running            0               6m35s
lifecycle-startup           1/1     Running            0               2m3s
lifecycle-succeeded         0/1     Completed          0               6m25s
```

### Summary table

| # | YAML | Final STATUS | Phase | What causes it |
|---|---|---|---|---|
| 01 | running | `Running` 1/1 | Running | normal start |
| 02 | pending | `Pending` | Pending | scheduler can't fit 9Gi request (`Insufficient memory`) |
| 03 | succeeded | `Completed` | Succeeded | exit 0, `restartPolicy: Never` |
| 04 | failed | `Error` | Failed | exit 1, `restartPolicy: Never` |
| 05 | crashloopbackoff | `CrashLoopBackOff` | Running | exit 1 + `restartPolicy: Always` → restart with back-off |
| 06 | imagepullbackoff | `ImagePullBackOff` | Pending | image does not exist |
| 07 | readiness | `0/1` → `1/1` | Running | readiness probe gates traffic, no restart |
| 08 | liveness | Running, restarts ↑ | Running | failing liveness probe → container restarted |
| 09 | startup | `0/1` for 30 s → `1/1` | Running | startup probe waits for slow boot |
| 10 | init-container | `Init:0/1` → `Running` | Pending → Running | init container must complete first |
| 11 | multi-container | `2/2` | Running | app + sidecar share network |
| 12 | termination | `Terminating` → gone | – | SIGTERM handled within grace period |

### Cleanup
```console
saniya@saniya-devops:~/devops-homework/session-10-pods-replicasets-deployments$ kubectl delete namespace s10-rolling s10-bluegreen s10-canary s10-recreate s10-lifecycle
namespace "s10-rolling" deleted
namespace "s10-bluegreen" deleted
namespace "s10-canary" deleted
namespace "s10-recreate" deleted
namespace "s10-lifecycle" deleted
```

