import os
import subprocess
import sys
import io
from modelscope.hub.api import HubApi
from tqdm import tqdm

class ProgressReader(io.BufferedIOBase):
    def __init__(self, stream, total_size):
        self.stream = stream
        self.pbar = tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc="Uploading")

    def read(self, size=-1):
        chunk = self.stream.read(size)
        if chunk:
            self.pbar.update(len(chunk))
        return chunk

    def readable(self):
        return True

    def close(self):
        self.pbar.close()
        # Do not close the underlying stream here if it's managed elsewhere

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

def upload_local_file(file_path, repo_id, token):
    print(f"Logging in to ModelScope...")
    api = HubApi()
    api.login(token)
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    total_size = os.path.getsize(file_path)
    print(f"File size: {total_size / (1024*1024):.2f} MB")
    print(f"Uploading {file_path} to ModelScope repo: {repo_id}...")

    with open(file_path, 'rb') as f:
        wrapped_stream = ProgressReader(f, total_size)
        try:
            api.upload_file(
                path_or_fileobj=wrapped_stream,
                path_in_repo=os.path.basename(file_path),
                repo_id=repo_id,
                commit_message='Test upload local file',
                commit_description='Uploaded via local test'
            )
            print("\nUpload completed successfully.")
        except Exception as e:
            print(f"\nUpload failed: {e}")
            sys.exit(1)
        finally:
            wrapped_stream.close()

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
    
    if len(sys.argv) < 2:
        print("Usage: python upload_to_modelscope.py <image_tag> OR --local-file <file_path>")
        sys.exit(1)

    if sys.argv[1] == "--local-file":
        if len(sys.argv) < 3:
             print("Usage: python upload_to_modelscope.py --local-file <file_path>")
             sys.exit(1)
        file_path = sys.argv[2]
        if not token or not repo_id:
             print("Environment variables MODELSCOPE_TOKEN and MODELSCOPE_REPO_ID must be set.")
             sys.exit(1)
        upload_local_file(file_path, repo_id, token)
    else:
        image_tag = sys.argv[1]
        if not token or not repo_id:
             print("Environment variables MODELSCOPE_TOKEN and MODELSCOPE_REPO_ID must be set.")
             sys.exit(1)
        upload_docker_image(image_tag, repo_id, token)
