#!/bin/bash

# OCI Signature V1 Configuration
TENANCY_OCID="ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
USER_OCID="ocid1.user.oc1..aaaaaaaaexampleuser"
FINGERPRINT="20:3b:97:13:example:fingerprint"
PRIVATE_KEY_PATH="$HOME/.oci/oci_api_key.pem"

# Target Storage Info
NAMESPACE="fr9qm01aaaa"
REGION="eu-frankfurt-1"
BUCKET="my-oci-bucket"

FILE_PATH="my_upload_file.txt"
KEY="uploads/$(basename "$FILE_PATH")"

# Compute signed date
DATE=$(LC_ALL=C date -u "+%a, %d %b %Y %H:%M:%S GMT")
HOST="$NAMESPACE.compat.objectstorage.$REGION.oraclecloud.com"
TARGET="/$BUCKET/$KEY"

# Build signing string safely
SIGNING_STRING=$(printf "date: %s\n(host): %s\n(request-target): put %s" "$DATE" "$HOST" "$TARGET")

# Generate signature using private key
SIGNATURE=$(printf "$SIGNING_STRING" | \
  openssl dgst -sha256 -sign "$PRIVATE_KEY_PATH" | \
  openssl base64 -A)

# Assemble Authorization header
AUTH_HEADER='Signature version="1",keyId="'$TENANCY_OCID'/'$USER_OCID'/'$FINGERPRINT'",algorithm="rsa-sha256",headers="date (host) request-target",signature="'$SIGNATURE'"'

# Perform the upload
curl -i -X PUT -T "$FILE_PATH" \
  -H "host: $HOST" \
  -H "date: $DATE" \
  -H "authorization: $AUTH_HEADER" \
  "https://$HOST/$BUCKET/$KEY"
