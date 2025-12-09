import os
import subprocess
import sys
from modelscope.hub.api import HubApi
from tqdm import tqdm

class ProgressReader:
    def __init__(self, stream, total_size):
        self.stream = stream
        self.pbar = tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc="Uploading")

    def read(self, size=-1):
        chunk = self.stream.read(size)
        if chunk:
            self.pbar.update(len(chunk))
        return chunk

    def close(self):
        self.pbar.close()

def get_image_size(image_tag):
    try:
        # docker inspect returns size in bytes
        result = subprocess.run(
            ['docker', 'inspect', '-f', '{{.Size}}', image_tag],
            capture_output=True, text=True, check=True
        )
        return int(result.stdout.strip())
    except Exception as e:
        print(f"Failed to get image size: {e}")
        return None

def upload_docker_image(image_tag, repo_id, token):
    print(f"Logging in to ModelScope...")
    api = HubApi()
    api.login(token)

    total_size = get_image_size(image_tag)
    if total_size:
        print(f"Image size: {total_size / (1024*1024*1024):.2f} GB")
    else:
        print("Could not determine image size, progress bar will be indefinite.")

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
    
    # Wrap the stream with progress reader
    wrapped_stream = ProgressReader(process.stdout, total_size)

    try:
        # upload_file accepts a file-like object
        # We disable the internal tqdm to use our own wrapper which tracks the stream
        api.upload_file(
            path_or_fileobj=wrapped_stream,
            path_in_repo='whisperlivekit.tar',
            repo_id=repo_id,
            commit_message='Update Docker image (streamed upload)',
            commit_description='Uploaded via GitHub Actions'
        )
        print("\nUpload completed successfully.")
    except Exception as e:
        print(f"\nUpload failed: {e}")
        process.kill()
        sys.exit(1)
    finally:
        wrapped_stream.close()
    
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
