# coding: utf-8
##########################################################################
# aws2oci_api_adapt.py
#
# @author:  Jose Villar
#
# Supports Python 3
#
# DISCLAIMER – This is not an official Oracle application.
# It is not supported by Oracle Support.
# It should NOT be used for utilization calculation purposes.
##########################################################################
# Info:
#   Bulk change AWS S3 API calls to OCI Object Storage S3-Compatible API
#   Supports Python, JavaScript, Shell, HTML, JSON, YAML, and Terraform files.
#
#   - Replaces AWS credentials and identifiers with OCI equivalents from config.
#   - Converts AWS S3 URLs to OCI-compatible path-style URLs.
#   - Adjusts syntax for each file type to ensure compatibility and correctness.
#   # The result for each file will be saved with a '_OCI' suffix.
# Each output is also validated for OCI compatibility by file type.
#
# Usage:
# python3 aws2oci_api_adapt.py -l source_aws_files.txt
#
# Replace the hardcoded credential constants with your actual OCI values
##########################################################################

import os
import re
import sys
import json
import argparse
from pathlib import Path

# Hardcoded config values 
#
AWS_ACCESS_KEY_PATTERN = "AWS_ACCESS_KEY_ID"
AWS_SECRET_KEY_PATTERN = "AWS_SECRET_ACCESS_KEY"
OCI_ACCESS_KEY_ID = "389ad6b353e485f812fa97aaaaaaaaaaaaaaaaaa"
OCI_SECRET_ACCESS_KEY = "g17SE1pgSIJcdfB6Xy2srjveziaaaaaaaaaaaaaaaaa="
NAMESPACE = "fr9qm01aaaa"
OCI_REGION = "eu-frankfurt-1"
# Required OCI values for Terraform compatibility apart from the SOME of the previous
OCI_TENANCY_OCID = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
OCI_USER_OCID = "ocid1.user.oc1..aaaaaaaaexampleuser"
OCI_FINGERPRINT = "20:3b:97:13:example:fingerprint"
OCI_PRIVATE_KEY_PATH = "~/.oci/oci_api_key.pem"
OCI_COMPARTMENT_OCID = "ocid1.compartment.oc1..aaaaaaaacomppart"

def detect_file_type(filepath):
    if filepath.endswith(".py"):
        return "python"
    elif filepath.endswith(".js"):
        return "javascript"
    elif filepath.endswith(".sh"):
        return "shell"
    elif filepath.endswith(".html"):
        return "html"
    elif filepath.endswith(".json"):
        return "json"
    elif filepath.endswith(".yaml") or filepath.endswith(".yml"):
        return "yaml"
    elif filepath.endswith(".tf"):
        return "terraform"
    else:
        return "unknown"

def replace_credentials(text, filetype):
    # Remove AWS-only headers before replacing credentials where appropriate
    if filetype in ["python", "javascript", "shell", "json", "yaml", "terraform", "html"]:
        if filetype == "html":
            text = re.sub(r'<input[^>]*name=["\']acl["\'][^>]*>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^.*x-amz-(acl|grant|object-lock-[^\s]*)[^\n]*\n?', '', text, flags=re.MULTILINE)
    # Replace variable names and values for Python
    if filetype == "python":
        text = re.sub(rf'^{AWS_ACCESS_KEY_PATTERN}\s*=\s*"[^"]*"', f'{"OCI_ACCESS_KEY_ID"} = "{OCI_ACCESS_KEY_ID}"', text, flags=re.MULTILINE)
        text = re.sub(rf'^{AWS_SECRET_KEY_PATTERN}\s*=\s*"[^"]*"', f'{"OCI_SECRET_ACCESS_KEY"} = "{OCI_SECRET_ACCESS_KEY}"', text, flags=re.MULTILINE)
        text = re.sub(rf'auth=\({AWS_ACCESS_KEY_PATTERN},\s*{AWS_SECRET_KEY_PATTERN}\)', f'auth=(OCI_ACCESS_KEY_ID, OCI_SECRET_ACCESS_KEY)', text)

    # JavaScript constant replacement
    elif filetype == "javascript":
        text = re.sub(rf'const\s+{AWS_ACCESS_KEY_PATTERN}\s*=\s*"[^"]*"', f'const OCI_ACCESS_KEY_ID = "{OCI_ACCESS_KEY_ID}"', text)
        text = re.sub(rf'const\s+{AWS_SECRET_KEY_PATTERN}\s*=\s*"[^"]*"', f'const OCI_SECRET_ACCESS_KEY = "{OCI_SECRET_ACCESS_KEY}"', text)

    # Shell variable export
    elif filetype == "shell":
        text = re.sub(rf'{AWS_ACCESS_KEY_PATTERN}\s*=\s*"[^"]*"', f'OCI_ACCESS_KEY_ID="{OCI_ACCESS_KEY_ID}"', text)
        text = re.sub(rf'{AWS_SECRET_KEY_PATTERN}\s*=\s*"[^"]*"', f'OCI_SECRET_ACCESS_KEY="{OCI_SECRET_ACCESS_KEY}"', text)

    # HTML input tag
    elif filetype == "html":
    # Remove entire line with ACL input and leading/trailing whitespace
        text = re.sub(r'<input[^>]*name=["\']acl["\'][^>]*>', '', text, flags=re.IGNORECASE)
        text = strip_extra_blank_lines(text)
       # Replace AWSAccessKeyId field
        text = re.sub(
            r'name=["\']AWSAccessKeyId["\']\s+value=["\'][^"\']*["\']',
            f'name="OCIAccessKeyId" value="{OCI_ACCESS_KEY_ID}"',
            text
        )

    # JSON keys
    elif filetype == "json":
        text = re.sub(r'("aws_access_key"\s*:\s*")[^"]+"', f'"oci_access_key": "OCI_ACCESS_KEY_ID"', text)
        text = re.sub(r'("aws_secret_key"\s*:\s*")[^"]+"', f'"oci_secret_key": "OCI_SECRET_ACCESS_KEY"', text)
        text = re.sub(r',?\s*"region"\s*:\s*"[^"]*"', '', text)

    # YAML
    elif filetype == "yaml":
        text = re.sub(r'(aws_credentials:\s*\n\s*)access_key_id:\s*[^\n]+', rf'\1access_key_id: {OCI_ACCESS_KEY_ID}', text)
        text = re.sub(r'(aws_credentials:\s*\n\s*access_key_id:.*\n\s*)secret_access_key:\s*[^\n]+', rf'\1secret_access_key: {OCI_SECRET_ACCESS_KEY}', text)

    # Terraform
        # Terraform
    elif filetype == "terraform":
        text = re.sub(
        r'provider\s+"aws"\s*\{[^}]*\}',
        f'''provider "oci" {{
        tenancy_ocid     = "{OCI_TENANCY_OCID}"
        user_ocid        = "{OCI_USER_OCID}"
        fingerprint      = "{OCI_FINGERPRINT}"
        private_key_path = "{OCI_PRIVATE_KEY_PATH}"
        region           = "{OCI_REGION}"
        }}''',
        text,
        flags=re.DOTALL
        )
        text = re.sub(
        r'resource\s+"aws_s3_bucket"\s+"([^"]+)"\s*\{[^}]*\}',
        rf'''resource "oci_objectstorage_bucket" "\1" {{
        compartment_id = "{OCI_COMPARTMENT_OCID}"
        name           = "my-oci-bucket"
        namespace      = "{NAMESPACE}"
        storage_tier   = "Standard"
        public_access_type = "NoPublicAccess"
        }}''',
        text,
        flags=re.DOTALL
        )

    return text
# strip extra white lines
def strip_extra_blank_lines(text):
    return re.sub(r'^\s*\n', '', text, flags=re.MULTILINE)

def remove_aws_only_headers(text):
    return re.sub(r'^.*x-amz-(acl|grant|object-lock-[^\s]*)[^\n]*\n?', '', text, flags=re.MULTILINE)

def convert_s3_urls(text):
    pattern = re.compile(r'https://([^.]+)\.s3\.([^.]+)\.amazonaws\.com/([^"\s]*)')
    def url_replacer(match):
        bucket = match.group(1)
        key = match.group(3)
        return f"https://{NAMESPACE}.compat.objectstorage.{OCI_REGION}.oraclecloud.com/{bucket}/{key}"
    text = pattern.sub(url_replacer, text)

    text = re.sub(
        r'https://s3[.-][a-z0-9-]+\.amazonaws\.com/([^\s"\'<>]+)',
        rf'https://{NAMESPACE}.compat.objectstorage.{OCI_REGION}.oraclecloud.com/\1',
        text
    )

    text = re.sub(r'hostname:\s*`?\$?\{bucket\}\.s3\.\$?\{region\}\.amazonaws\.com`?',
                  f'hostname: "{NAMESPACE}.compat.objectstorage.{OCI_REGION}.oraclecloud.com"', text)
    text = re.sub(r'path:\s*`?\$?\{key\}`?', 'path: `/${bucket}/${key}`', text)

    text = re.sub(r'(region\s*=\s*["\'])[a-z0-9-]+(["\'])', rf'\1{OCI_REGION}\2', text)
    text = re.sub(r'(REGION=)[a-z0-9-]+', rf'\1{OCI_REGION}', text)

    return text
# process javascript files
def process_js(content):
    """
    Detects AWS SDK or AWS-style manual upload patterns in a JS file,
    and replaces the whole content with an OCI Object Storage compatible
    Node.js script that uses the OCI Node SDK and hardcoded credentials.
    """
    aws_indicators = [
        "require(\"aws-sdk\")", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        ".s3.", "s3.amazonaws.com", "new AWS.S3", "axios(", "fetch("
    ]

    if any(indicator in content for indicator in aws_indicators):
        return """
const fs = require("fs");
const path = require("path");
const common = require("oci-common");
const objectStorage = require("oci-objectstorage");

// ---- OCI Credentials (Hardcoded, replace with environment usage in production) ----
const TENANCY_OCID = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy";
const USER_OCID = "ocid1.user.oc1..aaaaaaaaexampleuser";
const FINGERPRINT = "20:3b:97:13:example:fingerprint";
const PRIVATE_KEY_PATH = "/Users/yourname/.oci/oci_api_key.pem";
const REGION = "eu-frankfurt-1";
const NAMESPACE = "fr9qm01aaaa";
const BUCKET_NAME = "my-oci-bucket";

// ---- File to Upload ----
const FILE_PATH = process.argv[2] || "my_upload_file.txt";
const OBJECT_NAME = "uploads/" + path.basename(FILE_PATH);

// ---- Read Private Key ----
const privateKey = fs.readFileSync(PRIVATE_KEY_PATH, "utf8");

const provider = new common.SimpleAuthenticationDetailsProvider(
  TENANCY_OCID,
  USER_OCID,
  FINGERPRINT,
  privateKey,
  null,
  REGION
);

const client = new objectStorage.ObjectStorageClient({
  authenticationDetailsProvider: provider
});
client.region = REGION;

async function uploadFile() {
  console.log("Starting upload...");
  console.log("File:", FILE_PATH);
  console.log("Bucket:", BUCKET_NAME);
  console.log("Region:", REGION);

  try {
    const putObjectRequest = {
      namespaceName: NAMESPACE,
      bucketName: BUCKET_NAME,
      objectName: OBJECT_NAME,
      putObjectBody: fs.createReadStream(FILE_PATH)
    };

    const response = await client.putObject(putObjectRequest);
    console.log("Upload successful.");
    console.log("ETag:", response.etag);
  } catch (err) {
    console.error("Upload failed:", err.message);
  }
}

uploadFile();
"""
    return content.strip()

# process the shell .sh files
def process_shell_script(content):
    """
    Converts an AWS S3 upload shell script to an OCI-compatible version with signed request.
    Preserves KEY and FILE_PATH from the original, injects valid OCI Signature V1 logic.
    """

    # Detect and preserve shebang
    lines = content.strip().splitlines()
    if lines and lines[0].startswith("#!"):
        shebang = lines[0]
        lines = lines[1:]
    else:
        shebang = "#!/bin/bash"

    # Preserve FILE_PATH and KEY assignments
    preserved = []
    for line in lines:
        if re.match(r'^FILE_PATH="[^"]+"', line) or re.match(r'^KEY="[^"]+"', line):
            preserved.append(line.strip())

    # Remove AWS-specific logic and declarations
    text = "\n".join(lines)
    text = re.sub(r'(?m)^.*(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|REGION|SERVICE|BUCKET)=.*\n?', '', text)
    text = re.sub(r'(?m)^.*(kSecret|k(Date|Region|Service|Signing))=.*\n?', '', text)
    text = re.sub(r'(?m)^.*(AUTH_HEADER|STRING_TO_SIGN|SIGNED_HEADERS|ALGORITHM|CREDENTIAL_SCOPE|CANONICAL_|HASHED_|PAYLOAD_HASH|REQUEST_DATE|DATE_STAMP)=.*\n?', '', text)
    text = re.sub(r'(?m)^.*openssl.*(dgst|sha256|sha1).*\n?', '', text)
    text = re.sub(r'(?m)^.*aws s3 [^\n]*\n?', '', text)
    text = re.sub(
        r'curl\s+-X\s+PUT.*?Authorization:[^"\n]*"\s*\\?\n(?:[ \t]*-H\s+".*?"\s*\\?\n?)*',
        '',
        text,
        flags=re.MULTILINE | re.DOTALL
    )

    # Begin new OCI-compatible script
    final_script = shebang + "\n\n"

    final_script += f"""# OCI Signature V1 Configuration
TENANCY_OCID="{OCI_TENANCY_OCID}"
USER_OCID="{OCI_USER_OCID}"
FINGERPRINT="{OCI_FINGERPRINT}"
PRIVATE_KEY_PATH="$HOME/.oci/oci_api_key.pem"

# Target Storage Info
NAMESPACE="{NAMESPACE}"
REGION="{OCI_REGION}"
BUCKET="my-oci-bucket"
"""

    if preserved:
        final_script += "\n" + "\n".join(preserved) + "\n"

    final_script += """
# Compute signed date
DATE=$(LC_ALL=C date -u "+%a, %d %b %Y %H:%M:%S GMT")
HOST="$NAMESPACE.compat.objectstorage.$REGION.oraclecloud.com"
TARGET="/$BUCKET/$KEY"

# Build signing string safely
SIGNING_STRING=$(printf "date: %s\\n(host): %s\\n(request-target): put %s" "$DATE" "$HOST" "$TARGET")

# Generate signature using private key
SIGNATURE=$(printf "$SIGNING_STRING" | \\
  openssl dgst -sha256 -sign "$PRIVATE_KEY_PATH" | \\
  openssl base64 -A)

# Assemble Authorization header
AUTH_HEADER='Signature version="1",keyId="'$TENANCY_OCID'/'$USER_OCID'/'$FINGERPRINT'",algorithm="rsa-sha256",headers="date (host) request-target",signature="'$SIGNATURE'"'

# Perform the upload
curl -i -X PUT -T "$FILE_PATH" \\
  -H "host: $HOST" \\
  -H "date: $DATE" \\
  -H "authorization: $AUTH_HEADER" \\
  "https://$HOST/$BUCKET/$KEY"
"""

    # Final cleanup: remove trailing space, excessive newlines
    return re.sub(r'\n{3,}', '\n\n', final_script.strip())

# transfor the content considering filetype
def transform_content(content, filetype):
    if filetype == "javascript":
        content = process_js(content)

    content = replace_credentials(content, filetype)
    content = convert_s3_urls(content)
    content = re.sub(r'^.*x-amz-(acl|grant|object-lock-[^\s]*)[^\n]*\n?', '', content, flags=re.MULTILINE)

    if filetype == "shell":
        content = process_shell_script(content)

    return content
def validate_filetype(filetype, content):
    def validate_python(content):
        return all([
            "OCI_ACCESS_KEY_ID" in content,
            "OCI_SECRET_ACCESS_KEY" in content,
            ".compat.objectstorage." in content,
            "requests" in content or "oci" in content,
            "AWS_ACCESS_KEY_ID" not in content,
            ".s3.amazonaws.com" not in content
        ])

    def validate_javascript(content):
        return all([
            'require("oci-objectstorage")' in content,
            "SimpleAuthenticationDetailsProvider" in content,
            "putObject" in content,
            "TENANCY_OCID" in content,
            "AWS_ACCESS_KEY_ID" not in content,
            ".s3." not in content
        ])

    def validate_shell(content):
        return all([
            "TENANCY_OCID=" in content,
            "curl -i -X PUT" in content,
            'Signature version="1"' in content,
            "AWS_ACCESS_KEY_ID" not in content,
            "CANONICAL_REQUEST" not in content,
            "SIGNED_HEADERS" not in content
        ])

    def validate_html(content):
        return all([
            ".compat.objectstorage." in content,
            "OCIAccessKeyId" in content,
            "public-read" not in content
        ])

    def validate_json(content):
        return all([
            "oci_access_key" in content,
            "oci_secret_key" in content,
            "endpoint" in content and ".compat.objectstorage." in content,
            "us-west-2" not in content
        ])

    def validate_yaml(content):
        return all([
            "oci_access_key" in content or "OCI_ACCESS_KEY_ID" in content,
            "oci_secret_key" in content or "OCI_SECRET_ACCESS_KEY" in content,
            ".compat.objectstorage." in content,
            "aws_credentials" not in content or "AWS_ACCESS_KEY_ID" not in content
        ])

    def validate_terraform(content):
        return all([
            'provider "oci"' in content,
            "oci_objectstorage_bucket" in content,
            "namespace" in content,
            "aws_s3_bucket" not in content
        ])

    validators = {
        "python": validate_python,
        "javascript": validate_javascript,
        "shell": validate_shell,
        "html": validate_html,
        "json": validate_json,
        "yaml": validate_yaml,
        "terraform": validate_terraform
    }

    return validators.get(filetype, lambda x: False)(content)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--list", required=True, help="Path to source_aws_files.txt")
    args = parser.parse_args()

    with open(args.list, "r", encoding="utf-8") as f:
        files = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    for src_file in files:
        if not os.path.exists(src_file):
            print(f"[WARN] File not found: {src_file}")
            continue

        filetype = detect_file_type(src_file)

        with open(src_file, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = transform_content(content, filetype)

        if validate_filetype(filetype, new_content):
            print(f"[VALID] {src_file} passed OCI validation as {filetype}.")
        else:
            print(f"[WARNING] {src_file} may not be fully OCI compatible.")

        dest_path = Path(src_file)
        dest_file = dest_path.with_name(dest_path.stem + "_OCI" + dest_path.suffix)

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"[OK] Converted: {src_file} → {dest_file}")

if __name__ == "__main__":
    main()
