# Kubernetes Volumes & Persistent Storage (Session 13 – Task 1)

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

[← back to Session 13 README](../README.md)

Container filesystems are **ephemeral** – when a container restarts or a Pod is deleted, everything written inside it is lost.
Kubernetes solves this with **volumes**. This document explains each storage building block and shows a real, executed example
of each one on my k3s cluster (all output is real). YAMLs are adapted from
[`devops-heros/session-13-storage-hpa-probes`](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session-13-storage-hpa-probes) (`01-volumes`, `02-persistent-storage`, `03-storageclass`).

## Overview

| Type | Lifetime of data | Who creates it | Typical use |
|---|---|---|---|
| **emptyDir** | Same as the **Pod** (survives container restarts, deleted with the Pod) | Kubernetes, automatically | scratch space, cache, sharing files between containers of one Pod |
| **hostPath** | Same as the **node's** directory | Node admin | node agents (logs, Docker socket), local testing – avoid for apps |
| **PersistentVolume (PV)** | Independent of any Pod (cluster resource) | Admin (static) or a provisioner (dynamic) | the actual piece of storage (disk, NFS, EBS, local path …) |
| **PersistentVolumeClaim (PVC)** | Until the claim is deleted (then reclaim policy decides) | Developer | a *request* for storage: size + access mode + class |
| **StorageClass** | – (template) | Admin | describes *how* to create PVs on demand (provisioner, parameters, reclaim policy, binding mode) |
| **Dynamic provisioning** | – | StorageClass provisioner | PV is created automatically when a PVC is created/used – no admin work |

```text
 Static provisioning                     Dynamic provisioning
 ───────────────────                     ────────────────────
 Admin ──creates──► PV (1Gi)             Admin ──creates once──► StorageClass (local-path)
                     ▲  bind                                           │ provisioner
 Dev  ──creates──► PVC (500Mi)           Dev ──creates──► PVC ─────────┘ creates PV automatically
                     ▲                                     ▲
 Pod ──volumes: persistentVolumeClaim──┘ Pod ──────────────┘
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f namespace.yaml
namespace/s13-storage created
```

---

## 1. emptyDir – shared scratch space inside one Pod

`emptyDir` is created **empty** when the Pod is scheduled onto a node and is **deleted for ever when the Pod is removed**.
All containers of the Pod can mount it – the classic *sidecar* pattern.

[`emptydir-pod.yaml`](./emptydir-pod.yaml) – a `writer` container appends a line every 5 s, a `web` (nginx) container serves the same directory:

```yaml
# emptyDir shared by TWO containers of the same Pod
# Adapted from devops-heros/session-13-storage-hpa-probes/01-volumes/emptydir-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-demo
  namespace: s13-storage
spec:
  containers:
    - name: writer                       # writes a line every 5 seconds
      image: busybox:1.36
      command: ["sh", "-c", "while true; do echo \"$(date '+%H:%M:%S') written by writer container\" >> /data/index.html; sleep 5; done"]
      volumeMounts:
        - name: shared-data
          mountPath: /data
      resources:
        limits: { cpu: 20m, memory: 16Mi }
    - name: web                          # serves the same files with nginx
      image: nginx:1.27-alpine
      volumeMounts:
        - name: shared-data
          mountPath: /usr/share/nginx/html
      resources:
        limits: { cpu: 50m, memory: 32Mi }
  volumes:
    - name: shared-data
      emptyDir: {}                       # created empty when the Pod starts, deleted with the Pod
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f emptydir-pod.yaml
pod/emptydir-demo created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pod emptydir-demo -n s13-storage -o wide
NAME            READY   STATUS    RESTARTS   AGE   IP            NODE
emptydir-demo   2/2     Running   0          23s   10.42.0.190   saniya-k8s
```

The **writer** container sees the file it writes:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl exec emptydir-demo -n s13-storage -c writer -- cat /data/index.html
E1007 16:30:11.567779   18797 websocket.go:296] Unknown stream id 1, discarding message
16:29:53 written by writer container
16:29:58 written by writer container
16:30:03 written by writer container
16:30:08 written by writer container
```

The **web** container (a *different* container, mounted at a different path) sees the very same file and serves it over HTTP:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl exec emptydir-demo -n s13-storage -c web -- ls -l /usr/share/nginx/html/
total 4
-rw-r--r--    1 root     root           148 Oct  7 16:30 index.html
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ curl -s http://$(kubectl get pod emptydir-demo -n s13-storage -o jsonpath='{.status.podIP}')/
16:29:53 written by writer container
16:29:58 written by writer container
16:30:03 written by writer container
16:30:08 written by writer container
```

Delete the Pod and create it again – the emptyDir is brand new:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete pod emptydir-demo -n s13-storage
pod "emptydir-demo" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f emptydir-pod.yaml && kubectl wait --for=condition=Ready pod/emptydir-demo -n s13-storage --timeout=180s && kubectl exec emptydir-demo -n s13-storage -c writer -- cat /data/index.html
pod/emptydir-demo created
pod/emptydir-demo condition met
16:30:50 written by writer container
```

**Observation:** both containers share one directory (different mount paths, same data). After the Pod was deleted, the old lines
were gone – the new Pod started with an empty volume containing only its own fresh line(s).

---

## 2. hostPath – a directory of the node

`hostPath` mounts a file/directory **from the node's filesystem** into the Pod. Data survives Pod deletion but is tied to **that node**
(a Pod rescheduled to another node sees different data) and gives the Pod access to the host – a security risk. Fine for learning,
node-level agents and single-node clusters; not recommended for application data.

[`hostpath-pod.yaml`](./hostpath-pod.yaml):

```yaml
# hostPath – mounts a directory of the NODE into the Pod
# Adapted from devops-heros/session-13-storage-hpa-probes/01-volumes/hostpath-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-demo
  namespace: s13-storage
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "echo \"hello from pod $(hostname) at $(date)\" >> /data/log.txt; sleep 3600"]
      volumeMounts:
        - name: host-storage
          mountPath: /data
      resources:
        limits: { cpu: 20m, memory: 16Mi }
  volumes:
    - name: host-storage
      hostPath:
        path: /tmp/s13-hostpath-data
        type: DirectoryOrCreate
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f hostpath-pod.yaml
pod/hostpath-demo created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl exec hostpath-demo -n s13-storage -- cat /data/log.txt
hello from pod hostpath-demo at Wed Oct  7 16:30:54 UTC 2026
```

The file really lives on the node (my VM *is* the k3s node `saniya-k8s`):

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ ls -l /tmp/s13-hostpath-data/ && cat /tmp/s13-hostpath-data/log.txt
total 4
-rw-r--r-- 1 root root 61 Oct  7 16:30 log.txt
hello from pod hostpath-demo at Wed Oct  7 16:30:54 UTC 2026
```

Delete and re-create the Pod – the old line is still there and a second one is appended:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete pod hostpath-demo -n s13-storage --grace-period=1
pod "hostpath-demo" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f hostpath-pod.yaml && kubectl wait --for=condition=Ready pod/hostpath-demo -n s13-storage --timeout=180s && kubectl exec hostpath-demo -n s13-storage -- cat /data/log.txt
pod/hostpath-demo created
pod/hostpath-demo condition met
hello from pod hostpath-demo at Wed Oct  7 16:30:54 UTC 2026
hello from pod hostpath-demo at Wed Oct  7 16:31:01 UTC 2026
```

---

## 3. PersistentVolume + PersistentVolumeClaim (static provisioning)

- **PersistentVolume (PV)** – a piece of storage in the cluster, a **cluster-scoped** object with a capacity, access modes
  (`ReadWriteOnce`, `ReadOnlyMany`, `ReadWriteMany`, `ReadWriteOncePod`) and a **reclaim policy** (`Retain` / `Delete`).
- **PersistentVolumeClaim (PVC)** – a **namespaced request** for storage by an application. Kubernetes **binds** the PVC to a PV
  that satisfies size, access mode and `storageClassName`. The Pod only references the PVC – it never needs to know the storage backend.

[`static-pv.yaml`](./static-pv.yaml) (admin) and [`static-pvc.yaml`](./static-pvc.yaml) (developer):

```yaml
# Static provisioning: the ADMIN creates the PersistentVolume by hand
# Adapted from devops-heros/session-13-storage-hpa-probes/02-persistent-storage/pv.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: s13-student-pv              # PVs are cluster-scoped (no namespace)
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual          # so the default (local-path) class doesn't grab the claim
  hostPath:
    path: /tmp/s13-student-data
    type: DirectoryOrCreate
---
# The DEVELOPER claims storage – Kubernetes binds it to a matching PV
# Adapted from devops-heros/session-13-storage-hpa-probes/02-persistent-storage/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: student-pvc
  namespace: s13-storage
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  resources:
    requests:
      storage: 500Mi
```

> `storageClassName: manual` is used on both sides; without it the PVC would get k3s' **default** StorageClass (`local-path`) and be dynamically provisioned instead of binding to my hand-made PV.

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f static-pv.yaml
persistentvolume/s13-student-pv created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pv s13-student-pv
NAME             CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
s13-student-pv   1Gi        RWO            Retain           Available           manual         <unset>                          0s
```

The PV is `Available`. Now the claim:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f static-pvc.yaml
persistentvolumeclaim/student-pvc created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pvc student-pvc -n s13-storage
NAME          STATUS   VOLUME           CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
student-pvc   Bound    s13-student-pv   1Gi        RWO            manual         <unset>                 3s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pv s13-student-pv
NAME             CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                     STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
s13-student-pv   1Gi        RWO            Retain           Bound    s13-storage/student-pvc   manual         <unset>                          3s
```

The 500Mi claim was bound to the 1Gi PV (a PVC gets the *whole* PV, so CAPACITY shows `1Gi`). Use it from a Pod – [`static-pod.yaml`](./static-pod.yaml):

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f static-pod.yaml
pod/storage-demo created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl exec storage-demo -n s13-storage -- sh -c 'echo "Student: Saniya Sanjiv Patil (24bcs10246)" > /data/student.txt; df -h /data; cat /data/student.txt'
Filesystem                Size      Used Available Use% Mounted on
/dev/vda                252.0G     29.9G     13.4G  69% /data
Student: Saniya Sanjiv Patil (24bcs10246)
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl describe pvc student-pvc -n s13-storage
Name:          student-pvc
Namespace:     s13-storage
StorageClass:  manual
Status:        Bound
Volume:        s13-student-pv
Labels:        <none>
Finalizers:    [kubernetes.io/pvc-protection]
Capacity:      1Gi
Access Modes:  RWO
VolumeMode:    Filesystem
Used By:       storage-demo
Events:        <none>
```

Delete the Pod, start it again → data is still there:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete pod storage-demo -n s13-storage --grace-period=1
pod "storage-demo" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f static-pod.yaml && kubectl wait --for=condition=Ready pod/storage-demo -n s13-storage --timeout=180s && kubectl exec storage-demo -n s13-storage -- cat /data/student.txt
pod/storage-demo created
pod/storage-demo condition met
Student: Saniya Sanjiv Patil (24bcs10246)
```

---

## 4. StorageClass & dynamic provisioning

A **StorageClass** is a *template* for creating PVs on demand: which **provisioner** to call (AWS EBS CSI, GCE PD, Azure Disk, NFS,
`rancher.io/local-path` …), its parameters, the `reclaimPolicy` of the PVs it creates and the `volumeBindingMode`.
With **dynamic provisioning**, a developer only writes a PVC that names a class (or uses the default class) and the provisioner
creates a matching PV automatically – no ticket to the storage admin.

k3s ships the `local-path` StorageClass (marked **default**):

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get storageclass
NAME                   PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
local-path (default)   rancher.io/local-path   Delete          WaitForFirstConsumer   false                  3h31m
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl describe storageclass local-path
Name:                  local-path
IsDefaultClass:        Yes
Annotations:           defaultVolumeType=local,objectset.rio.cattle.io/applied=H4sIAAAAAAAA/4yRz47UMAyHXwX53JYpnamqSBxg0V4QEhJoObuJOzVN4ypxi0areXeUMqDhwJ9j8ov9xZ+fARd+ophYAhhIKhHPVE1dqlhebjUUMHFwYODTj+jBY0pQwEyKDhXBPAOGIIrKElI+Ohpw9fokfp3p82UhMODFoocCpP9KVhNpFVkqi6qeMokz4i+5fAsUy/M2gYGpSXfJVhcv3nNwr984J+GfLQLOv/5T3sb9r6K0oM2V09pTmS5JaYbipzCbrVQ5ioGUdnmcypuJco/BgMaV4FqAx5787upP3BHTCAbqrhmak21Pw9Db5tAe20MzHJuhPnUH19m2w1cOe3fMTX+bbEEd8+USZeO8XIpgIGKwI8UMuHtWQMwD8PxRPNsLGHhHnjRr2fYdvuXgOJw/iMuAL8j6KPGRY9IHCWmdKcL1ewAAAP//KQ1Ko0kCAAA,objectset.rio.cattle.io/id=,objectset.rio.cattle.io/owner-gvk=k3s.cattle.io/v1, Kind=Addon,objectset.rio.cattle.io/owner-name=local-storage,objectset.rio.cattle.io/owner-namespace=kube-system,storageclass.kubernetes.io/is-default-class=true
Provisioner:           rancher.io/local-path
Parameters:            <none>
AllowVolumeExpansion:  <unset>
MountOptions:          <none>
ReclaimPolicy:         Delete
VolumeBindingMode:     WaitForFirstConsumer
Events:                <none>
```

[`dynamic-pvc.yaml`](./dynamic-pvc.yaml) – note there is **no PV** written by me:

```yaml
# Dynamic provisioning: only a PVC is written; the StorageClass' provisioner creates the PV.
# Adapted from devops-heros/session-13-storage-hpa-probes/03-storageclass/pvc.yaml
# (storageClassName "standard" is minikube's; on k3s the class is "local-path")
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dynamic-pvc
  namespace: s13-storage
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 500Mi
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f dynamic-pvc.yaml
persistentvolumeclaim/dynamic-pvc created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pvc dynamic-pvc -n s13-storage
NAME          STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
dynamic-pvc   Pending                                      local-path     <unset>                 3s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl describe pvc dynamic-pvc -n s13-storage | sed -n '/^Events:/,$p'
Events:
  Type    Reason                Age   From                         Message
  ----    ------                ----  ----                         -------
  Normal  WaitForFirstConsumer  3s    persistentvolume-controller  waiting for first consumer to be created before binding
```

`Pending` is expected: `local-path` uses `volumeBindingMode: WaitForFirstConsumer`, so the PV is only created once a Pod using the
claim is scheduled (so the volume is created on the node where the Pod runs). Deploy a consumer – [`dynamic-deployment.yaml`](./dynamic-deployment.yaml):

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl apply -f dynamic-deployment.yaml
deployment.apps/notes-app created
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pvc dynamic-pvc -n s13-storage
NAME          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
dynamic-pvc   Bound    pvc-a7188a8e-4dac-4a4f-9e6b-692151a9519d   500Mi      RWO            local-path     <unset>                 26s
```

A PV named `pvc-<uid>` was **created automatically** by the `rancher.io/local-path` provisioner:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pv
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                               STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-a7188a8e-4dac-4a4f-9e6b-692151a9519d   500Mi      RWO            Delete           Bound    s13-storage/dynamic-pvc             local-path     <unset>                          6s
pvc-e1fd58d1-077d-4cd5-b627-2f03b456f366   1Gi        RWO            Delete           Bound    s21-final/taskboard-postgres-data   local-path     <unset>                          124m
s13-student-pv                             1Gi        RWO            Retain           Bound    s13-storage/student-pvc             manual         <unset>                          38s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pv $(kubectl get pvc dynamic-pvc -n s13-storage -o jsonpath='{.spec.volumeName}') -o jsonpath='{.metadata.annotations.pv\.kubernetes\.io/provisioned-by}{"\n"}{.spec.local.path}{.spec.hostPath.path}{"\n"}'
rancher.io/local-path
/var/lib/rancher/k3s/storage/pvc-a7188a8e-4dac-4a4f-9e6b-692151a9519d_s13-storage_dynamic-pvc
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get events -n s13-storage --field-selector involvedObject.name=dynamic-pvc
LAST SEEN   TYPE     REASON                  OBJECT                              MESSAGE
26s         Normal   WaitForFirstConsumer    persistentvolumeclaim/dynamic-pvc   waiting for first consumer to be created before binding
15s         Normal   ExternalProvisioning    persistentvolumeclaim/dynamic-pvc   Waiting for a volume to be created either by the external provisioner 'rancher.io/local-path' or manually by the system
23s         Normal   Provisioning            persistentvolumeclaim/dynamic-pvc   External provisioner is provisioning volume for claim "s13-storage/dynamic-pvc"
6s          Normal   ProvisioningSucceeded   persistentvolumeclaim/dynamic-pvc   Successfully provisioned volume pvc-a7188a8e-4dac-4a4f-9e6b-692151a9519d
```

### Data persists across Pod deletion

Each new Pod appends one line to `/data/notes.txt` on startup. I delete the Pod twice; the Deployment creates replacements and they all find the earlier lines:

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl exec deploy/notes-app -n s13-storage -- cat /data/notes.txt
pod notes-app-6bbbf45498-69t28 started at 16:31:41
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete pod -n s13-storage -l app=notes-app --grace-period=1
pod "notes-app-6bbbf45498-69t28" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete pod -n s13-storage -l app=notes-app --grace-period=1
pod "notes-app-6bbbf45498-txm6q" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pods -n s13-storage -l app=notes-app
NAME                         READY   STATUS    RESTARTS   AGE
notes-app-6bbbf45498-vwq9m   1/1     Running   0          7s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl exec deploy/notes-app -n s13-storage -- cat /data/notes.txt
pod notes-app-6bbbf45498-69t28 started at 16:31:41
pod notes-app-6bbbf45498-txm6q started at 16:31:48
pod notes-app-6bbbf45498-vwq9m started at 16:31:54
```

---

## 5. Reclaim policy – what happens when the claim is deleted?

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete deploy notes-app -n s13-storage && kubectl delete pod storage-demo emptydir-demo -n s13-storage --grace-period=1
deployment.apps "notes-app" deleted
pod "storage-demo" deleted
pod "emptydir-demo" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete pvc dynamic-pvc student-pvc -n s13-storage
persistentvolumeclaim "dynamic-pvc" deleted
persistentvolumeclaim "student-pvc" deleted
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl get pv
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS     CLAIM                               STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-a7188a8e-4dac-4a4f-9e6b-692151a9519d   500Mi      RWO            Delete           Released   s13-storage/dynamic-pvc             local-path     <unset>                          60s
pvc-e1fd58d1-077d-4cd5-b627-2f03b456f366   1Gi        RWO            Delete           Bound      s21-final/taskboard-postgres-data   local-path     <unset>                          125m
s13-student-pv                             1Gi        RWO            Retain           Released   s13-storage/student-pvc             manual         <unset>                          92s
```

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ ls /tmp/s13-student-data/
student.txt
```

| PV | Created by | Reclaim policy | After PVC deletion |
|---|---|---|---|
| `pvc-…` (dynamic) | `local-path` provisioner | `Delete` (from the StorageClass) | PV **and** its data were removed automatically |
| `s13-student-pv` (static) | me | `Retain` | PV is `Released`, data still on disk – an admin must clean it / re-use it manually |

## Summary

- **emptyDir** → temporary, per-Pod, shared between containers; gone with the Pod.
- **hostPath** → node directory; survives Pods but tied to one node and a security risk.
- **PV** → the storage; **PVC** → the request; Pods use PVCs, so apps are decoupled from the storage backend.
- **StorageClass** → template + provisioner; **dynamic provisioning** creates PVs automatically when a PVC is used.
- Data on a PV **outlives Pods** – verified above by deleting Pods and reading the data back.

```console
saniya@saniya-devops:~/devops-homework/session-13-storage-hpa-probes/01-kubernetes-volumes$ kubectl delete pv s13-student-pv && kubectl delete namespace s13-storage
persistentvolume "s13-student-pv" deleted
namespace "s13-storage" deleted
```

