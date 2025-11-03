# backend/api/s3_upload_handler.py
# Example backend Python module using AWS S3 APIs.

import requests
import os

AWS_ACCESS_KEY_ID = "AKIAFAKEKEY1234567890"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYFAKESECRET1234"

def upload_to_s3(bucket, key, file_path, region="eu-west-1"):
    """
    Uploads a file to S3 using PUT request.
    """
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    headers = {
        "Content-Type": "application/octet-stream",
        "x-amz-acl": "private",
        "x-amz-meta-origin": "backend",
    }

    # Read file content
    with open(file_path, "rb") as f:
        data = f.read()

    # Make S3 PUT request
    response = requests.put(
        url,
        headers=headers,
        data=data,
        auth=(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY),
    )

    if response.status_code == 200:
        print(f"Uploaded {file_path} successfully to {bucket}/{key}")
    else:
        print(f"Upload failed: {response.status_code}, {response.text}")


if __name__ == "__main__":
    upload_to_s3("test-bucket", "images/test1.jpg", "/tmp/test1.jpg")
