# AWS to OCI S3 Compatibility Conversion Toolkit

This toolkit automates the conversion of source files in batch mode that use AWS S3 APIs, credentials, hostnames, and access logic into Oracle Cloud Infrastructure (OCI) compatible equivalents.

## Purpose

Many applications and scripts are written to work with Amazon S3. OCI offers an S3-compatible Object Storage API, but direct reuse is limited due to differences in endpoints, authentication, headers, and tooling. This tool performs automated transformations to support OCI compatibility. It can be easily be extended to support other formats, with the same logic. 

## Features

- Converts AWS S3 API calls, hostnames, and URLs to OCI format
- Replaces AWS access keys and secrets with OCI-compatible variables
- Removes AWS-only headers (like ACL, grants)
- Supports multiple file types:
  - `.py` Python scripts
  - `.js` Node.js modules (AWS SDK → OCI SDK)
  - `.sh` Shell scripts using signed curl or CLI
  - `.json` AWS config → OCI config
  - `.yaml` config references
  - `.html` forms using AWS credentials and upload policies
  - `.tf` Terraform scripts (AWS provider → OCI)

## File Structure

- `aws2oci_api_adapt.py` — The main conversion script
- `source_aws_files.txt` — A list of file paths to process
- Transformed files will be written to the same directory with `_OCI` suffix before the extension
- Set of filetype-specific validation checks in the logic.

## Usage

```bash
python3 aws2oci_api_adapt.py -l source_aws_files.txt
```

- Make sure to replace the hardcoded constants at the top of the script with your actual OCI credentials and region
- Your `source_aws_files.txt` should list one file per line (e.g., `myapp/upload.js`)
- Make sure to replace the hardcoded 'sample' identity constants declared at the beginning of the script with your own identity and signing values.
  
## Output

- Each file is converted and validated
- Valid transformations are confirmed with `[VALID]`
- Files that may still include AWS-specific logic are flagged with `[WARNING]`

## Requirements

- Python 3.7+
- `oci` CLI or SDK installed (for runtime execution of transformed files)

## Limitations

- Transformation logic expects a conventional code structure
- Complex obfuscation or AWS logic wrapped in dynamic or nested structures may require manual review.
- JavaScript, Python, and other adaptations may require the usage of client-side OCI SDK, as they originally were intended to be used with AWS SDK. Others may require external signers. For those SDK cases, it may surely require config files for the OCI SDK for correct configuration. Those config files will contain ID and values that need to be replicated in the mentioned header of the script aws2oci_api_adapt.py. Those are independent values that won't interfere with their respective operations. In other words, if there are any wrongly set values in any of these cases, The SDK or this script won't perform as expected, but they have no dependency on each other.

## Example

**Before (Python):**
```python
AWS_ACCESS_KEY_ID = "AKIA..."
AWS_SECRET_ACCESS_KEY = "abc123..."
url = "https://mybucket.s3.us-west-2.amazonaws.com/file"
```

**After (_OCI.py):**
```python
OCI_ACCESS_KEY_ID = "ocid1.credential.oc1..."
OCI_SECRET_ACCESS_KEY = "xyz987..."
url = "https://namespace.compat.objectstorage.eu-frankfurt-1.oraclecloud.com/mybucket/file"
```

## Authors

Script by Jose Villar. Adapted and extended for automation and validation with Python.

---
This project is not affiliated with or supported by Oracle. Use at your own discretion.

-----------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------
# AWS S3 to OCI Object Storage S3 Compatibility Conversion Toolkit

This toolkit batch-converts common Amazon S3 usage in source files and configuration files to Oracle Cloud Infrastructure (OCI) Object Storage's Amazon S3 Compatibility API.

It updates S3 endpoints, credentials, common SDK client options, shell upload flows, JSON/YAML configuration, HTML upload forms, and selected Terraform patterns. Converted files are written beside the source files with an `_OCI` suffix by default.

## What changed in this update

This version adopts the current OCI Object Storage S3-compatible endpoint model:

- Path-style endpoint, used by default:
  `https://<namespace>.compat.objectstorage.<region>.oci.customer-oci.com`
- Virtual-hosted service endpoint:
  `https://vhcompat.objectstorage.<region>.oci.customer-oci.com`
- Virtual-hosted object URL:
  `https://<bucket>.vhcompat.objectstorage.<region>.oci.customer-oci.com/<object_name>`
- Legacy `oraclecloud.com` S3-compatible endpoints are converted to the current `oci.customer-oci.com` endpoint domain unless you explicitly override `--endpoint-domain`.
- The generated code uses OCI Customer Secret Key values for S3-compatible clients. These are an access key and secret key pair, not the native OCI API signing key pair.
- The generated SDK and CLI examples use AWS Signature Version 4. SigV2 is not supported by OCI Object Storage's S3 Compatibility API.
- Credentials are not hardcoded by default. Generated files read from `OCI_S3_ACCESS_KEY_ID` and `OCI_S3_SECRET_ACCESS_KEY` unless you intentionally use `--credential-mode literal`.

## Supported input file types

- `.py` Python scripts, including simple `boto3.client("s3")` and `boto3.resource("s3")` usage
- `.js`, `.mjs`, `.cjs` JavaScript or Node.js files using common AWS SDK v2/v3 S3 patterns
- `.sh`, `.bash` shell scripts, converted to AWS CLI `s3api put-object` with an OCI endpoint
- `.json` S3 client configuration files
- `.yaml`, `.yml` S3 client configuration files
- `.html`, `.htm` upload forms, with endpoint and obvious ACL field cleanup
- `.tf` Terraform files, including simple AWS S3 bucket resources and S3 backend blocks

## Requirements

For the converter itself:

- Python 3.8 or later
- No third-party Python packages are required for the converter

For the converted files, requirements depend on the source language and runtime:

- Python outputs that use `boto3` need `boto3` and `botocore` installed.
- JavaScript outputs continue to use AWS SDK patterns where possible, so install the AWS SDK package used by the original source, such as `aws-sdk` or `@aws-sdk/client-s3`.
- Shell outputs use the AWS CLI with `--endpoint-url` pointed at OCI Object Storage.
- Terraform outputs that are converted to native OCI resources need the OCI Terraform provider. Terraform S3 backend conversion remains compatibility-focused; use the native OCI backend where available.

## Setup

Create or identify an OCI Customer Secret Key for the user that will access Object Storage. Save both values securely:

- Access Key: exported as `OCI_S3_ACCESS_KEY_ID`
- Secret Key: exported as `OCI_S3_SECRET_ACCESS_KEY`

Example:

```bash
export OCI_S3_ACCESS_KEY_ID="<your_customer_secret_access_key>"
export OCI_S3_SECRET_ACCESS_KEY="<your_customer_secret_key>"
```

Also gather:

- OCI Object Storage namespace, for example `mytenancynamespace`
- OCI region identifier, for example `eu-frankfurt-1`
- Default bucket name to use in generated examples, for example `my-bucket`

## Usage

Create a file list with one source path per line:

```text
app/upload.py
web/upload.js
scripts/upload.sh
config/s3.json
infra/backend.tf
```

Run the converter in default path-style mode:

```bash
python3 aws2oci_api_adapt.py \
  --list source_aws_files.txt \
  --namespace mytenancynamespace \
  --region eu-frankfurt-1 \
  --bucket my-bucket
```

Run with virtual-hosted style output:

```bash
python3 aws2oci_api_adapt.py \
  --list source_aws_files.txt \
  --namespace mytenancynamespace \
  --region eu-frankfurt-1 \
  --bucket my-virtual-bucket \
  --endpoint-style virtual-hosted
```

Preview without writing files:

```bash
python3 aws2oci_api_adapt.py \
  --list source_aws_files.txt \
  --namespace mytenancynamespace \
  --region eu-frankfurt-1 \
  --bucket my-bucket \
  --dry-run
```

Overwrite source files, keeping `.bak` backups:

```bash
python3 aws2oci_api_adapt.py \
  --list source_aws_files.txt \
  --namespace mytenancynamespace \
  --region eu-frankfurt-1 \
  --bucket my-bucket \
  --in-place \
  --backup
```

## Main command-line options

| Option | Default | Description |
| --- | --- | --- |
| `-l`, `--list` | Required | Text file containing one source path per line. |
| `--namespace` | `OCI_NAMESPACE` env var or `your_namespace` | OCI Object Storage namespace. Required for path-style endpoints. |
| `--region` | `OCI_REGION` env var or `eu-frankfurt-1` | OCI region identifier. |
| `--bucket` | `OCI_BUCKET` env var or `my-oci-bucket` | Default bucket name used in generated examples. |
| `--endpoint-style` | `path` | Use `path` or `virtual-hosted`. |
| `--endpoint-domain` | `oci.customer-oci.com` | Current OCI S3-compatible endpoint domain suffix. Use `oraclecloud.com` only for a legacy requirement. |
| `--access-key-id` | `<OCI_CUSTOMER_SECRET_ACCESS_KEY>` placeholder | Fallback value to write only as a placeholder in generated env-mode code, or as the literal access key when `--credential-mode literal` is used. |
| `--secret-access-key` | `<OCI_CUSTOMER_SECRET_KEY>` placeholder | Fallback value to write only as a placeholder in generated env-mode code, or as the literal secret key when `--credential-mode literal` is used. |
| `--credential-mode` | `env` | `env` writes generated code that reads environment variables. `literal` embeds provided key values. |
| `--output-suffix` | `_OCI` | Suffix placed before each converted file extension. |
| `--dry-run` | Off | Report conversions and validation without writing output. |
| `--in-place` | Off | Overwrite source files instead of writing suffixed copies. |
| `--backup` | Off | With `--in-place`, write `.bak` backups first. |

Terraform-specific options are available for simple AWS provider/resource conversion: `--tenancy-ocid`, `--user-ocid`, `--fingerprint`, `--private-key-path`, and `--compartment-ocid`.

## Output

For each source file, the tool prints one of these results:

- `[VALID]` when the generated output passes built-in compatibility checks
- `[WARNING]` when the output was converted but still contains patterns that need manual review
- `[WARN]` for missing source files or non-fatal file list issues
- `[OK]` when a converted file is written

By default, `app/upload.py` becomes `app/upload_OCI.py`.

## What the converter changes

### Python

- Adds OCI S3-compatible endpoint, region, addressing style, and Customer Secret Key variables.
- Converts simple `boto3.client("s3")` and `boto3.resource("s3")` calls to include:
  - `endpoint_url`
  - `region_name`
  - Customer Secret Key credentials
  - `Config(signature_version="s3v4", s3={"addressing_style": ...})`
- Converts common AWS S3 URLs to OCI object URLs.

### JavaScript

- Adds OCI S3-compatible endpoint, region, addressing style, and Customer Secret Key variables.
- Converts simple AWS SDK v2 `new AWS.S3()` constructors.
- Converts simple AWS SDK v3 `new S3Client({})` constructors.
- Converts common AWS S3 URLs to OCI object URLs.

### Shell

- Replaces common AWS S3 upload scripts with an AWS CLI `s3api put-object` flow.
- Uses `--endpoint-url` with the configured OCI S3-compatible endpoint.
- Exports AWS CLI credential environment variables from OCI Customer Secret Key values.
- Writes a temporary AWS CLI config file to make S3 addressing style explicit.

### JSON and YAML

- Converts common endpoint, region, credential, and addressing-style keys.
- Removes common ACL/grant/object-lock fields.
- Adds OCI S3-compatible defaults when the top-level config is missing them.

### HTML

- Converts S3 URLs and removes obvious ACL form fields.
- Adds a review comment when browser upload signature fields are present. Browser-upload policies and signatures must be regenerated with SigV4 using an OCI Customer Secret Key.

### Terraform

- Updates S3 backend blocks with OCI S3-compatible endpoint settings, including `endpoints = { s3 = ... }` for modern Terraform S3 backend syntax.
- Converts simple `provider "aws"` blocks to `provider "oci"` blocks using the Terraform-specific OCI identity options.
- Converts simple `aws_s3_bucket` resources to `oci_objectstorage_bucket` resources.

## Important OCI S3 compatibility notes

- Use OCI Customer Secret Keys for S3-compatible access. Do not use native OCI API signing keys as S3 access keys.
- Do not commit access keys or secret keys to source control. The default `env` credential mode is recommended.
- OCI does not support AWS Signature Version 2 for the S3 Compatibility API.
- OCI does not use S3 object ACLs. Use OCI IAM policies, compartments, and bucket settings instead.
- Path-style access remains supported and is the safest default for existing buckets.
- Virtual-hosted style requires bucket names that are valid DNS labels. Bucket names must be lowercase letters, numbers, and hyphens, must be 3 to 63 characters, must not begin with a hyphen, and must not contain consecutive hyphens. Existing buckets may need REGION scope and uniqueness checks before virtual-hosted style is enabled.
- If an application cannot set the OCI region identifier, OCI documentation says to use `us-east-1` or leave the region blank, but that limits use to the tenancy home region. Prefer setting the real OCI region when the client supports it.
- Terraform's S3-compatible backend is documented as deprecated by OCI for new Terraform state configurations. Prefer the native OCI backend when your Terraform version supports it.

## Before and after examples

### Python before

```python
import boto3

AWS_ACCESS_KEY_ID = "AKIA..."
AWS_SECRET_ACCESS_KEY = "abc123..."
s3 = boto3.client("s3")
url = "https://mybucket.s3.us-west-2.amazonaws.com/file.txt"
```

### Python after, path-style default

```python
from botocore.config import Config
import os
import boto3

# OCI Object Storage Amazon S3 Compatibility API settings
OCI_S3_ENDPOINT_URL = "https://mytenancynamespace.compat.objectstorage.eu-frankfurt-1.oci.customer-oci.com"
OCI_S3_REGION = "eu-frankfurt-1"
OCI_S3_ADDRESSING_STYLE = "path"
OCI_S3_ACCESS_KEY_ID = os.getenv("OCI_S3_ACCESS_KEY_ID", "<OCI_CUSTOMER_SECRET_ACCESS_KEY>")
OCI_S3_SECRET_ACCESS_KEY = os.getenv("OCI_S3_SECRET_ACCESS_KEY", "<OCI_CUSTOMER_SECRET_KEY>")
OCI_S3_CLIENT_CONFIG = Config(signature_version="s3v4", s3={"addressing_style": OCI_S3_ADDRESSING_STYLE})

s3 = boto3.client(
    "s3",
    endpoint_url=OCI_S3_ENDPOINT_URL,
    region_name=OCI_S3_REGION,
    aws_access_key_id=OCI_S3_ACCESS_KEY_ID,
    aws_secret_access_key=OCI_S3_SECRET_ACCESS_KEY,
    config=OCI_S3_CLIENT_CONFIG,
)
url = "https://mytenancynamespace.compat.objectstorage.eu-frankfurt-1.oci.customer-oci.com/mybucket/file.txt"
```

### Object URL after, virtual-hosted style

```text
https://mybucket.vhcompat.objectstorage.eu-frankfurt-1.oci.customer-oci.com/file.txt
```

## Limitations

This is a regex- and template-based conversion helper, not a full parser or compiler for every supported language. Manual review is still required, especially for:

- Dynamic endpoint construction
- Custom request-signing code
- Browser form uploads and presigned POST policies
- Complex SDK client factories
- Generated code or minified JavaScript
- Terraform modules with nested or highly dynamic HCL

Run your normal tests and review generated diffs before committing converted files.

## References

- OCI Object Storage Amazon S3 Compatibility API: https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/s3compatibleapi.htm
- OCI S3 virtual-hosted style support: https://docs.oracle.com/en-us/iaas/Content/Object/s3-virtual-style.htm
- OCI Customer Secret Keys: https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingcredentials.htm#Working_with_Customer_Secret_Keys
- Terraform state files in OCI Object Storage: https://docs.oracle.com/en-us/iaas/Content/dev/terraform/object-storage-state.htm

## Disclaimer

Script by Jose Villar. Adapted and extended for automation and validation with Python.

This project is not affiliated with or supported by Oracle. Use at your own discretion.
