# Kubernetes Deployment: Python Flask Application + Authenticated MongoDB

An end-to-end implementation for containerizing and deploying a scalable, authenticated Python Flask API connected to MongoDB on a local Kubernetes cluster (Minikube).

---

## Table of Contents
1. [Project Overview & Architecture](#project-overview--architecture)
2. [Repository Layout](#repository-layout)
3. [Prerequisites](#prerequisites)
4. [Part 1: Local Development & Verification](#part-1-local-development--verification)
   - [Virtual Environment Explanation](#benefits-of-using-a-python-virtual-environment)
5. [Docker Containerization & Image Push](#docker-containerization--image-push)
6. [Kubernetes Deployment Guide (Minikube)](#kubernetes-deployment-guide-minikube)
   - [Step 1: Start Minikube & Enable Metrics Server](#step-1-start-minikube--enable-metrics-server)
   - [Step 2: Create Namespace & Local Secrets](#step-2-create-namespace--local-secrets)
   - [Step 3: Deploy MongoDB (PV, PVC, ConfigMap, Services, StatefulSet)](#step-3-deploy-mongodb)
   - [Step 4: Build Image & Deploy Flask (ConfigMap, Deployment, Service)](#step-4-build-image--deploy-flask)
   - [Step 5: Configure Horizontal Pod Autoscaler (HPA)](#step-5-configure-horizontal-pod-autoscaler-hpa)
7. [Accessing the Application](#accessing-the-application)
8. [Technical Explanations](#technical-explanations)
   - [Kubernetes DNS Resolution for Inter-Pod Communication](#kubernetes-dns-resolution-for-inter-pod-communication)
   - [Resource Requests and Limits Explained](#resource-requests-and-limits-explained)
9. [Design Choices & Trade-off Analysis](#design-choices--trade-off-analysis)
10. [Testing Scenarios & Evidence (Cookie Points)](#testing-scenarios--evidence-cookie-points)
    - [Test 1: CRUD & API Verification](#test-1-crud--api-verification)
    - [Test 2: Database Persistence Verification](#test-2-database-persistence-verification)
    - [Test 3: High Traffic Simulation & Autoscaling (HPA)](#test-3-high-traffic-simulation--autoscaling-hpa)
    - [Issues Encountered & Solutions](#issues-encountered--solutions)
11. [Cleanup](#cleanup)

---

## Project Overview & Architecture

This repository delivers a resilient cloud-native application consisting of:
- **Stateless Flask API (`Deployment`, min 2, max 5 replicas)**: Serves HTTP endpoints, backed by production-ready `gunicorn` WSGI server, with liveness, readiness, and startup health probes.
- **Stateful MongoDB Database (`StatefulSet`, 1 replica)**: Configured with role-based authentication, non-root application user, persistent data storage via Kubernetes `PersistentVolume` and `PersistentVolumeClaim`.
- **Internal Service Networking**: Headless Service for StatefulSet identity and `ClusterIP` Service for database access.
- **Client Access**: `NodePort` Service (port 30080) and `kubectl port-forward` compatibility.
- **Autoscaling**: Kubernetes `HorizontalPodAutoscaler` (HPA v2) automatically scaling Flask between 2 and 5 pods when average CPU exceeds 70%.

```
                             [ Local Developer Machine ]
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   │                                           │
         (Option A: NodePort)                        (Option B: port-forward)
        http://<minikube-ip>:30080                   http://localhost:5000:80
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         ▼
                           ┌───────────────────────────┐
                           │   flask-service (NodePort)│
                           │   ClusterIP: 10.96.x.x:80 │
                           └─────────────┬─────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
         ┌───────────────────┐                       ┌───────────────────┐
         │     flask-pod-1   │                       │    flask-pod-2    │
         │  (Gunicorn WSGI)  │                       │  (Gunicorn WSGI)  │
         │  Port 5000 (app)  │                       │  Port 5000 (app)  │
         └─────────┬─────────┘                       └─────────┬─────────┘
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         │ DNS: mongodb.flask-demo.svc.cluster.local:27017
                                         ▼
                           ┌───────────────────────────┐
                           │      mongodb Service      │
                           │     (ClusterIP: 27017)    │
                           └─────────────┬─────────────┘
                                         │
                                         ▼
                           ┌───────────────────────────┐
                           │    mongodb-0 (Pod)        │
                           │   StatefulSet (mongo:8.0) │
                           └─────────────┬─────────────┘
                                         │ Mount: /data/db
                                         ▼
                           ┌───────────────────────────┐
                           │      mongodb-pvc (1Gi)    │
                           │  Bound to mongodb-pv (PV) │
                           └───────────────────────────┘
```

---

## Repository Layout

```
.
├── Dockerfile                      # Production container definition (Gunicorn, non-root)
├── .dockerignore                   # Prevents dev files from leaking into image
├── .gitignore                      # Excludes local secrets, environments, and caches
├── .env.example                    # Template for environment variables
├── README.md                       # Comprehensive guide and documentation
├── app/
│   ├── app.py                      # Flask API with auth, endpoints, health probes
│   └── requirements.txt            # Python dependencies (Flask 3, PyMongo 4, Gunicorn)
├── mongo/
│   ├── 01-create-app-user.sh       # Bash initialization script for Mongo app user
│   └── 01-create-app-user.js       # JS equivalent for mongosh
├── k8s/
│   ├── 00-namespace.yaml           # Dedicated namespace (flask-demo)
│   ├── 01-mongodb-init-configmap.yaml # Mounted init script for user creation
│   ├── 02-mongodb-pv.yaml          # PersistentVolume (1Gi, hostPath)
│   ├── 03-mongodb-pvc.yaml         # PersistentVolumeClaim (1Gi)
│   ├── 04-mongodb-headless-service.yaml # Headless Service for StatefulSet
│   ├── 05-mongodb-service.yaml     # Internal ClusterIP Service for MongoDB
│   ├── 06-mongodb-statefulset.yaml # MongoDB StatefulSet with auth & health checks
│   ├── 07-flask-configmap.yaml     # Non-sensitive configuration (Host, Port, DB)
│   ├── 08-flask-deployment.yaml    # Flask Deployment (2 replicas, probes, resources)
│   ├── 09-flask-service.yaml       # NodePort Service exposing Flask
│   └── 10-flask-hpa.yaml           # HorizontalPodAutoscaler (70% CPU, 2-5 replicas)
└── tests/
    ├── test_api.py                 # Automated smoke & HPA CPU stress test suite
    ├── test_api.ps1                # PowerShell smoke tests
    └── test_api.sh                 # Bash smoke tests
```

---

## Prerequisites

Ensure the following tools are installed:
- **Python 3.10+** (tested with Python 3.12)
- **Docker Desktop** (running with Linux containers)
- **kubectl** (Kubernetes CLI)
- **Minikube** (local Kubernetes cluster)
- **curl** or **PowerShell** for API validation

---

## Part 1: Local Development & Verification

### Benefits of Using a Python Virtual Environment
1. **Dependency Isolation**: Prevents dependency conflicts between different projects (e.g., project A requiring Flask 2.0 vs project B requiring Flask 3.0).
2. **System Protection**: Avoids polluting the global Python installation or breaking operating system-managed packages.
3. **Reproducibility**: Guarantees that dependencies exported via `pip freeze` match the project's exact runtime requirements.
4. **Security & Least Privilege**: Virtual environments can be created and managed without administrator/root permissions.

### Local Run Instructions

1. **Create and Activate Virtual Environment**:
   ```bash
   # On Windows (PowerShell):
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # On Linux/macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r app/requirements.txt
   ```

3. **Start Local MongoDB Container**:
   ```bash
   docker run -d --name mongodb-local -p 27017:27017 \
     -e MONGO_INITDB_ROOT_USERNAME=admin_root \
     -e MONGO_INITDB_ROOT_PASSWORD=admin_password \
     -e MONGO_INITDB_DATABASE=flask_db \
     mongo:8.0
   ```

4. **Initialize Application User**:
   ```bash
   docker exec mongodb-local mongosh -u admin_root -p admin_password --authenticationDatabase admin --eval "
   use flask_db;
   db.createUser({
     user: 'local_app',
     pwd: 'local_password',
     roles: [{ role: 'readWrite', db: 'flask_db' }]
   });"
   ```

5. **Run the Flask Application**:
   ```bash
   # PowerShell
   $env:MONGODB_HOST="localhost"
   $env:MONGODB_PORT="27017"
   $env:MONGODB_DATABASE="flask_db"
   $env:MONGO_APP_USERNAME="local_app"
   $env:MONGO_APP_PASSWORD="local_password"
   python app/app.py
   ```

6. **Verify Endpoints**:
   ```bash
   curl http://localhost:5000/
   curl -X POST http://localhost:5000/data -H "Content-Type: application/json" -d "{\"sampleKey\":\"sampleValue\"}"
   curl http://localhost:5000/data
   ```

---

## Docker Containerization & Image Push

The Flask application is packaged into a container using an official lightweight `python:3.12-slim` base image, runs under a dedicated unprivileged user (`app`), and uses `gunicorn` with multiple workers and threads.

### Build and Push Instructions

1. **Build Container Image Locally**:
   ```bash
   docker build -t flask-mongodb-app:v1 .
   ```

2. **Test Docker Container Locally**:
   ```bash
   docker run --rm -p 5000:5000 \
     -e MONGODB_HOST=host.docker.internal \
     -e MONGODB_PORT=27017 \
     -e MONGODB_DATABASE=flask_db \
     -e MONGO_APP_USERNAME=local_app \
     -e MONGO_APP_PASSWORD=local_password \
     flask-mongodb-app:v1
   ```

3. **Tag and Push to Container Registry (e.g., Docker Hub)**:
   ```bash
   # Log in to registry
   docker login

   # Tag image with your username
   docker tag flask-mongodb-app:v1 <YOUR_DOCKERHUB_USERNAME>/flask-mongodb-app:v1

   # Push image
   docker push <YOUR_DOCKERHUB_USERNAME>/flask-mongodb-app:v1
   ```

> **Note for Minikube**: When running Minikube locally, you can build the image directly inside Minikube's Docker daemon without pushing to an external registry:
> ```bash
> minikube image build -t flask-mongodb-app:v1 .
> ```
> The manifests use `imagePullPolicy: IfNotPresent` to seamlessly use this locally built image.

---

## Kubernetes Deployment Guide (Minikube)

### Step 1: Start Minikube & Enable Metrics Server

Start Minikube with sufficient CPU and memory resources:
```bash
minikube start --driver=docker --cpus=4 --memory=6144
```

Enable the **Metrics Server** addon (required for HPA autoscaling):
```bash
minikube addons enable metrics-server
```
Verify the metrics server is active:
```bash
kubectl get deployment metrics-server -n kube-system
```

### Step 2: Create Namespace & Local Secrets

1. **Create Namespace**:
   ```bash
   kubectl apply -f k8s/00-namespace.yaml
   ```

2. **Create Kubernetes Secret for MongoDB Credentials**:
   To follow security best practices, sensitive passwords are never committed to git in plain text. Create the secret imperatively:
   ```bash
   # PowerShell
   kubectl create secret generic mongodb-secret -n flask-demo `
     --from-literal=MONGO_INITDB_ROOT_USERNAME=admin_root `
     --from-literal=MONGO_INITDB_ROOT_PASSWORD=RootSuperSecurePassword123! `
     --from-literal=MONGO_APP_USERNAME=flask_app `
     --from-literal=MONGO_APP_PASSWORD=AppSuperSecurePassword123!
   ```
   *(Or on Bash, replace backticks with standard trailing backslashes `\`)*.

### Step 3: Deploy MongoDB

Apply the MongoDB manifests in dependency order:
```bash
# 1. ConfigMap containing user creation script
kubectl apply -f k8s/01-mongodb-init-configmap.yaml

# 2. Persistent Volume and Persistent Volume Claim
kubectl apply -f k8s/02-mongodb-pv.yaml
kubectl apply -f k8s/03-mongodb-pvc.yaml

# Verify PVC is Bound:
kubectl get pvc -n flask-demo

# 3. Headless and ClusterIP Services
kubectl apply -f k8s/04-mongodb-headless-service.yaml
kubectl apply -f k8s/05-mongodb-service.yaml

# 4. MongoDB StatefulSet
kubectl apply -f k8s/06-mongodb-statefulset.yaml

# Wait for MongoDB to reach Ready status:
kubectl rollout status statefulset/mongodb -n flask-demo
```

### Step 4: Build Image & Deploy Flask

1. **Build image into Minikube**:
   ```bash
   minikube image build -t flask-mongodb-app:v1 .
   ```

2. **Deploy Flask manifests**:
   ```bash
   # 1. Flask Configuration
   kubectl apply -f k8s/07-flask-configmap.yaml

   # 2. Flask Deployment (2 replicas)
   kubectl apply -f k8s/08-flask-deployment.yaml

   # 3. Flask Service (NodePort)
   kubectl apply -f k8s/09-flask-service.yaml

   # Wait for Flask pods to become Ready:
   kubectl rollout status deployment/flask -n flask-demo
   ```

### Step 5: Configure Horizontal Pod Autoscaler (HPA)

Apply the HPA configuration:
```bash
kubectl apply -f k8s/10-flask-hpa.yaml
```

Verify HPA status:
```bash
kubectl get hpa flask-hpa -n flask-demo
```

---

## Accessing the Application

### Option A: Using `kubectl port-forward` (Recommended for Local Testing)
Forward port 5000 to the Flask Service:
```bash
kubectl port-forward -n flask-demo service/flask-service 5000:80
```
Open a second terminal and access `http://localhost:5000`.

### Option B: Using `NodePort`
Retrieve the service URL directly through Minikube:
```bash
minikube service flask-service -n flask-demo --url
```
Or directly target `<minikube-ip>:30080`.

---

## Technical Explanations

### Kubernetes DNS Resolution for Inter-Pod Communication

Kubernetes manages internal cluster DNS via the **CoreDNS** service deployed in the `kube-system` namespace.

1. **Service Registration**:
   When the `mongodb` service is created in the `flask-demo` namespace with cluster IP `10.96.x.x`, CoreDNS creates an internal A-record:
   ```
   mongodb.flask-demo.svc.cluster.local -> 10.96.x.x
   ```
2. **Search Domains**:
   Every pod launched in the `flask-demo` namespace has a `/etc/resolv.conf` file automatically configured by kubelet with search domains:
   ```
   search flask-demo.svc.cluster.local svc.cluster.local cluster.local
   nameserver 10.96.0.10
   ```
3. **Inter-Pod Discovery**:
   - Because Flask pods reside in the same namespace (`flask-demo`), Flask connects directly to `mongodb:27017`.
   - CoreDNS expands `mongodb` against the search path, resolving it to `mongodb.flask-demo.svc.cluster.local`.
   - The connection hits the stable `ClusterIP` virtual IP, which kube-proxy translates to the active `mongodb-0` pod IP using iptables/IPVS.
   - **Why this is critical**: Pod IPs are ephemeral and change whenever a pod restarts. Connecting through the Service DNS name guarantees continuous communication regardless of pod recreation.

To verify DNS directly from within the cluster:
```bash
kubectl run dns-check -n flask-demo --rm -it --image=busybox:1.36 --restart=Never -- nslookup mongodb
```

---

### Resource Requests and Limits Explained

Resource management in Kubernetes is governed by two parameters per container:
- **Requests (`resources.requests`)**:
  - The minimum guaranteed resources reserved for scheduling.
  - The Kubernetes scheduler (`kube-scheduler`) uses requests to decide which node has enough capacity to host the pod.
  - **HPA Metric Base**: The Horizontal Pod Autoscaler uses the CPU request as the denominator (100% baseline) when calculating utilization.
- **Limits (`resources.limits`)**:
  - The maximum allowable resource consumption.
  - **CPU Limit Enforcement**: Managed by Linux CFS (Completely Fair Scheduler) quotas. If a container exceeds its CPU limit, it is throttled, but not terminated.
  - **Memory Limit Enforcement**: Managed by cgroups. If a container exceeds its memory limit, the Linux kernel terminates the container with an **Out Of Memory (OOMKilled - Exit Code 137)** error.

#### Resource Allocation for This Deployment:
- **Requests**: `0.2 CPU` (`200m`) and `250M` RAM
- **Limits**: `0.5 CPU` (`500m`) and `500M` RAM

#### Autoscaling Target Math:
The assignment specifies an HPA target of **70% CPU utilization**:
$$\text{Target CPU per Pod} = 70\% \times \text{CPU Request} = 0.70 \times 200\text{m} = 140\text{m}$$
When average pod usage across the deployment exceeds `140m` CPU, the HPA triggers horizontal scale-up (up to 5 pods).

---

## Design Choices & Trade-off Analysis

| Architecture Choice | Selected Design | Alternatives Considered | Rationale & Trade-offs |
|---|---|---|---|
| **MongoDB Workload** | `StatefulSet` | `Deployment` | Stateful workloads require stable network identity (`mongodb-0`), ordered startup, and dedicated persistent storage binding. Deployments treat pods as interchangeable and stateless. |
| **MongoDB Services** | `ClusterIP` + Headless Service | `NodePort` / `LoadBalancer` | Databases should never be exposed externally. `ClusterIP` restricts DB traffic strictly inside the cluster. The headless service (`ClusterIP: None`) provides required DNS identity for the StatefulSet. |
| **Flask Workload** | `Deployment` (2 replicas) | `DaemonSet` | Flask is completely stateless. Deployments provide rolling updates, replica management, self-healing, and HPA compatibility. |
| **Flask External Access** | `NodePort` (30080) & `port-forward` | `Ingress` / `LoadBalancer` | In Minikube, `NodePort` exposes the service directly to the host machine without requiring external cloud load balancers or an Ingress Controller setup. |
| **Storage Architecture** | Explicit `PersistentVolume` + `PersistentVolumeClaim` with `hostPath` | Dynamic Provisioning (`standard` StorageClass) | The assignment explicitly requested manifests for both PV and PVC. `hostPath` is appropriate for single-node Minikube demonstration. |
| **Database Auth** | Non-root `flask_app` user (`readWrite`) | Root user credentials in Flask | Least-privilege principle: the application should only have data read/write rights on `flask_db`, not administrative cluster access. |
| **Application Server** | `gunicorn` (2 workers, 4 threads) | Flask dev server (`flask run`) | Flask's built-in server is single-threaded and not designed for production concurrency or HPA load handling. Gunicorn provides multi-worker concurrency. |

---

## Testing Scenarios & Evidence (Cookie Points)

### Test 1: CRUD & API Verification

Execute the automated test script:
```bash
python tests/test_api.py --url http://localhost:5000
```
Or manually using curl:
```bash
# 1. GET /
curl -i http://localhost:5000/
# Expected: HTTP 200, "Welcome to the Flask app! The current time is: ..."

# 2. POST /data
curl -i -X POST http://localhost:5000/data \
  -H "Content-Type: application/json" \
  -d '{"sampleKey":"sampleValue","author":"Aman"}'
# Expected: HTTP 201, {"status": "Data inserted"}

# 3. GET /data
curl -i http://localhost:5000/data
# Expected: HTTP 200, [{"sampleKey":"sampleValue","author":"Aman"}]

# 4. POST Invalid Payload
curl -i -X POST http://localhost:5000/data \
  -H "Content-Type: application/json" \
  -d 'not-json'
# Expected: HTTP 400 Bad Request
```

---

### Test 2: Database Persistence Verification

This test proves that data survives pod deletion and failure:

1. **Insert a test document**:
   ```bash
   curl -X POST http://localhost:5000/data \
     -H "Content-Type: application/json" \
     -d '{"persistenceCheck": "data-must-survive"}'
   ```
2. **Force delete the MongoDB Pod**:
   ```bash
   kubectl delete pod mongodb-0 -n flask-demo
   ```
3. **Watch StatefulSet self-heal**:
   ```bash
   kubectl get pods -n flask-demo -w
   ```
4. **Query data once pod is back Ready**:
   ```bash
   curl http://localhost:5000/data
   ```
   **Result**: The document `{"persistenceCheck": "data-must-survive"}` is retrieved successfully from `/data/db` on the PersistentVolume.

---

### Test 3: High Traffic Simulation & Autoscaling (HPA)

To demonstrate autoscaling up to 5 replicas under load:

1. **Open Terminal 1 (Watch HPA and Replicas)**:
   ```bash
   kubectl get hpa flask-hpa -n flask-demo -w
   ```
2. **Open Terminal 2 (Watch Pod Status)**:
   ```bash
   kubectl get pods -n flask-demo -l app=flask -w
   ```
3. **Open Terminal 3 (Run Load Generator)**:
   ```bash
   python tests/test_api.py --url http://localhost:5000 --stress --duration 60 --concurrency 10
   ```

#### Observed Autoscaling Behavior:
- **Baseline**: 2 replicas, CPU ~1% / 70%.
- **Under Load**: CPU rises to >100% (>200m).
- **Scale-Up**: HPA triggers scale-up: 2 -> 4 -> 5 replicas (capped at `maxReplicas: 5`).
- **Cool-Down**: Once the load stops, after the stabilization window (default 5 minutes), HPA smoothly scales back down to 2 replicas.

---

### Issues Encountered & Solutions

1. **MongoDB Health Probe Failure with Authentication**:
   - *Issue*: Executing unauthenticated `mongosh --eval "db.adminCommand('ping')"` failed with `command adminCommand requires authentication`, causing MongoDB to crash loop.
   - *Solution*: Configured `tcpSocket: {port: 27017}` probes for both readiness and liveness, which safely verify socket availability without leaking credentials or failing authentication checks.
2. **Environment Variable Inheritance in MongoDB Initialization**:
   - *Issue*: Official MongoDB entrypoint executes `.js` files without passing container `process.env` reliably.
   - *Solution*: Used a shell script `/docker-entrypoint-initdb.d/01-create-app-user.sh` mounted via ConfigMap. Bash cleanly interpolates `$MONGO_APP_USERNAME` and `$MONGO_APP_PASSWORD` to create the application user idempotently.
3. **External Cluster Access on Windows**:
   - *Issue*: On Docker Desktop for Windows, Minikube containers run inside a WSL2 virtual network, meaning NodePort IPs are not always directly routable from the host browser.
   - *Solution*: Configured `NodePort` on the service and provided `kubectl port-forward` instructions for universal cross-platform access.

---

## Cleanup

To cleanly remove all deployed resources:
```bash
# Delete all resources in the namespace
kubectl delete namespace flask-demo

# Delete PersistentVolume (reclaimPolicy: Retain)
kubectl delete pv mongodb-pv

# Stop or delete Minikube cluster (optional)
minikube stop
# minikube delete
```
