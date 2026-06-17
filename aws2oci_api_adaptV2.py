#!/usr/bin/env python3
# coding: utf-8
##########################################################################
# aws2oci_api_adapt.py
#
# @author: Jose Villar
# Updated: 2026-06-17
#
# Supports Python 3.8+
#
# DISCLAIMER: This is not an official Oracle application.
# It is not supported by Oracle Support.
# It should NOT be used for utilization calculation purposes.
##########################################################################
# Info:
#   Bulk-converts common AWS S3 API usage to OCI Object Storage's
#   Amazon S3 Compatibility API.
#
#   Current OCI S3-compatible behavior covered by this version:
#   - Uses Customer Secret Key access key / secret key values for SigV4.
#   - Defaults to the current OCI S3 endpoint domain:
#       https://<namespace>.compat.objectstorage.<region>.oci.customer-oci.com
#   - Can emit virtual-hosted style endpoints:
#       https://<bucket>.vhcompat.objectstorage.<region>.oci.customer-oci.com/<object>
#   - Keeps path-style access as the default because it works with existing
#     buckets and many legacy S3 clients.
#   - Removes common AWS-only ACL/grant/object-lock headers.
#
# Usage:
#   python3 aws2oci_api_adapt.py -l source_aws_files.txt \
#     --namespace mynamespace --region eu-frankfurt-1 --bucket my-bucket
#
# Credentials:
#   By default the generated code reads credentials from:
#     OCI_S3_ACCESS_KEY_ID
#     OCI_S3_SECRET_ACCESS_KEY
#   Pass --credential-mode literal with --access-key-id and --secret-access-key
#   only if you intentionally want credentials written into generated files.
##########################################################################

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import urlsplit, urlunsplit


AWS_ACCESS_KEY_NAMES = (
    "AWS_ACCESS_KEY_ID",
    "AWS_ACCESS_KEY",
    "aws_access_key_id",
    "aws_access_key",
)
AWS_SECRET_KEY_NAMES = (
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SECRET_KEY",
    "aws_secret_access_key",
    "aws_secret_key",
)

S3_ONLY_HEADER_LINE_RE = re.compile(
    r"^.*x-amz-(?:acl|grant-[^:\s]+|object-lock-[^:\s]+).*\n?",
    flags=re.IGNORECASE | re.MULTILINE,
)

# Common SDK argument/property forms for object ACLs. OCI authorization should
# be handled with IAM policies, not object ACLs.
ACL_ASSIGNMENT_LINE_RE = re.compile(
    r"^\s*(?:ACL|acl|x-amz-acl)\s*[:=]\s*['\"]?[^,}\n]+['\"]?,?\s*\n?",
    flags=re.MULTILINE,
)

S3_URI_RE = re.compile(r"s3://(?P<bucket>[^/\s'\"<>]+)/?(?P<key>[^\s'\"<>]*)")

AWS_S3_VIRTUAL_URL_RE = re.compile(
    r"https://(?P<bucket>[A-Za-z0-9][A-Za-z0-9.-]{1,62})"
    r"\.s3(?:[.-](?:dualstack\.)?(?P<region>[a-z0-9-]+))?"
    r"\.amazonaws\.com/?(?P<key>[^\s'\"<>]*)"
)

AWS_S3_PATH_URL_RE = re.compile(
    r"https://s3(?:[.-](?:dualstack\.)?(?P<region>[a-z0-9-]+))?"
    r"\.amazonaws\.com/(?P<bucket>[^/\s'\"<>]+)/?(?P<key>[^\s'\"<>]*)"
)

AWS_S3_ENDPOINT_RE = re.compile(
    r"https://s3(?:[.-](?:dualstack\.)?[a-z0-9-]+)?\.amazonaws\.com/?"
)

OLD_OCI_PATH_ENDPOINT_RE = re.compile(
    r"https://(?P<namespace>[^./\s'\"<>]+)\.compat\.objectstorage\."
    r"(?P<region>[a-z0-9-]+)\.oraclecloud\.com/?(?P<path>[^\s'\"<>]*)"
)

OLD_OCI_VH_ENDPOINT_RE = re.compile(
    r"https://(?P<bucket>[a-z0-9][a-z0-9-]{1,62})\.vhcompat\.objectstorage\."
    r"(?P<region>[a-z0-9-]+)\.oraclecloud\.com/?(?P<path>[^\s'\"<>]*)"
)

DEFAULT_NAMESPACE = os.getenv("OCI_NAMESPACE", "your_namespace")
DEFAULT_REGION = os.getenv("OCI_REGION", "eu-frankfurt-1")
DEFAULT_BUCKET = os.getenv("OCI_BUCKET", "my-oci-bucket")
DEFAULT_ACCESS_KEY = "<OCI_CUSTOMER_SECRET_ACCESS_KEY>"
DEFAULT_SECRET_KEY = "<OCI_CUSTOMER_SECRET_KEY>"
DEFAULT_ENDPOINT_DOMAIN = os.getenv("OCI_S3_ENDPOINT_DOMAIN", "oci.customer-oci.com")


@dataclass(frozen=True)
class OciS3Config:
    namespace: str
    region: str
    bucket: str
    endpoint_style: str
    endpoint_domain: str
    access_key_id: str
    secret_access_key: str
    credential_mode: str
    tenancy_ocid: str
    user_ocid: str
    fingerprint: str
    private_key_path: str
    compartment_ocid: str

    @property
    def addressing_style(self) -> str:
        return "virtual" if self.endpoint_style == "virtual-hosted" else "path"

    @property
    def force_path_style_js(self) -> str:
        return "false" if self.endpoint_style == "virtual-hosted" else "true"

    @property
    def force_path_style_python(self) -> str:
        return "False" if self.endpoint_style == "virtual-hosted" else "True"

    def service_endpoint(self) -> str:
        if self.endpoint_style == "virtual-hosted":
            return f"https://vhcompat.objectstorage.{self.region}.{self.endpoint_domain}"
        return f"https://{self.namespace}.compat.objectstorage.{self.region}.{self.endpoint_domain}"

    def object_url(self, bucket: str, key: str = "") -> str:
        key = (key or "").lstrip("/")
        if self.endpoint_style == "virtual-hosted":
            base = f"https://{bucket}.vhcompat.objectstorage.{self.region}.{self.endpoint_domain}"
            return f"{base}/{key}" if key else base
        base = f"https://{self.namespace}.compat.objectstorage.{self.region}.{self.endpoint_domain}/{bucket}"
        return f"{base}/{key}" if key else base

    def python_access_expr(self) -> str:
        if self.credential_mode == "literal":
            return repr(self.access_key_id)
        return f'os.getenv("OCI_S3_ACCESS_KEY_ID", {self.access_key_id!r})'

    def python_secret_expr(self) -> str:
        if self.credential_mode == "literal":
            return repr(self.secret_access_key)
        return f'os.getenv("OCI_S3_SECRET_ACCESS_KEY", {self.secret_access_key!r})'

    def js_access_expr(self) -> str:
        if self.credential_mode == "literal":
            return json.dumps(self.access_key_id)
        return f"process.env.OCI_S3_ACCESS_KEY_ID || {json.dumps(self.access_key_id)}"

    def js_secret_expr(self) -> str:
        if self.credential_mode == "literal":
            return json.dumps(self.secret_access_key)
        return f"process.env.OCI_S3_SECRET_ACCESS_KEY || {json.dumps(self.secret_access_key)}"

    def shell_access_expr(self) -> str:
        if self.credential_mode == "literal":
            return self.access_key_id
        return f"${{OCI_S3_ACCESS_KEY_ID:-{self.access_key_id}}}"

    def shell_secret_expr(self) -> str:
        if self.credential_mode == "literal":
            return self.secret_access_key
        return f"${{OCI_S3_SECRET_ACCESS_KEY:-{self.secret_access_key}}}"

    def json_access_value(self) -> str:
        return self.access_key_id if self.credential_mode == "literal" else "${OCI_S3_ACCESS_KEY_ID}"

    def json_secret_value(self) -> str:
        return self.secret_access_key if self.credential_mode == "literal" else "${OCI_S3_SECRET_ACCESS_KEY}"


def detect_file_type(filepath: str) -> str:
    suffix = Path(filepath).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".sh": "shell",
        ".bash": "shell",
        ".html": "html",
        ".htm": "html",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".tf": "terraform",
    }.get(suffix, "unknown")


def strip_extra_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def remove_aws_only_headers(text: str) -> str:
    text = S3_ONLY_HEADER_LINE_RE.sub("", text)
    text = ACL_ASSIGNMENT_LINE_RE.sub("", text)
    # Remove common HTML form ACL fields.
    text = re.sub(
        r"<input[^>]*name=[\"']acl[\"'][^>]*>\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _replace_region_assignments(text: str, cfg: OciS3Config) -> str:
    # Replace common standalone region assignments while leaving arbitrary text alone.
    text = re.sub(
        r"(?P<prefix>\b(?:AWS_)?REGION\s*=\s*[\"'])[a-z0-9-]+(?P<suffix>[\"'])",
        rf"\g<prefix>{cfg.region}\g<suffix>",
        text,
    )
    text = re.sub(
        r"(?P<prefix>\bregion(?:_name)?\s*[:=]\s*[\"'])[a-z0-9-]+(?P<suffix>[\"'])",
        rf"\g<prefix>{cfg.region}\g<suffix>",
        text,
        flags=re.IGNORECASE,
    )
    return text


def convert_s3_urls(text: str, cfg: OciS3Config) -> str:
    """Convert common AWS S3 and old OCI S3-compatible URLs to current OCI URLs."""

    def replace_old_oci_path(match: re.Match[str]) -> str:
        path = (match.group("path") or "").lstrip("/")
        endpoint = cfg.service_endpoint()
        return f"{endpoint}/{path}" if path else endpoint

    def replace_old_oci_vh(match: re.Match[str]) -> str:
        bucket = match.group("bucket")
        path = (match.group("path") or "").lstrip("/")
        return cfg.object_url(bucket, path)

    def replace_path_url(match: re.Match[str]) -> str:
        return cfg.object_url(match.group("bucket"), match.group("key") or "")

    def replace_virtual_url(match: re.Match[str]) -> str:
        return cfg.object_url(match.group("bucket"), match.group("key") or "")

    text = OLD_OCI_PATH_ENDPOINT_RE.sub(replace_old_oci_path, text)
    text = OLD_OCI_VH_ENDPOINT_RE.sub(replace_old_oci_vh, text)
    text = AWS_S3_PATH_URL_RE.sub(replace_path_url, text)
    text = AWS_S3_VIRTUAL_URL_RE.sub(replace_virtual_url, text)
    text = AWS_S3_ENDPOINT_RE.sub(cfg.service_endpoint(), text)

    # Hostname-only fragments commonly found in Node http/https examples.
    service_host = urlsplit(cfg.service_endpoint()).netloc
    text = re.sub(
        r"(?P<prefix>hostname\s*[:=]\s*[`\"'])s3(?:[.-](?:dualstack\.)?[a-z0-9-]+)?\.amazonaws\.com(?P<suffix>[`\"'])",
        rf"\g<prefix>{service_host}\g<suffix>",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?P<prefix>host\s*[:=]\s*[`\"'])s3(?:[.-](?:dualstack\.)?[a-z0-9-]+)?\.amazonaws\.com(?P<suffix>[`\"'])",
        rf"\g<prefix>{service_host}\g<suffix>",
        text,
        flags=re.IGNORECASE,
    )

    # Template literals such as ${bucket}.s3.${region}.amazonaws.com.
    if cfg.endpoint_style == "virtual-hosted":
        templated_host = f"${{bucket}}.vhcompat.objectstorage.{cfg.region}.{cfg.endpoint_domain}"
        templated_path = "${key}"
    else:
        templated_host = service_host
        templated_path = "${bucket}/${key}"
    text = re.sub(
        r"\$\{bucket\}\.s3\.\$\{region\}\.amazonaws\.com",
        templated_host,
        text,
    )
    text = re.sub(
        r"(?P<prefix>path\s*[:=]\s*[`\"'])/?\$\{key\}(?P<suffix>[`\"'])",
        rf"\g<prefix>/{templated_path}\g<suffix>",
        text,
    )

    text = _replace_region_assignments(text, cfg)
    return text


def _ensure_python_import(text: str, import_line: str) -> str:
    if re.search(rf"^\s*{re.escape(import_line)}\s*$", text, flags=re.MULTILINE):
        return text

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("#!") or "coding" in lines[insert_at]
    ):
        insert_at += 1
    lines.insert(insert_at, import_line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _insert_python_block(text: str, block: str) -> str:
    if re.search(r"(?m)^\s*OCI_S3_ENDPOINT_URL\s*=", text):
        return text
    lines = text.splitlines()
    insert_at = 0

    # Keep shebang and encoding comments first.
    while insert_at < len(lines) and (
        lines[insert_at].startswith("#!") or "coding" in lines[insert_at]
    ):
        insert_at += 1

    # Skip contiguous import statements after the header.
    while insert_at < len(lines) and (
        lines[insert_at].startswith("import ")
        or lines[insert_at].startswith("from ")
        or not lines[insert_at].strip()
    ):
        insert_at += 1

    lines.insert(insert_at, block.rstrip())
    return "\n".join(lines) + "\n"


def process_python(content: str, cfg: OciS3Config) -> str:
    uses_boto3 = "boto3" in content or "botocore" in content
    content = remove_aws_only_headers(content)
    content = convert_s3_urls(content, cfg)

    for name in AWS_ACCESS_KEY_NAMES:
        content = re.sub(rf"\b{re.escape(name)}\b", "OCI_S3_ACCESS_KEY_ID", content)
    for name in AWS_SECRET_KEY_NAMES:
        content = re.sub(rf"\b{re.escape(name)}\b", "OCI_S3_SECRET_ACCESS_KEY", content)

    has_existing_oci_block = re.search(r"(?m)^\s*OCI_S3_ENDPOINT_URL\s*=", content) is not None
    if not has_existing_oci_block:
        # Remove simple original credential declarations after renaming.
        # The generated OCI block below supplies the definitions once.
        content = re.sub(
            r"(?m)^\s*OCI_S3_ACCESS_KEY_ID\s*=\s*[^\n]+\n?",
            "",
            content,
        )
        content = re.sub(
            r"(?m)^\s*OCI_S3_SECRET_ACCESS_KEY\s*=\s*[^\n]+\n?",
            "",
            content,
        )

    if cfg.credential_mode == "env" or "os.getenv" in content or "OCI_S3_ACCESS_KEY_ID" in content:
        content = _ensure_python_import(content, "import os")

    if uses_boto3:
        content = _ensure_python_import(content, "from botocore.config import Config")

    # Fix simple boto3 client/resource constructors. More complex constructors
    # are left mostly intact after credential/endpoint string replacement.
    boto3_args = (
        "endpoint_url=OCI_S3_ENDPOINT_URL, "
        "region_name=OCI_S3_REGION, "
        "aws_access_key_id=OCI_S3_ACCESS_KEY_ID, "
        "aws_secret_access_key=OCI_S3_SECRET_ACCESS_KEY, "
        "config=OCI_S3_CLIENT_CONFIG"
    )
    content = re.sub(
        r"boto3\.client\(\s*(['\"])s3\1\s*\)",
        f'boto3.client("s3", {boto3_args})',
        content,
    )
    content = re.sub(
        r"boto3\.resource\(\s*(['\"])s3\1\s*\)",
        f'boto3.resource("s3", {boto3_args})',
        content,
    )

    block_lines = [
        "",
        "# OCI Object Storage Amazon S3 Compatibility API settings",
        f'OCI_S3_ENDPOINT_URL = "{cfg.service_endpoint()}"',
        f'OCI_S3_REGION = "{cfg.region}"',
        f'OCI_S3_ADDRESSING_STYLE = "{cfg.addressing_style}"',
        f"OCI_S3_ACCESS_KEY_ID = {cfg.python_access_expr()}",
        f"OCI_S3_SECRET_ACCESS_KEY = {cfg.python_secret_expr()}",
    ]
    if uses_boto3:
        block_lines.append(
            'OCI_S3_CLIENT_CONFIG = Config(signature_version="s3v4", '
            's3={"addressing_style": OCI_S3_ADDRESSING_STYLE})'
        )
    block = "\n".join(block_lines) + "\n"
    content = _insert_python_block(content, block)

    return strip_extra_blank_lines(content)


def _insert_js_block(text: str, block: str) -> str:
    if "OCI_S3_ENDPOINT" in text:
        return text
    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("#!/")
        or lines[insert_at].startswith("import ")
        or lines[insert_at].startswith("const ") and "require(" in lines[insert_at]
        or lines[insert_at].startswith("var ") and "require(" in lines[insert_at]
        or lines[insert_at].startswith("let ") and "require(" in lines[insert_at]
        or not lines[insert_at].strip()
    ):
        insert_at += 1
    lines.insert(insert_at, block.rstrip())
    return "\n".join(lines) + "\n"


def process_javascript(content: str, cfg: OciS3Config) -> str:
    original_content = content
    needs_block = any(
        marker in original_content
        for marker in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "aws_access_key_id",
            "aws_secret_access_key",
            "AWS.S3",
            "S3Client",
            "@aws-sdk/client-s3",
            "aws-sdk",
            "s3.amazonaws.com",
        )
    )

    content = remove_aws_only_headers(content)
    content = convert_s3_urls(content, cfg)

    for name in AWS_ACCESS_KEY_NAMES:
        content = re.sub(rf"\b{re.escape(name)}\b", "OCI_S3_ACCESS_KEY_ID", content)
    for name in AWS_SECRET_KEY_NAMES:
        content = re.sub(rf"\b{re.escape(name)}\b", "OCI_S3_SECRET_ACCESS_KEY", content)

    # Remove simple original credential declarations after they have been
    # renamed. A single OCI block below supplies the definitions.
    content = re.sub(
        r"(?m)^\s*(?:const|let|var)\s+OCI_S3_ACCESS_KEY_ID\s*=\s*[^;\n]+;?\s*\n?",
        "",
        content,
    )
    content = re.sub(
        r"(?m)^\s*(?:const|let|var)\s+OCI_S3_SECRET_ACCESS_KEY\s*=\s*[^;\n]+;?\s*\n?",
        "",
        content,
    )

    block = f'''
// OCI Object Storage Amazon S3 Compatibility API settings
const OCI_S3_ENDPOINT = "{cfg.service_endpoint()}";
const OCI_S3_REGION = "{cfg.region}";
const OCI_S3_FORCE_PATH_STYLE = {cfg.force_path_style_js};
const OCI_S3_ACCESS_KEY_ID = {cfg.js_access_expr()};
const OCI_S3_SECRET_ACCESS_KEY = {cfg.js_secret_expr()};
'''
    if needs_block:
        content = _insert_js_block(content, block)

    # AWS SDK v2 simple constructor.
    content = re.sub(
        r"new\s+AWS\.S3\(\s*\)",
        "new AWS.S3({\n"
        "  endpoint: OCI_S3_ENDPOINT,\n"
        "  region: OCI_S3_REGION,\n"
        "  accessKeyId: OCI_S3_ACCESS_KEY_ID,\n"
        "  secretAccessKey: OCI_S3_SECRET_ACCESS_KEY,\n"
        "  signatureVersion: \"v4\",\n"
        "  s3ForcePathStyle: OCI_S3_FORCE_PATH_STYLE\n"
        "})",
        content,
    )

    # AWS SDK v3 simple constructor.
    content = re.sub(
        r"new\s+S3Client\(\s*\{\s*\}\s*\)",
        "new S3Client({\n"
        "  endpoint: OCI_S3_ENDPOINT,\n"
        "  region: OCI_S3_REGION,\n"
        "  credentials: {\n"
        "    accessKeyId: OCI_S3_ACCESS_KEY_ID,\n"
        "    secretAccessKey: OCI_S3_SECRET_ACCESS_KEY\n"
        "  },\n"
        "  forcePathStyle: OCI_S3_FORCE_PATH_STYLE\n"
        "})",
        content,
    )

    return strip_extra_blank_lines(content)

def _extract_shell_assignment(content: str, name: str) -> Optional[str]:
    pattern = re.compile(
        rf"^\s*(?:export\s+)?{re.escape(name)}=(?P<quote>['\"]?)(?P<value>.*?)(?P=quote)\s*$",
        flags=re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return None
    value = match.group("value").strip()
    if value.endswith(";"):
        value = value[:-1]
    return value


def process_shell_script(content: str, cfg: OciS3Config) -> str:
    """Convert common AWS shell uploads to AWS CLI + OCI S3 endpoint."""
    content = remove_aws_only_headers(content)
    content = convert_s3_urls(content, cfg)

    lines = content.strip().splitlines()
    if lines and lines[0].startswith("#!"):
        shebang = lines[0]
    else:
        shebang = "#!/usr/bin/env bash"

    file_path = _extract_shell_assignment(content, "FILE_PATH") or _extract_shell_assignment(content, "FILE") or "my_upload_file.txt"
    key = _extract_shell_assignment(content, "KEY") or _extract_shell_assignment(content, "OBJECT_NAME") or "uploads/$(basename \"$FILE_PATH\")"
    bucket = _extract_shell_assignment(content, "BUCKET") or cfg.bucket

    # The AWS CLI still expects AWS_* environment variable names, but the values
    # are OCI Customer Secret Key values.
    script = f'''{shebang}
set -euo pipefail

# OCI Object Storage Amazon S3 Compatibility API settings
OCI_S3_ENDPOINT="{cfg.service_endpoint()}"
OCI_S3_REGION="{cfg.region}"
OCI_S3_ADDRESSING_STYLE="{cfg.addressing_style}"

# These are OCI Customer Secret Key values. The AWS CLI reads AWS_* names.
export AWS_ACCESS_KEY_ID="{cfg.shell_access_expr()}"
export AWS_SECRET_ACCESS_KEY="{cfg.shell_secret_expr()}"
export AWS_DEFAULT_REGION="$OCI_S3_REGION"

BUCKET="{bucket}"
FILE_PATH="{file_path}"
KEY="{key}"

# Make addressing style explicit for custom S3-compatible endpoints.
TMP_AWS_CONFIG="${{TMPDIR:-/tmp}}/oci_s3_aws_config.$$"
trap 'rm -f "$TMP_AWS_CONFIG"' EXIT
cat > "$TMP_AWS_CONFIG" <<EOF
[default]
region = $OCI_S3_REGION
s3 =
    addressing_style = $OCI_S3_ADDRESSING_STYLE
EOF
export AWS_CONFIG_FILE="$TMP_AWS_CONFIG"

aws --endpoint-url "$OCI_S3_ENDPOINT" s3api put-object \\
  --bucket "$BUCKET" \\
  --key "$KEY" \\
  --body "$FILE_PATH"
'''
    return strip_extra_blank_lines(script)


def process_html(content: str, cfg: OciS3Config) -> str:
    content = remove_aws_only_headers(content)
    content = convert_s3_urls(content, cfg)
    content = re.sub(
        r"name=[\"']AWSAccessKeyId[\"']\s+value=[\"'][^\"']*[\"']",
        f'name="AWSAccessKeyId" value="{cfg.json_access_value()}"',
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"name=[\"']x-amz-credential[\"']\s+value=[\"'][^\"']*[\"']",
        f'name="x-amz-credential" value="{cfg.json_access_value()}/YYYYMMDD/{cfg.region}/s3/aws4_request"',
        content,
        flags=re.IGNORECASE,
    )
    if "AWSAccessKeyId" in content or "x-amz-credential" in content:
        note = (
            "<!-- OCI S3 Compatibility note: regenerate any browser-upload "
            "policy and signature with AWS Signature Version 4 using an OCI "
            "Customer Secret Key. OCI does not support AWS SigV2. -->\n"
        )
        if "OCI S3 Compatibility note" not in content:
            content = note + content
    return strip_extra_blank_lines(content)


def _transform_json_value(value: Any, cfg: OciS3Config, depth: int = 0) -> Any:
    if isinstance(value, str):
        return convert_s3_urls(value, cfg)
    if isinstance(value, list):
        return [_transform_json_value(item, cfg, depth + 1) for item in value]
    if not isinstance(value, dict):
        return value

    out: dict[str, Any] = {}
    for key, raw_value in value.items():
        lower = key.lower().replace("-", "_")
        if lower in {"acl", "x_amz_acl"} or lower.startswith("x_amz_grant"):
            continue
        if lower in {"aws_access_key", "aws_access_key_id", "access_key", "access_key_id"}:
            out["oci_s3_access_key_id"] = cfg.json_access_value()
            continue
        if lower in {"aws_secret_key", "aws_secret_access_key", "secret_key", "secret_access_key"}:
            out["oci_s3_secret_access_key"] = cfg.json_secret_value()
            continue
        if lower in {"endpoint", "endpoint_url", "s3_endpoint", "host", "hostname"}:
            out[key] = cfg.service_endpoint()
            continue
        if lower in {"region", "aws_region", "region_name"}:
            out[key] = cfg.region
            continue
        if lower in {"addressing_style", "s3_addressing_style"}:
            out[key] = cfg.addressing_style
            continue
        if lower in {"force_path_style", "use_path_style", "path_style"}:
            out[key] = cfg.endpoint_style != "virtual-hosted"
            continue
        out[key] = _transform_json_value(raw_value, cfg, depth + 1)

    if depth == 0:
        out.setdefault("endpoint_url", cfg.service_endpoint())
        out.setdefault("region", cfg.region)
        out.setdefault("addressing_style", cfg.addressing_style)
        out.setdefault("oci_s3_access_key_id", cfg.json_access_value())
        out.setdefault("oci_s3_secret_access_key", cfg.json_secret_value())
    return out


def process_json(content: str, cfg: OciS3Config) -> str:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        text = remove_aws_only_headers(content)
        text = convert_s3_urls(text, cfg)
        text = re.sub(r'"aws_access_key(?:_id)?"\s*:\s*"[^"]*"', f'"oci_s3_access_key_id": "{cfg.json_access_value()}"', text)
        text = re.sub(r'"aws_secret_(?:access_)?key"\s*:\s*"[^"]*"', f'"oci_s3_secret_access_key": "{cfg.json_secret_value()}"', text)
        return strip_extra_blank_lines(text)

    transformed = _transform_json_value(data, cfg)
    return json.dumps(transformed, indent=2, ensure_ascii=False) + "\n"


def process_yaml(content: str, cfg: OciS3Config) -> str:
    text = remove_aws_only_headers(content)
    text = convert_s3_urls(text, cfg)
    text = re.sub(
        r"(?m)^(?P<indent>\s*)(?:aws_)?access_key(?:_id)?\s*:\s*.*$",
        rf"\g<indent>oci_s3_access_key_id: \"{cfg.json_access_value()}\"",
        text,
    )
    text = re.sub(
        r"(?m)^(?P<indent>\s*)(?:aws_)?secret_(?:access_)?key\s*:\s*.*$",
        rf"\g<indent>oci_s3_secret_access_key: \"{cfg.json_secret_value()}\"",
        text,
    )
    text = re.sub(
        r"(?m)^(?P<indent>\s*)(?:endpoint|endpoint_url|s3_endpoint)\s*:\s*.*$",
        rf"\g<indent>endpoint_url: \"{cfg.service_endpoint()}\"",
        text,
    )
    text = re.sub(
        r"(?m)^(?P<indent>\s*)region\s*:\s*.*$",
        rf"\g<indent>region: \"{cfg.region}\"",
        text,
    )
    text = re.sub(
        r"(?m)^(?P<indent>\s*)addressing_style\s*:\s*.*$",
        rf"\g<indent>addressing_style: \"{cfg.addressing_style}\"",
        text,
    )
    if "endpoint_url:" not in text:
        block = f'''
# OCI Object Storage Amazon S3 Compatibility API settings
oci_s3:
  endpoint_url: "{cfg.service_endpoint()}"
  region: "{cfg.region}"
  addressing_style: "{cfg.addressing_style}"
  access_key_id: "{cfg.json_access_value()}"
  secret_access_key: "{cfg.json_secret_value()}"
'''
        text = block.strip() + "\n\n" + text
    return strip_extra_blank_lines(text)


def _find_matching_brace(text: str, open_brace_index: int) -> int:
    depth = 0
    in_string: Optional[str] = None
    escape = False
    i = open_brace_index
    while i < len(text):
        char = text[i]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
        else:
            if char in {'"', "'"}:
                in_string = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _update_s3_backend_block(body: str, cfg: OciS3Config) -> str:
    body = re.sub(r"(?ms)^\s*endpoints\s*=\s*\{.*?^\s*\}\s*", "", body)
    body = re.sub(r"(?m)^\s*endpoint\s*=\s*\"[^\"]*\"\s*", "", body)
    for key in (
        "skip_region_validation",
        "skip_credentials_validation",
        "skip_requesting_account_id",
        "skip_metadata_api_check",
        "force_path_style",
        "use_path_style",
        "skip_s3_checksum",
    ):
        body = re.sub(rf"(?m)^\s*{key}\s*=\s*[^\n]+\n?", "", body)

    body = re.sub(
        r"(?m)^(\s*region\s*=\s*)\"[^\"]*\"",
        rf'\1"{cfg.region}"',
        body,
    )
    if not re.search(r"(?m)^\s*region\s*=", body):
        body += f'\n    region = "{cfg.region}"\n'

    path_bool = "false" if cfg.endpoint_style == "virtual-hosted" else "true"
    additions = f'''
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    use_path_style              = {path_bool}
    skip_s3_checksum            = true
    endpoints = {{
      s3 = "{cfg.service_endpoint()}"
    }}
'''
    return body.rstrip() + "\n" + additions.rstrip() + "\n  "


def update_terraform_s3_backend(text: str, cfg: OciS3Config) -> str:
    search_from = 0
    while True:
        match = re.search(r'backend\s+"s3"\s*\{', text[search_from:], flags=re.MULTILINE)
        if not match:
            break
        start = search_from + match.start()
        open_brace = text.find("{", start)
        close_brace = _find_matching_brace(text, open_brace)
        if close_brace == -1:
            break
        body = text[open_brace + 1 : close_brace]
        new_body = _update_s3_backend_block(body, cfg)
        text = text[: open_brace + 1] + new_body + text[close_brace:]
        search_from = open_brace + 1 + len(new_body)
    return text


def process_terraform(content: str, cfg: OciS3Config) -> str:
    text = remove_aws_only_headers(content)
    text = convert_s3_urls(text, cfg)
    text = update_terraform_s3_backend(text, cfg)

    # Native OCI provider/resource conversion for simple AWS bucket examples.
    text = re.sub(
        r'provider\s+"aws"\s*\{[^}]*\}',
        f'''provider "oci" {{
  tenancy_ocid     = "{cfg.tenancy_ocid}"
  user_ocid        = "{cfg.user_ocid}"
  fingerprint      = "{cfg.fingerprint}"
  private_key_path = "{cfg.private_key_path}"
  region           = "{cfg.region}"
}}''',
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r'resource\s+"aws_s3_bucket"\s+"([^"]+)"\s*\{[^}]*\}',
        lambda m: f'''resource "oci_objectstorage_bucket" "{m.group(1)}" {{
  compartment_id    = "{cfg.compartment_ocid}"
  name              = "{cfg.bucket}"
  namespace         = "{cfg.namespace}"
  storage_tier      = "Standard"
  public_access_type = "NoPublicAccess"
}}''',
        text,
        flags=re.DOTALL,
    )
    return strip_extra_blank_lines(text)


def transform_content(content: str, filetype: str, cfg: OciS3Config) -> str:
    processors: dict[str, Callable[[str, OciS3Config], str]] = {
        "python": process_python,
        "javascript": process_javascript,
        "shell": process_shell_script,
        "html": process_html,
        "json": process_json,
        "yaml": process_yaml,
        "terraform": process_terraform,
    }
    processor = processors.get(filetype)
    if processor is None:
        return strip_extra_blank_lines(convert_s3_urls(remove_aws_only_headers(content), cfg))
    return processor(content, cfg)


def validate_filetype(filetype: str, content: str, cfg: OciS3Config) -> list[str]:
    issues: list[str] = []
    if ".amazonaws.com" in content:
        issues.append("still contains an amazonaws.com endpoint")
    if ".oraclecloud.com" in content and cfg.endpoint_domain == "oci.customer-oci.com":
        issues.append("still contains the legacy oraclecloud.com S3-compatible endpoint")
    if re.search(r"x-amz-(acl|grant-|object-lock-)", content, flags=re.IGNORECASE):
        issues.append("still contains AWS-only ACL/grant/object-lock headers")
    if re.search(r"signature[_-]?version\s*[:=]\s*['\"]?s3(?!v4)['\"]?", content, flags=re.IGNORECASE):
        issues.append("appears to request AWS Signature Version 2 instead of SigV4")
    if cfg.endpoint_domain not in content and filetype != "unknown":
        issues.append("does not contain the configured OCI S3-compatible endpoint")

    if filetype in {"python", "javascript", "shell", "json", "yaml"}:
        if "OCI_S3_ACCESS_KEY_ID" not in content and "oci_s3_access_key_id" not in content and "AWS_ACCESS_KEY_ID" not in content:
            issues.append("does not expose an OCI Customer Secret access key reference")
        if "OCI_S3_SECRET_ACCESS_KEY" not in content and "oci_s3_secret_access_key" not in content and "AWS_SECRET_ACCESS_KEY" not in content:
            issues.append("does not expose an OCI Customer Secret key reference")

    if filetype == "terraform" and 'backend "s3"' in content and "endpoints" not in content:
        issues.append("S3 backend does not contain an explicit endpoints block")
    if filetype == "terraform" and 'provider "aws"' in content:
        issues.append("still contains an AWS provider block")
    if filetype == "terraform" and "aws_s3_bucket" in content:
        issues.append("still contains an aws_s3_bucket resource")

    return issues


def _read_file_list(list_path: Path) -> list[str]:
    with list_path.open("r", encoding="utf-8") as handle:
        return [
            line.strip()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]


def _destination_path(src_file: str, suffix: str, in_place: bool) -> Path:
    src_path = Path(src_file)
    if in_place:
        return src_path
    return src_path.with_name(f"{src_path.stem}{suffix}{src_path.suffix}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert common AWS S3 usage to OCI Object Storage S3-compatible usage."
    )
    parser.add_argument("-l", "--list", required=True, help="Path to source_aws_files.txt")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE, help="OCI Object Storage namespace")
    parser.add_argument("--region", default=DEFAULT_REGION, help="OCI region identifier, for example eu-frankfurt-1")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Default bucket name for generated examples")
    parser.add_argument(
        "--endpoint-style",
        choices=("path", "virtual-hosted"),
        default=os.getenv("OCI_S3_ENDPOINT_STYLE", "path"),
        help="OCI S3-compatible addressing style to emit",
    )
    parser.add_argument(
        "--endpoint-domain",
        default=DEFAULT_ENDPOINT_DOMAIN,
        help="Endpoint domain suffix. Current default: oci.customer-oci.com. Use oraclecloud.com only for legacy clients.",
    )
    parser.add_argument("--access-key-id", default=DEFAULT_ACCESS_KEY, help="OCI Customer Secret access key")
    parser.add_argument("--secret-access-key", default=DEFAULT_SECRET_KEY, help="OCI Customer Secret key")
    parser.add_argument(
        "--credential-mode",
        choices=("env", "literal"),
        default=os.getenv("OCI_S3_CREDENTIAL_MODE", "env"),
        help="env writes generated code that reads OCI_S3_* environment variables; literal embeds the provided values",
    )
    parser.add_argument("--output-suffix", default="_OCI", help="Suffix for generated files")
    parser.add_argument("--in-place", action="store_true", help="Overwrite source files instead of writing suffixed copies")
    parser.add_argument("--backup", action="store_true", help="When --in-place is used, create .bak files first")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report changes without writing output files")

    # Optional values used only if Terraform AWS provider/resources are converted
    # to native OCI provider/resources.
    parser.add_argument("--tenancy-ocid", default=os.getenv("OCI_TENANCY_OCID", "ocid1.tenancy.oc1..example"))
    parser.add_argument("--user-ocid", default=os.getenv("OCI_USER_OCID", "ocid1.user.oc1..example"))
    parser.add_argument("--fingerprint", default=os.getenv("OCI_FINGERPRINT", "00:00:00:00:example"))
    parser.add_argument("--private-key-path", default=os.getenv("OCI_PRIVATE_KEY_PATH", "~/.oci/oci_api_key.pem"))
    parser.add_argument("--compartment-ocid", default=os.getenv("OCI_COMPARTMENT_OCID", "ocid1.compartment.oc1..example"))
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> OciS3Config:
    return OciS3Config(
        namespace=args.namespace,
        region=args.region,
        bucket=args.bucket,
        endpoint_style=args.endpoint_style,
        endpoint_domain=args.endpoint_domain,
        access_key_id=args.access_key_id,
        secret_access_key=args.secret_access_key,
        credential_mode=args.credential_mode,
        tenancy_ocid=args.tenancy_ocid,
        user_ocid=args.user_ocid,
        fingerprint=args.fingerprint,
        private_key_path=args.private_key_path,
        compartment_ocid=args.compartment_ocid,
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    cfg = build_config(args)
    list_path = Path(args.list)

    if not list_path.exists():
        print(f"[ERROR] File list not found: {list_path}")
        return 2

    files = _read_file_list(list_path)
    if not files:
        print(f"[WARN] No source files found in list: {list_path}")
        return 0

    print(f"[INFO] OCI S3 endpoint: {cfg.service_endpoint()}")
    print(f"[INFO] Addressing style: {cfg.addressing_style}")

    for src_file in files:
        src_path = Path(src_file)
        if not src_path.exists():
            print(f"[WARN] File not found: {src_file}")
            continue

        filetype = detect_file_type(src_file)
        content = src_path.read_text(encoding="utf-8")
        new_content = transform_content(content, filetype, cfg)
        issues = validate_filetype(filetype, new_content, cfg)

        if issues:
            print(f"[WARNING] {src_file} converted as {filetype}, but needs review:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"[VALID] {src_file} passed OCI S3 compatibility checks as {filetype}.")

        dest_file = _destination_path(src_file, args.output_suffix, args.in_place)
        if args.dry_run:
            print(f"[DRY-RUN] Would write: {dest_file}")
            continue

        if args.in_place and args.backup:
            backup_path = src_path.with_name(f"{src_path.name}.bak")
            shutil.copy2(src_path, backup_path)
            print(f"[OK] Backup written: {backup_path}")

        dest_file.write_text(new_content, encoding="utf-8")
        print(f"[OK] Converted: {src_file} -> {dest_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
