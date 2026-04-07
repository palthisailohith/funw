# MinIO Automation on OpenShift

Automates MinIO user, policy, and bucket management on OpenShift — no Ansible, no ArgoCD needed.  
Edit a YAML file, run a script (or a Kubernetes Job), done.

---

## How It Works

There are **3 pieces**:

| File | In Git? | Purpose |
|------|---------|---------|
| `minio-users.yaml` | ✅ YES | Defines all users, policies, buckets — no secrets |
| `minio-secrets.yaml` | ❌ NEVER | Admin credentials + user passwords |
| `minio-setup.py` | ✅ YES | Reads both files, talks to MinIO, creates everything |

Policies are defined **once** and **reused** across many users. No copy-pasting permissions.

---

## Repo Structure

```
minio-automation/
├── minio-setup.py          # Main automation script
├── minio-users.yaml        # Users, policies, buckets (commit this)
├── minio-secrets.yaml      # Passwords + admin creds (NEVER commit)
├── minio-setup-job.yaml    # OpenShift Job definition
├── Dockerfile              # Bakes dependencies into image
├── requirements.txt        # Python dependencies
├── .gitignore              # Excludes minio-secrets.yaml
└── README.md               # This file
```

---

## Prerequisites

- Python 3.9+
- Access to your MinIO instance
- `pip install -r requirements.txt`

---

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd minio-automation
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your secrets file (never commit this)

```yaml
# minio-secrets.yaml
minio_admin:
  endpoint: your-minio-route.example.com:9000
  access_key: your-admin-key
  secret_key: your-admin-secret
  secure: false   # set true if HTTPS with valid cert

user_passwords:
  alice: "StrongPass123!"
  bob:   "AnotherPass456!"
```

### 4. Configure your users and policies

Edit `minio-users.yaml` — this is the only file you touch day-to-day:

```yaml
policies:
  - name: rw-bucket-a
    bucket: bucket-a
    access: readwrite

  - name: ro-bucket-b
    bucket: bucket-b
    access: readonly

users:
  - username: alice
    policies:
      - rw-bucket-a

  - username: bob
    policies:
      - ro-bucket-b
```

### 5. Run it

```bash
python minio-setup.py
```

---

## Access Levels

| Level | Can List | Can Download | Can Upload | Can Delete |
|-------|----------|--------------|------------|------------|
| `readonly` | ✅ | ✅ | ❌ | ❌ |
| `writeonly` | ✅ | ❌ | ✅ | ✅ |
| `readwrite` | ✅ | ✅ | ✅ | ✅ |
| `listonly` | ✅ | ❌ | ❌ | ❌ |

---

## Day-to-Day Workflows

### Adding a new user

1. Add to `minio-users.yaml`:
```yaml
  - username: newguy
    policies:
      - rw-bucket-a    # reference an existing policy
```

2. Add their password to `minio-secrets.yaml`:
```yaml
  newguy: "TheirPassword!"
```

3. Run the script:
```bash
python minio-setup.py
```

4. Commit only the YAML — never the secrets:
```bash
git add minio-users.yaml
git commit -m "add newguy"
git push
```

### Adding a new bucket + policy

Add to `policies:` in `minio-users.yaml` first, then reference in a user:

```yaml
policies:
  - name: rw-new-bucket
    bucket: new-bucket
    access: readwrite

users:
  - username: alice
    policies:
      - rw-new-bucket
```

The bucket is **automatically created** if it doesn't exist.

### Resetting a password

Update the password in `minio-secrets.yaml` and re-run. The script overwrites it.

### Changing user permissions

Update their `policies:` list in `minio-users.yaml` and re-run.

---

## Running on OpenShift

### Step 1 — Store secrets in OpenShift (once)

```bash
oc create secret generic minio-setup-secrets \
  --from-file=minio-secrets.yaml=./minio-secrets.yaml

oc create configmap minio-users-config \
  --from-file=minio-users.yaml=./minio-users.yaml

oc create configmap minio-setup-script \
  --from-file=minio-setup.py=./minio-setup.py
```

### Step 2 — Build and push the Docker image

The cluster has no internet access, so we bake dependencies into the image:

```bash
# Build using your internal Artifactory registry
docker build -t sidx-docker-virtual.artifactory.six-group.net/minio-setup:latest .

# Push
docker push sidx-docker-virtual.artifactory.six-group.net/minio-setup:latest
```

### Step 3 — Run the Job

```bash
oc apply -f minio-setup-job.yaml
oc logs job/minio-setup -f
```

### Step 4 — When you update users

```bash
# Update the ConfigMap with new users file
oc create configmap minio-users-config \
  --from-file=minio-users.yaml=./minio-users.yaml \
  --dry-run=client -o yaml | oc apply -f -

# Re-run the job
oc delete job minio-setup
oc apply -f minio-setup-job.yaml
oc logs job/minio-setup -f
```

---

## Security Rules

- ❌ **Never** commit `minio-secrets.yaml` to Git
- ❌ **Never** hardcode passwords in `minio-users.yaml`
- ✅ `minio-secrets.yaml` lives only on your machine or in an OpenShift Secret
- ✅ The script is safe to re-run — it is fully idempotent (won't duplicate anything)
- ✅ If a user/policy/bucket already exists, it just updates it

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `No password found for <user>` | Username in YAML missing from secrets file | Add password to `minio-secrets.yaml` |
| `XMinioAdminNoSuchPolicy` | Policy name in user doesn't match policy definition | Check spelling in `minio-users.yaml` — case sensitive |
| `SSL: WRONG_VERSION_NUMBER` | Connecting with HTTPS to an HTTP endpoint | Set `secure: false` in `minio-secrets.yaml` |
| `Connection timed out` | Cluster can't reach Artifactory for pip | Build Docker image locally and push (see OpenShift section) |
| `ModuleNotFoundError: yaml` | Packages not installed | Run `pip install -r requirements.txt` |

---

## How Parallelism Works

When you have 10 or 20 users, the script creates them **all at the same time** using Python's `ThreadPoolExecutor`. A 5 second wait after policy creation ensures MinIO has registered them before users try to attach.

```
Policies created → wait 5s → all users created in parallel
```

---

## Dependencies

```
minio==7.2.9
pyyaml==6.0.1
```
