import yaml
import json
import sys
from minio import Minio
from minio.minioadmin import MinioAdmin
from concurrent.futures import ThreadPoolExecutor, as_completed

# --------------------------------------------------
# STEP 1: Load both config files and merge them
# --------------------------------------------------
def load_config(users_file, secrets_file):
    with open(users_file) as f:
        cfg = yaml.safe_load(f)

    with open(secrets_file) as f:
        secrets = yaml.safe_load(f)

    passwords = secrets['user_passwords']

    for user in cfg['users']:
        username = user['username']
        if username not in passwords:
            print(f'[!!] No password for {username} - SKIPPING')
            user['skip'] = True
        else:
            user['password'] = passwords[username]

    cfg['admin'] = secrets['minio_admin']
    return cfg


# --------------------------------------------------
# STEP 2: Build the S3 policy JSON
# --------------------------------------------------
ACCESS_LEVELS = {
    'readonly': ['s3:GetObject', 's3:ListBucket'],
    'writeonly': ['s3:PutObject', 's3:DeleteObject', 's3:ListBucket'],
    'readwrite': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:ListBucket'],
    'listonly': ['s3:ListBucket']
}


def build_policy_doc(policy):
    actions = ACCESS_LEVELS.get(policy['access'], ACCESS_LEVELS['readonly'])
    buckets = policy.get('buckets') or [policy.get('bucket')]

    statements = []
    for bucket in buckets:
        statements.append({
            'Effect': 'Allow',
            'Action': actions,
            'Resource': [
                f'arn:aws:s3:::{bucket}',
                f'arn:aws:s3:::{bucket}/*'
            ]
        })

    return json.dumps({
        'Version': '2012-10-17',
        'Statement': statements
    })


# --------------------------------------------------
# STEP 3: Ensure bucket exists
# --------------------------------------------------
def ensure_bucket(client, bucket_name):
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f'[+] Created bucket: {bucket_name}')
        else:
            print(f'[=] Bucket already exists: {bucket_name}')
    except Exception as e:
        print(f'[!] Bucket error {bucket_name}: {e}')


# --------------------------------------------------
# STEP 4: Create or update policy
# --------------------------------------------------
def ensure_policy(admin, policy):
    name = policy['name']
    try:
        admin.add_policy(name, build_policy_doc(policy))
        print(f'[+] Policy ready: {name}')
    except Exception as e:
        print(f'[!] Policy {name}: {e}')


# --------------------------------------------------
# STEP 5: Create user and attach policies
# --------------------------------------------------
def ensure_user(admin, user):
    if user.get('skip'):
        return

    username = user['username']

    try:
        admin.add_user(username, user['password'])
        print(f'[+] User ready: {username}')
    except Exception as e:
        print(f'[!] User {username}: {e}')
        return

    for policy in user.get('policies', []):
        try:
            admin.attach_policy(policy, user=username)
            print(f'    -> {username} attached to policy: {policy}')
        except Exception as e:
            print(f'    [!] Could not attach {policy} to {username}: {e}')


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    users_file = sys.argv[1] if len(sys.argv) > 1 else 'minio-users.yaml'
    secrets_file = sys.argv[2] if len(sys.argv) > 2 else 'minio-secrets.yaml'

    print('Loading config...')
    cfg = load_config(users_file, secrets_file)
    admin_cfg = cfg['admin']

    admin = MinioAdmin(
        admin_cfg['endpoint'],
        access_key=admin_cfg['access_key'],
        secret_key=admin_cfg['secret_key'],
        secure=admin_cfg.get('secure', True)
    )

    client = Minio(
        admin_cfg['endpoint'],
        access_key=admin_cfg['access_key'],
        secret_key=admin_cfg['secret_key'],
        secure=admin_cfg.get('secure', True)
    )

    # 1. Buckets
    print('\n=== Ensuring Buckets ===')
    all_buckets = set()

    for pol in cfg.get('policies', []):
        for b in pol.get('buckets') or [pol.get('bucket')]:
            if b:
                all_buckets.add(b)

    for bucket in all_buckets:
        ensure_bucket(client, bucket)

    # 2. Policies
    print('\n=== Ensuring Policies ===')
    for policy in cfg.get('policies', []):
        ensure_policy(admin, policy)

    # 3. Users (parallel)
    print('\n=== Ensuring Users (parallel) ===')
    users = cfg.get('users', [])

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(ensure_user, admin, u): u['username']
            for u in users
        }

        for future in as_completed(futures):
            username = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f'[!!] Unexpected error for {username}: {e}')

    print('\nAll done!')


if __name__ == '__main__':
    main()
