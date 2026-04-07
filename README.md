# minio-automation

Manages MinIO users, policies, and buckets on OpenShift via a Python script and a Kubernetes Job.

## Files

| File | Commit? | Description |
|------|---------|-------------|
| `minio-setup.py` | ✅ | The script |
| `minio-users.yaml` | ✅ | Users, policies, buckets |
| `minio-secrets.yaml` | ❌ | Passwords and admin creds — never commit |
| `minio-setup-job.yaml` | ✅ | OpenShift Job |
| `Dockerfile` | ✅ | Bakes pip dependencies into image |
| `requirements.txt` | ✅ | `minio==7.2.9`, `pyyaml==6.0.1` |

---

## Local Usage

```bash
pip install -r requirements.txt
python minio-setup.py
```

---

## Configuration

### minio-users.yaml

Policies are defined once and referenced by multiple users.

```yaml
policies:
  - name: rw-bucket-a
    bucket: bucket-a
    access: readwrite        # readonly | writeonly | readwrite | listonly

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
      - rw-bucket-a
```

Buckets are created automatically if they don't exist.

### minio-secrets.yaml

```yaml
minio_admin:
  endpoint: your-minio-route.example.com:9000
  access_key: your-admin-key
  secret_key: your-admin-secret
  secure: false

user_passwords:
  alice: "password"
  bob: "password"
```

Every username in `minio-users.yaml` needs a matching entry here.

---

## Adding a New User

1. Add to `minio-users.yaml` under `users:`
2. Add their password to `minio-secrets.yaml`
3. Run the script
4. Commit only `minio-users.yaml`

---

## OpenShift

### First time setup

```bash
# Store secrets in the cluster
oc create secret generic minio-setup-secrets \
  --from-file=minio-secrets.yaml=./minio-secrets.yaml

oc create configmap minio-users-config \
  --from-file=minio-users.yaml=./minio-users.yaml

oc create configmap minio-setup-script \
  --from-file=minio-setup.py=./minio-setup.py
```

### Build and push the image

The cluster has no internet access so dependencies are baked into the image.

```bash
docker build -t sidx-docker-virtual.artifactory.six-group.net/minio-setup:latest .
docker push sidx-docker-virtual.artifactory.six-group.net/minio-setup:latest
```

### Run

```bash
oc apply -f minio-setup-job.yaml
oc logs job/minio-setup -f
```

### Update users and re-run

```bash
oc create configmap minio-users-config \
  --from-file=minio-users.yaml=./minio-users.yaml \
  --dry-run=client -o yaml | oc apply -f -

oc delete job minio-setup
oc apply -f minio-setup-job.yaml
```

---

## Notes

- The script is idempotent — safe to re-run anytime
- Users are created in parallel (up to 10 at a time)
- `minio-secrets.yaml` is in `.gitignore` — keep it that way
