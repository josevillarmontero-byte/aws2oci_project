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

