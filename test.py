import tempfile
import os

def ensure_policy(admin, policy):
    name = policy['name']
    try:
        policy_json = build_policy_doc(policy)
        
        # Write to temp file — policy_add needs a file path, not a string
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(policy_json)
            tmp_path = f.name
        
        admin.policy_add(name, tmp_path)
        print(f'  [+] Policy ready: {name}')
        
    except Exception as e:
        print(f'  [!] Policy {name}: {e}')
    finally:
        # Always clean up the temp file
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
