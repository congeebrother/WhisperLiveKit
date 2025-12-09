import os
import subprocess
import sys
from modelscope.hub.api import HubApi

def upload_docker_image(image_tag, repo_id, token):
    print(f"Logging in to ModelScope...")
    api = HubApi()
    api.login(token)

    print(f"Starting docker save for {image_tag}...")
    # Start docker save process
    # We pipe stdout so we can read from it
    process = subprocess.Popen(
        ['docker', 'save', image_tag],
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        bufsize=1024*1024*10  # 10MB buffer
    )

    print(f"Uploading stream to ModelScope repo: {repo_id} as whisperlivekit.tar...")
    
    try:
        # upload_file accepts a file-like object
        api.upload_file(
            path_or_fileobj=process.stdout,
            path_in_repo='whisperlivekit.tar',
            repo_id=repo_id,
            commit_message='Update Docker image (streamed upload)',
            commit_description='Uploaded via GitHub Actions'
        )
        print("Upload completed successfully.")
    except Exception as e:
        print(f"Upload failed: {e}")
        process.kill()
        sys.exit(1)
    
    # Ensure docker save finished correctly
    process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        print(f"docker save failed with return code {return_code}")
        sys.exit(return_code)

if __name__ == "__main__":
    token = os.environ.get('MODELSCOPE_TOKEN')
    repo_id = os.environ.get('MODELSCOPE_REPO_ID')
    image_tag = sys.argv[1] if len(sys.argv) > 1 else None

    if not token or not repo_id or not image_tag:
        print("Usage: python upload_to_modelscope.py <image_tag>")
        print("Environment variables MODELSCOPE_TOKEN and MODELSCOPE_REPO_ID must be set.")
        sys.exit(1)

    upload_docker_image(image_tag, repo_id, token)
