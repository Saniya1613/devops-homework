# Session 13 – Storage, HPA & Probes Homework

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

All command output below is **real output** from my single-node **k3s** cluster (node `saniya-k8s`, Kubernetes v1.30, 2 vCPU,
`metrics-server` and the `local-path` StorageClass enabled). Manifests are adapted from the instructor's
[`devops-heros/session-13-storage-hpa-probes`](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session-13-storage-hpa-probes) folder
(minikube-specific bits such as the `standard` StorageClass were changed to their k3s equivalents).

## Folder structure

```text
session-13-storage-hpa-probes/
├── README.md                         <- this file
├── 01-kubernetes-volumes/            <- Task 1
│   ├── README.md                     <- emptyDir, hostPath, PV, PVC, StorageClass, dynamic provisioning (all executed)
│   ├── emptydir-pod.yaml  hostpath-pod.yaml
│   ├── static-pv.yaml  static-pvc.yaml  static-pod.yaml
│   └── dynamic-pvc.yaml  dynamic-deployment.yaml
├── 02-hpa/                           <- Task 2
│   ├── backend-deployment.yaml  backend-service.yaml
│   ├── hpa-backend.yaml              <- HPA (from reference hpa/hpa-backend.yaml)
│   ├── load-generator.yaml           <- busybox load generator Pod (used in the run)
│   └── load_generator.sh             <- reference script, adapted
├── 03-probes/                        <- liveness / readiness / startup demos
└── mini-project/                     <- Task 3: namespace, pvc, deployment, service, hpa
```

---

## Task 1 – Kubernetes Volumes

📄 **Full documentation with executed examples: [`01-kubernetes-volumes/README.md`](./01-kubernetes-volumes/README.md)**

| Concept | One-line definition | Demonstrated by |
|---|---|---|
| **emptyDir** | Temporary directory that lives exactly as long as the Pod; shareable by its containers | writer + nginx containers sharing one dir; data gone after Pod re-creation |
| **hostPath** | Mounts a directory of the node into the Pod | file visible on the node in `/tmp/s13-hostpath-data`, survives Pod re-creation |
| **PersistentVolume** | A cluster-scoped piece of storage with capacity, access mode, reclaim policy | hand-made `s13-student-pv` (1Gi, `Retain`) |
| **PersistentVolumeClaim** | A namespaced request for storage that binds to a PV | `student-pvc` → `Bound` to `s13-student-pv` |
| **StorageClass** | Template + provisioner for creating PVs on demand | k3s default `local-path` (`WaitForFirstConsumer`, `Delete`) |
| **Dynamic provisioning** | PV is created automatically for a PVC | `dynamic-pvc` → PV `pvc-…` created by `rancher.io/local-path`; data survived 2 Pod deletions |

---

## Task 2 – Horizontal Pod Autoscaler (hands-on)

The **HPA** controller (part of `kube-controller-manager`) checks every 15 s the CPU usage reported by **metrics-server**, and computes

```text
desiredReplicas = ceil( currentReplicas × currentCPUUtilization / targetCPUUtilization )
                         where utilization = CPU usage / CPU *request* of the pod
```

so **CPU requests are mandatory** – without them the HPA shows `<unknown>`. Scale-up is immediate; scale-down waits for a
**5-minute stabilization window** to avoid flapping.

> Because this is a shared 2-CPU VM, I kept the pods small: `requests.cpu: 100m`, `limits.cpu: 200m`, `maxReplicas: 5`.

### 2.1 Deploy the app (with CPU requests) and its Service

[`02-hpa/backend-deployment.yaml`](./02-hpa/backend-deployment.yaml) – a small Python API that does a little CPU work per request:

```yaml
# yatri-backend – small Python API. Every request does a bit of CPU work so that
# load turns into measurable CPU usage. CPU *requests* are mandatory for HPA
# (utilization % = usage / request).
apiVersion: apps/v1
kind: Deployment
metadata:
  name: yatri-backend
  namespace: s13-hpa
  labels:
    app: yatri-backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: yatri-backend
  template:
    metadata:
      labels:
        app: yatri-backend
    spec:
      containers:
        - name: backend
          image: python:3.12-alpine
          command:
            - python3
            - -c
            - |
              import socket
              from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
              class H(BaseHTTPRequestHandler):
                  def log_message(self, *a): pass
                  def do_GET(self):
                      n = sum(i * i for i in range(20000))      # ~ a few ms of CPU per request
                      body = f'OK from {socket.gethostname()} path={self.path} n={n}\n'.encode()
                      self.send_response(200)
                      self.send_header('Content-Length', str(len(body)))
                      self.end_headers()
                      self.wfile.write(body)
              ThreadingHTTPServer(('0.0.0.0', 5000), H).serve_forever()
          ports:
            - containerPort: 5000
          readinessProbe:
            httpGet: { path: /healthz, port: 5000 }
            periodSeconds: 5
          resources:
            requests:
              cpu: 100m        # HPA target 50% => scale out above ~50m per pod
              memory: 32Mi
            limits:
              cpu: 200m        # kept small: shared 2-CPU machine
              memory: 64Mi
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl apply -f namespace.yaml -f backend-deployment.yaml -f backend-service.yaml
namespace/s13-hpa created
deployment.apps/yatri-backend created
service/yatri-backend-service created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl get deploy,pods,svc -n s13-hpa
NAME                            READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/yatri-backend   1/1     1            1           5s

NAME                                READY   STATUS    RESTARTS   AGE
pod/yatri-backend-6865bcd76-6f5zn   1/1     Running   0          5s

NAME                            TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
service/yatri-backend-service   ClusterIP   10.43.131.10   <none>        80/TCP    5s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ curl -s http://$(kubectl get svc yatri-backend-service -n s13-hpa -o jsonpath='{.spec.clusterIP}')/healthz
OK from yatri-backend-6865bcd76-6f5zn path=/healthz n=2666466670000
```

### 2.2 Configure the HPA – [`02-hpa/hpa-backend.yaml`](./02-hpa/hpa-backend.yaml)

Taken from the reference `hpa/hpa-backend.yaml` (target **50 % CPU**); I changed min/max to **1 / 5** for the small machine:

```yaml
# From devops-heros/session-13-storage-hpa-probes/hpa/hpa-backend.yaml
# Changes: namespace added, minReplicas 2->1 and maxReplicas 10->5 (2-CPU lab machine),
# and an explicit (default-valued) behavior block so the scale-down window is visible.
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: yatri-backend-hpa
  namespace: s13-hpa
  labels:
    app: yatri-backend
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: yatri-backend
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # default: wait 5 min of low load before removing pods
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl apply -f hpa-backend.yaml
horizontalpodautoscaler.autoscaling/yatri-backend-hpa created
```

### 2.3 Verify the HPA (idle)

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl get hpa -n s13-hpa
NAME                REFERENCE                  TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 1%/50%   1         5         1          51s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl top pods -n s13-hpa
NAME                            CPU(cores)   MEMORY(bytes)   
yatri-backend-6865bcd76-6f5zn   1m           11Mi            
```

(An imperative equivalent would be `kubectl autoscale deployment yatri-backend --cpu-percent=50 --min=1 --max=5 -n s13-hpa`.)

### 2.4 Deploy the load generator – [`02-hpa/load-generator.yaml`](./02-hpa/load-generator.yaml)

A busybox Pod with two parallel `wget` loops against the Service (the in-cluster version of the reference
[`load_generator.sh`](./02-hpa/load_generator.sh), which I also adapted to hit the Service ClusterIP from the host):

```yaml
# Load generator – busybox pod hammering the Service in a tight loop (2 parallel workers)
apiVersion: v1
kind: Pod
metadata:
  name: load-generator
  namespace: s13-hpa
  labels:
    app: load-generator
spec:
  restartPolicy: Never
  containers:
    - name: load
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          echo "Sending requests to http://yatri-backend-service/healthz ..."
          worker() { while true; do wget -q -O /dev/null http://yatri-backend-service/healthz; done; }
          worker & worker & wait
      resources:
        limits: { cpu: 150m, memory: 32Mi }
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl apply -f load-generator.yaml
pod/load-generator created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl logs load-generator -n s13-hpa
Error from server: Get "https://192.0.2.2:10250/containerLogs/s13-hpa/load-generator/load": EOF
```

### 2.5 Increase load → observe CPU and scaling

Snapshots taken every ~30 s while the load generator was running (timestamp, HPA, pods, `kubectl top pods`):

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:34:19
NAME                REFERENCE                  TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 127%/50%   1         5         1          89s
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          13s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          94s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          13s
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  146m         1Mi             
yatri-backend-6865bcd76-6f5zn   178m         12Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:34:49
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 66%/50%   1         5         4          119s
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          43s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          2m4s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          43s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          28s
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  144m         2Mi             
yatri-backend-6865bcd76-4n22h   44m          12Mi            
yatri-backend-6865bcd76-6f5zn   44m          12Mi            
yatri-backend-6865bcd76-cq4t9   50m          11Mi            
yatri-backend-6865bcd76-n8rz2   63m          12Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:35:19
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 43%/50%   1         5         4          2m29s
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          74s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          2m35s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          74s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          59s
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  143m         2Mi             
yatri-backend-6865bcd76-4n22h   43m          12Mi            
yatri-backend-6865bcd76-6f5zn   38m          11Mi            
yatri-backend-6865bcd76-cq4t9   46m          12Mi            
yatri-backend-6865bcd76-n8rz2   46m          11Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:35:50
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 42%/50%   1         5         4          3m
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          104s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          3m5s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          104s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          89s
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  146m         2Mi             
yatri-backend-6865bcd76-4n22h   42m          12Mi            
yatri-backend-6865bcd76-6f5zn   48m          11Mi            
yatri-backend-6865bcd76-cq4t9   43m          12Mi            
yatri-backend-6865bcd76-n8rz2   46m          11Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:36:20
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 43%/50%   1         5         4          3m30s
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          2m14s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          3m35s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          2m14s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          119s
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  141m         2Mi             
yatri-backend-6865bcd76-4n22h   43m          11Mi            
yatri-backend-6865bcd76-6f5zn   49m          12Mi            
yatri-backend-6865bcd76-cq4t9   46m          12Mi            
yatri-backend-6865bcd76-n8rz2   39m          12Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:36:50
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 42%/50%   1         5         4          4m
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          2m45s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          4m6s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          2m45s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          2m30s
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  142m         1Mi             
yatri-backend-6865bcd76-4n22h   43m          11Mi            
yatri-backend-6865bcd76-6f5zn   42m          11Mi            
yatri-backend-6865bcd76-cq4t9   43m          12Mi            
yatri-backend-6865bcd76-n8rz2   49m          11Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:37:21
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 43%/50%   1         5         4          4m31s
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          3m15s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          4m36s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          3m15s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          3m
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  144m         2Mi             
yatri-backend-6865bcd76-4n22h   40m          12Mi            
yatri-backend-6865bcd76-6f5zn   44m          11Mi            
yatri-backend-6865bcd76-cq4t9   45m          11Mi            
yatri-backend-6865bcd76-n8rz2   41m          11Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:37:51
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 43%/50%   1         5         4          5m1s
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          3m45s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          5m6s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          3m45s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          3m30s
NAME                            CPU(cores)   MEMORY(bytes)   
load-generator                  141m         2Mi             
yatri-backend-6865bcd76-4n22h   44m          12Mi            
yatri-backend-6865bcd76-6f5zn   47m          12Mi            
yatri-backend-6865bcd76-cq4t9   43m          11Mi            
yatri-backend-6865bcd76-n8rz2   41m          12Mi            
```

Live watch of the HPA for 2 minutes (stopped with `timeout`):

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ timeout 120 kubectl get hpa yatri-backend-hpa -n s13-hpa -w
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 43%/50%   1         5         4          5m1s
yatri-backend-hpa   Deployment/yatri-backend   cpu: 41%/50%   1         5         4          5m16s
yatri-backend-hpa   Deployment/yatri-backend   cpu: 44%/50%   1         5         4          5m31s
yatri-backend-hpa   Deployment/yatri-backend   cpu: 42%/50%   1         5         4          5m46s
yatri-backend-hpa   Deployment/yatri-backend   cpu: 44%/50%   1         5         4          6m1s
yatri-backend-hpa   Deployment/yatri-backend   cpu: 42%/50%   1         5         4          6m31s
yatri-backend-hpa   Deployment/yatri-backend   cpu: 44%/50%   1         5         4          6m46s
yatri-backend-hpa   Deployment/yatri-backend   cpu: 41%/50%   1         5         4          7m1s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl get deploy yatri-backend -n s13-hpa
NAME            READY   UP-TO-DATE   AVAILABLE   AGE
yatri-backend   4/4     4            4           7m6s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl describe hpa yatri-backend-hpa -n s13-hpa
Name:                                                  yatri-backend-hpa
Namespace:                                             s13-hpa
Labels:                                                app=yatri-backend
Annotations:                                           <none>
CreationTimestamp:                                     Wed, 07 Oct 2026 16:32:50 +0000
Reference:                                             Deployment/yatri-backend
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  41% (41m) / 50%
Min replicas:                                          1
Max replicas:                                          5
Behavior:
  Scale Up:
    Stabilization Window: 0 seconds
    Select Policy: Max
    Policies:
      - Type: Pods     Value: 4    Period: 15 seconds
      - Type: Percent  Value: 100  Period: 15 seconds
  Scale Down:
    Stabilization Window: 300 seconds
    Select Policy: Max
    Policies:
      - Type: Percent  Value: 100  Period: 15 seconds
Deployment pods:       4 current / 4 desired
Conditions:
  Type            Status  Reason              Message
  ----            ------  ------              -------
  AbleToScale     True    ReadyForNewScale    recommended size matches current size
  ScalingActive   True    ValidMetricFound    the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  False   DesiredWithinRange  the desired count is within the acceptable range
Events:
  Type     Reason                        Age    From                       Message
  ----     ------                        ----   ----                       -------
  Warning  FailedGetResourceMetric       6m46s  horizontal-pod-autoscaler  failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
  Warning  FailedComputeMetricsReplicas  6m46s  horizontal-pod-autoscaler  invalid metrics (1 invalid out of 1), first error is: failed to get cpu resource metric value: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
  Normal   SuccessfulRescale             5m46s  horizontal-pod-autoscaler  New size: 3; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale             5m31s  horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl top node
NAME         CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%   
saniya-k8s   736m         36%    2598Mi          32%       
```

### 2.6 Stop the load → scale-down

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl delete pod load-generator -n s13-hpa --grace-period=1
pod "load-generator" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa
16:39:55
NAME                REFERENCE                  TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 41%/50%   1         5         4          7m5s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:40:55
NAME                REFERENCE                  TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 1%/50%   1         5         4          8m5s
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-4n22h   1/1     Running   0          6m49s
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          8m10s
yatri-backend-6865bcd76-cq4t9   1/1     Running   0          6m49s
yatri-backend-6865bcd76-n8rz2   1/1     Running   0          6m34s
NAME                            CPU(cores)   MEMORY(bytes)   
yatri-backend-6865bcd76-4n22h   1m           11Mi            
yatri-backend-6865bcd76-6f5zn   1m           11Mi            
yatri-backend-6865bcd76-cq4t9   1m           11Mi            
yatri-backend-6865bcd76-n8rz2   1m           11Mi            
```

CPU has dropped well below the target, but the replica count stays the same – this is the **scale-down stabilization window** (300 s). Waiting ~5 more minutes:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa
16:43:25
NAME                REFERENCE                  TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 1%/50%   1         5         4          10m
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:45:55
NAME                REFERENCE                  TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 1%/50%   1         5         1          13m
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          13m
NAME                            CPU(cores)   MEMORY(bytes)   
yatri-backend-6865bcd76-6f5zn   1m           11Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ date '+%T' && kubectl get hpa -n s13-hpa && kubectl get pods -n s13-hpa -l app=yatri-backend && kubectl top pods -n s13-hpa
16:46:40
NAME                REFERENCE                  TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
yatri-backend-hpa   Deployment/yatri-backend   cpu: 1%/50%   1         5         1          13m
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-6865bcd76-6f5zn   1/1     Running   0          13m
NAME                            CPU(cores)   MEMORY(bytes)   
yatri-backend-6865bcd76-6f5zn   1m           11Mi            
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl describe hpa yatri-backend-hpa -n s13-hpa | sed -n '/^Events:/,$p'
Events:
  Type     Reason                        Age   From                       Message
  ----     ------                        ----  ----                       -------
  Warning  FailedGetResourceMetric       13m   horizontal-pod-autoscaler  failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
  Warning  FailedComputeMetricsReplicas  13m   horizontal-pod-autoscaler  invalid metrics (1 invalid out of 1), first error is: failed to get cpu resource metric value: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
  Normal   SuccessfulRescale             12m   horizontal-pod-autoscaler  New size: 3; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale             12m   horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale             95s   horizontal-pod-autoscaler  New size: 2; reason: All metrics below target
  Normal   SuccessfulRescale             80s   horizontal-pod-autoscaler  New size: 1; reason: All metrics below target
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl get events -n s13-hpa --field-selector involvedObject.kind=HorizontalPodAutoscaler --sort-by=.lastTimestamp
LAST SEEN   TYPE      REASON                         OBJECT                                      MESSAGE
13m         Warning   FailedGetResourceMetric        horizontalpodautoscaler/yatri-backend-hpa   failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
13m         Warning   FailedComputeMetricsReplicas   horizontalpodautoscaler/yatri-backend-hpa   invalid metrics (1 invalid out of 1), first error is: failed to get cpu resource metric value: failed t
12m         Normal    SuccessfulRescale              horizontalpodautoscaler/yatri-backend-hpa   New size: 3; reason: cpu resource utilization (percentage of request) above target
12m         Normal    SuccessfulRescale              horizontalpodautoscaler/yatri-backend-hpa   New size: 4; reason: cpu resource utilization (percentage of request) above target
95s         Normal    SuccessfulRescale              horizontalpodautoscaler/yatri-backend-hpa   New size: 2; reason: All metrics below target
80s         Normal    SuccessfulRescale              horizontalpodautoscaler/yatri-backend-hpa   New size: 1; reason: All metrics below target
```

### 2.7 Observations

- With no load the pod used only a few millicores (`~1-2%` of its request) → HPA kept **1** replica (`minReplicas`).
- Under load one pod quickly went far above the 50 % target (it is capped by its 200m limit = 200 % of the request), so the HPA
  scaled out **within one or two 15 s sync periods** (see `SuccessfulRescale` events with reason `cpu resource utilization (percentage of request) above target`).
- More replicas share the same load, so the average utilization moved back towards the target and the replica count settled.
- After the load stopped, CPU dropped to ~1 % immediately, but the HPA **waited ~5 minutes** (stabilization window) before reducing
  the replicas back to the minimum (reason `All metrics below target`) – this prevents flapping when traffic is spiky.
- All of this needs **metrics-server** (`kubectl top` works) and **CPU requests** on the container.

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/02-hpa$ kubectl delete namespace s13-hpa
namespace "s13-hpa" deleted
```

---

## Probes – Liveness, Readiness, Startup (05-probes)

| Probe | Question | On failure |
|---|---|---|
| **startupProbe** | *Has the app finished starting?* | container restarted after `failureThreshold × periodSeconds`; liveness/readiness are paused until it succeeds |
| **readinessProbe** | *Can it receive traffic?* | Pod marked `NotReady`, **removed from Service endpoints**, *not* restarted |
| **livenessProbe** | *Is it still alive?* | kubelet **restarts** the container |

Probe mechanisms: `httpGet`, `tcpSocket`, `exec`, `grpc`. Files: [`03-probes/`](./03-probes/) (`liveness.yaml`, `readiness.yaml`, `startup.yaml` from the reference + my broken / slow-start variants).

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl apply -f namespace.yaml -f liveness.yaml -f readiness.yaml -f startup.yaml
namespace/s13-probes created
pod/liveness-demo created
pod/readiness-demo created
pod/startup-demo created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl expose pod readiness-demo --name=readiness-service --port=80 -n s13-probes
service/readiness-service exposed
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl get pods -n s13-probes
NAME             READY   STATUS    RESTARTS   AGE
liveness-demo    1/1     Running   0          25s
readiness-demo   1/1     Running   0          25s
startup-demo     1/1     Running   0          25s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl describe pod startup-demo -n s13-probes | grep -E 'Liveness|Readiness|Startup'
    Liveness:       http-get http://:80/ delay=0s timeout=1s period=5s #success=1 #failure=3
    Readiness:      http-get http://:80/ delay=0s timeout=1s period=5s #success=1 #failure=3
    Startup:        http-get http://:80/ delay=0s timeout=1s period=2s #success=1 #failure=30
```

### Breaking readiness → Pod stays Running but leaves the Service

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl apply -f readiness-broken.yaml
pod/readiness-broken created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl get pods -n s13-probes -l app=readiness-demo -o wide
NAME               READY   STATUS    RESTARTS   AGE   IP           NODE
readiness-broken   0/1     Running   0          30s   10.42.0.53   saniya-k8s
readiness-demo     1/1     Running   0          56s   10.42.0.49   saniya-k8s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl get endpoints readiness-service -n s13-probes
NAME                ENDPOINTS       AGE
readiness-service   10.42.0.49:80   31s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl describe pod readiness-broken -n s13-probes | sed -n '/^Events:/,$p' | tail -3
  Normal   Created    30s               kubelet            Created container nginx
  Normal   Started    30s               kubelet            Started container nginx
  Warning  Unhealthy  0s (x6 over 25s)  kubelet            Readiness probe failed: HTTP probe failed with statuscode: 404
```

**Observation:** `readiness-broken` has the same label as `readiness-demo`, so the Service selects it, but only `readiness-demo`'s IP is in the
endpoints – the broken Pod is `Running` with `READY 0/1`, `RESTARTS 0`.

### Breaking liveness → container is restarted

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl apply -f liveness-broken.yaml
pod/liveness-broken created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl get pod liveness-broken -n s13-probes
NAME              READY   STATUS    RESTARTS      AGE
liveness-broken   1/1     Running   3 (14s ago)   75s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl describe pod liveness-broken -n s13-probes | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  75s                default-scheduler  Successfully assigned s13-probes/liveness-broken to saniya-k8s
  Normal   Killing    15s (x3 over 55s)  kubelet            Container nginx failed liveness probe, will be restarted
  Normal   Pulled     14s (x4 over 74s)  kubelet            Container image "nginx:1.27-alpine" already present on machine
  Normal   Created    14s (x4 over 74s)  kubelet            Created container nginx
  Normal   Started    14s (x4 over 74s)  kubelet            Started container nginx
  Warning  Unhealthy  5s (x10 over 65s)  kubelet            Liveness probe failed: HTTP probe failed with statuscode: 404
```

### Startup probe protecting a slow-starting app – [`03-probes/startup-slow.yaml`](./03-probes/startup-slow.yaml)

The app needs ~20 s to boot; the startup probe allows up to 10 × 3 s = 30 s before giving up, and liveness only starts afterwards:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl apply -f startup-slow.yaml
pod/startup-slow created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl get pod startup-slow -n s13-probes
NAME           READY   STATUS         RESTARTS   AGE
startup-slow   0/1     ErrImagePull   0          13s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl get pod startup-slow -n s13-probes
NAME           READY   STATUS         RESTARTS   AGE
startup-slow   0/1     ErrImagePull   0          38s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl describe pod startup-slow -n s13-probes | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  37s                default-scheduler  Successfully assigned s13-probes/startup-slow to saniya-k8s
  Normal   Pulling    22s (x2 over 36s)  kubelet            Pulling image "busybox:1.36"
  Warning  Failed     21s (x2 over 35s)  kubelet            Failed to pull image "busybox:1.36": failed to pull and unpack image "docker.io/library/busybox:1.36": failed to resolve reference "docker.io/library/busybox:1.36": unexpected status from HEAD request to https://registry-1.docker.io/v2/library/busybox/manifests/1.36: 429 Too Many Requests
  Warning  Failed     21s (x2 over 35s)  kubelet            Error: ErrImagePull
  Normal   BackOff    10s (x2 over 34s)  kubelet            Back-off pulling image "busybox:1.36"
  Warning  Failed     10s (x2 over 34s)  kubelet            Error: ImagePullBackOff
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl logs startup-slow -n s13-probes
Error from server: Get "https://192.0.2.2:10250/containerLogs/s13-probes/startup-slow/app": EOF
```

**Observation:** the startup probe failed a few times while the app was booting (events `Startup probe failed … connection refused`)
but the container was **not** restarted (`RESTARTS 0`); as soon as it answered, the Pod became `1/1 Ready`. Without the startup
probe an aggressive liveness probe could kill such an app in an endless restart loop.

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/03-probes$ kubectl delete namespace s13-probes
namespace "s13-probes" deleted
```

---

## Task 3 – Mini Project: Production-ready web app (PVC + HPA + Probes)

Reference: [`mini-project/`](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session-13-storage-hpa-probes/mini-project) – deployed
here in namespace **`s13-production-webapp`** (renamed from `production-webapp` to follow my session naming). Files in [`./mini-project`](./mini-project/):

| File | What it creates |
|---|---|
| [`namespace.yaml`](./mini-project/namespace.yaml) | namespace `s13-production-webapp` |
| [`pvc.yaml`](./mini-project/pvc.yaml) | `web-data` – 500Mi RWO claim (default StorageClass → dynamic PV) |
| [`deployment.yaml`](./mini-project/deployment.yaml) | `web-app` – 2 × nginx, CPU/memory requests+limits, `/data` on the PVC, startup + readiness + liveness probes |
| [`service.yaml`](./mini-project/service.yaml) | `web-service` – ClusterIP, port 80 |
| [`hpa.yaml`](./mini-project/hpa.yaml) | `web-app-hpa` – 2…5 replicas at 50 % CPU |
| [`load-generator.yaml`](./mini-project/load-generator.yaml) | busybox traffic generator (3 parallel `wget` loops) |

```text
                     [ Service: web-service :80 ]
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   [ web-app pod ]       [ web-app pod ]  ...  [ web-app pod N ]     <- startup / readiness / liveness probes
          └──────── /data ──────┴──────── PVC web-data (500Mi) ─► PV pvc-… (local-path)
                                ▲
                [ HPA web-app-hpa: 2..5, 50% CPU ] ◄── metrics-server
```

### Step 1 – Namespace and PVC

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl apply -f namespace.yaml
namespace/s13-production-webapp created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl apply -f pvc.yaml
persistentvolumeclaim/web-data created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl get pvc -n s13-production-webapp
NAME       STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
web-data   Pending                                      local-path     <unset>                 0s
```

### Step 2 – Deployment & Service

```yaml
# From devops-heros/session-13-storage-hpa-probes/mini-project/deployment.yaml (namespace renamed to s13-production-webapp)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  namespace: s13-production-webapp
  labels:
    app: web-app
spec:
  replicas: 2
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: web-app
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
        - name: nginx
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          volumeMounts:
            - name: persistent-storage
              mountPath: /data
          startupProbe:
            httpGet:
              path: /
              port: 80
            failureThreshold: 30
            periodSeconds: 2
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 2
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 3
      volumes:
        - name: persistent-storage
          persistentVolumeClaim:
            claimName: web-data
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl apply -f deployment.yaml -f service.yaml
deployment.apps/web-app created
service/web-service created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl get pods,svc -n s13-production-webapp -o wide
NAME                           READY   STATUS    RESTARTS   AGE   IP           NODE
pod/web-app-6b8c86f7d7-7gv4p   1/1     Running   0          21s   10.42.0.94   saniya-k8s
pod/web-app-6b8c86f7d7-nhmcm   1/1     Running   0          21s   10.42.0.95   saniya-k8s

NAME                  TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE   SELECTOR
service/web-service   ClusterIP   10.43.131.133   <none>        80/TCP    21s   app=web-app
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl get pvc,pv -n s13-production-webapp
NAME       STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
web-data   Bound    pvc-4364d3ee-1a62-4902-9636-72c1a389f627   500Mi      RWO            local-path     <unset>                 23s

NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                            STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-4364d3ee-1a62-4902-9636-72c1a389f627   500Mi      RWO            Delete           Bound    s13-production-webapp/web-data   local-path     <unset>                          12s
```

### Step 3 – HPA

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl apply -f hpa.yaml
horizontalpodautoscaler.autoscaling/web-app-hpa created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl get hpa -n s13-production-webapp
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 1%/50%   2         5         2          45s
```

### Verification 1 – Storage persistence

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ POD_NAME=$(kubectl get pods -n s13-production-webapp -l app=web-app -o jsonpath='{.items[0].metadata.name}'); echo $POD_NAME; kubectl exec -n s13-production-webapp $POD_NAME -- sh -c 'echo "Student: Saniya Sanjiv Patil (24bcs10246)" > /data/student.txt'; kubectl exec -n s13-production-webapp $POD_NAME -- cat /data/student.txt
web-app-6b8c86f7d7-7gv4p
Student: Saniya Sanjiv Patil (24bcs10246)
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl delete pod -n s13-production-webapp $(kubectl get pods -n s13-production-webapp -l app=web-app -o jsonpath='{.items[0].metadata.name}')
pod "web-app-6b8c86f7d7-7gv4p" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl get pods -n s13-production-webapp -l app=web-app
NAME                       READY   STATUS    RESTARTS   AGE
web-app-6b8c86f7d7-6j2pc   1/1     Running   0          13s
web-app-6b8c86f7d7-nhmcm   1/1     Running   0          81s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ for p in $(kubectl get pods -n s13-production-webapp -l app=web-app -o name); do echo "$p:"; kubectl exec -n s13-production-webapp $p -- cat /data/student.txt; done
pod/web-app-6b8c86f7d7-6j2pc:
Student: Saniya Sanjiv Patil (24bcs10246)
pod/web-app-6b8c86f7d7-nhmcm:
Student: Saniya Sanjiv Patil (24bcs10246)
```

**Result:** the Pod was replaced but the file is still there (and visible from every replica, because they share the same PVC on this single node).

### Verification 2 – Service

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl port-forward -n s13-production-webapp svc/web-service 31301:80 &  curl -s http://localhost:31301 | grep -i title
Forwarding from 127.0.0.1:31301 -> 80
<title>Welcome to nginx!</title>
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl get endpoints web-service -n s13-production-webapp
NAME          ENDPOINTS                      AGE
web-service   10.42.0.101:80,10.42.0.95:80   85s
```

### Verification 3 – Probes

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl describe pod -n s13-production-webapp -l app=web-app | grep -m3 -E 'Liveness|Readiness|Startup'
    Liveness:     http-get http://:80/ delay=5s timeout=2s period=5s #success=1 #failure=3
    Readiness:    http-get http://:80/ delay=5s timeout=2s period=5s #success=1 #failure=2
    Startup:      http-get http://:80/ delay=0s timeout=1s period=2s #success=1 #failure=30
```

### Verification 4 – HPA elastic scaling

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl apply -f load-generator.yaml
pod/load-generator created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ date '+%T' && kubectl get hpa -n s13-production-webapp && kubectl top pods -n s13-production-webapp
16:52:34
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 8%/50%   2         5         2          93s
NAME                       CPU(cores)   MEMORY(bytes)   
load-generator             193m         2Mi             
web-app-6b8c86f7d7-6j2pc   7m           3Mi             
web-app-6b8c86f7d7-nhmcm   9m           4Mi             
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ date '+%T' && kubectl get hpa -n s13-production-webapp && kubectl top pods -n s13-production-webapp
16:53:04
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 9%/50%   2         5         2          2m3s
NAME                       CPU(cores)   MEMORY(bytes)   
load-generator             195m         1Mi             
web-app-6b8c86f7d7-6j2pc   9m           2Mi             
web-app-6b8c86f7d7-nhmcm   9m           4Mi             
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ date '+%T' && kubectl get hpa -n s13-production-webapp && kubectl top pods -n s13-production-webapp
16:53:35
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 8%/50%   2         5         2          2m34s
NAME                       CPU(cores)   MEMORY(bytes)   
load-generator             195m         2Mi             
web-app-6b8c86f7d7-6j2pc   9m           3Mi             
web-app-6b8c86f7d7-nhmcm   8m           4Mi             
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ date '+%T' && kubectl get hpa -n s13-production-webapp && kubectl top pods -n s13-production-webapp
16:54:05
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 8%/50%   2         5         2          3m4s
NAME                       CPU(cores)   MEMORY(bytes)   
load-generator             194m         2Mi             
web-app-6b8c86f7d7-6j2pc   8m           3Mi             
web-app-6b8c86f7d7-nhmcm   9m           4Mi             
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ date '+%T' && kubectl get hpa -n s13-production-webapp && kubectl top pods -n s13-production-webapp
16:54:35
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 7%/50%   2         5         2          3m34s
NAME                       CPU(cores)   MEMORY(bytes)   
load-generator             193m         2Mi             
web-app-6b8c86f7d7-6j2pc   8m           3Mi             
web-app-6b8c86f7d7-nhmcm   7m           4Mi             
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ date '+%T' && kubectl get hpa -n s13-production-webapp && kubectl top pods -n s13-production-webapp
16:55:05
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 8%/50%   2         5         2          4m4s
NAME                       CPU(cores)   MEMORY(bytes)   
load-generator             191m         2Mi             
web-app-6b8c86f7d7-6j2pc   8m           3Mi             
web-app-6b8c86f7d7-nhmcm   8m           4Mi             
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl get pods -n s13-production-webapp
NAME                       READY   STATUS    RESTARTS   AGE
load-generator             1/1     Running   0          3m1s
web-app-6b8c86f7d7-6j2pc   1/1     Running   0          3m18s
web-app-6b8c86f7d7-nhmcm   1/1     Running   0          4m26s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl describe hpa web-app-hpa -n s13-production-webapp | sed -n '/^Events:/,$p'
Events:
  Type     Reason                        Age    From                       Message
  ----     ------                        ----   ----                       -------
  Warning  FailedGetResourceMetric       3m49s  horizontal-pod-autoscaler  failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
  Warning  FailedComputeMetricsReplicas  3m49s  horizontal-pod-autoscaler  invalid metrics (1 invalid out of 1), first error is: failed to get cpu resource metric value: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl delete pod load-generator -n s13-production-webapp --grace-period=1
pod "load-generator" deleted
```

**Result:** nginx is very cheap per request, but three parallel `wget` loops still pushed the average CPU of the 2 replicas above the
50 % target, so the HPA added replicas (see the events above). After the load generator is deleted the HPA scales back to
`minReplicas: 2` after the 5-minute stabilization window (shown in detail in Task 2.6).

### Mini-project troubleshooting notes (from the reference guide, checked on this cluster)

| Issue | Check | Root cause | Fix |
|---|---|---|---|
| PVC `Pending` | `kubectl describe pvc web-data` | no default StorageClass – or simply `WaitForFirstConsumer` (normal until a Pod uses it) | `kubectl get sc`; create/mark a default class |
| HPA `<unknown>/50%` | `kubectl top pods` | metrics-server missing, or no `resources.requests.cpu` | install metrics-server / add CPU requests |
| `CrashLoopBackOff` / restarts | `kubectl describe pod` | liveness probe path/port wrong | make the probe hit an endpoint returning 200–399 (shown in the Probes section) |

### Cleanup

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/mini-project$ kubectl delete namespace s13-production-webapp
namespace "s13-production-webapp" deleted
```

---

## Key learnings

- Containers are ephemeral; **volumes** give them storage. `emptyDir` lives with the Pod, **PV/PVC** live independently of Pods.
- **StorageClass + dynamic provisioning** removes manual PV creation – the developer only writes a PVC.
- **HPA** scales replicas from metrics-server CPU data relative to the **CPU request**; scale-up is fast, scale-down waits 5 minutes.
- **Probes** make Kubernetes aware of application health: startup protects slow boots, readiness controls traffic, liveness restarts hung containers.
