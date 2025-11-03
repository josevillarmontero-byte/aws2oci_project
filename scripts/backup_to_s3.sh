#!/bin/bash

# AWS Credentials
AWS_ACCESS_KEY_ID="AKIAEXAMPLEKEY12345678"
AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# AWS Parameters
REGION="us-west-2"
SERVICE="s3"
BUCKET="my-aws-bucket"
FILE_PATH="my_upload_file.txt"
KEY="uploads/$(basename "$FILE_PATH")"

# Dates
REQUEST_DATE=$(date -u "+%Y%m%dT%H%M%SZ")
DATE_STAMP=$(date -u "+%Y%m%d")

# Read file as payload hash
PAYLOAD_HASH=$(openssl dgst -sha256 < "$FILE_PATH" | sed 's/^.* //')

# Prepare Canonical Request
CANONICAL_URI="/$KEY"
CANONICAL_QUERY=""
CANONICAL_HEADERS="host:$BUCKET.s3.$REGION.amazonaws.com\nx-amz-content-sha256:$PAYLOAD_HASH\nx-amz-date:$REQUEST_DATE\n"
SIGNED_HEADERS="host;x-amz-content-sha256;x-amz-date"
CANONICAL_REQUEST="PUT\n$CANONICAL_URI\n$CANONICAL_QUERY\n$CANONICAL_HEADERS\n$SIGNED_HEADERS\n$PAYLOAD_HASH"

# Create String to Sign
ALGORITHM="AWS4-HMAC-SHA256"
CREDENTIAL_SCOPE="$DATE_STAMP/$REGION/$SERVICE/aws4_request"
HASHED_CANONICAL_REQUEST=$(echo -n "$CANONICAL_REQUEST" | openssl dgst -sha256 | sed 's/^.* //')
STRING_TO_SIGN="$ALGORITHM\n$REQUEST_DATE\n$CREDENTIAL_SCOPE\n$HASHED_CANONICAL_REQUEST"

# Generate Signature Key
kSecret="AWS4$AWS_SECRET_ACCESS_KEY"
kDate=$(echo -n "$DATE_STAMP" | openssl dgst -sha256 -mac HMAC -macopt key:$kSecret -binary)
kRegion=$(echo -n "$REGION" | openssl dgst -sha256 -mac HMAC -macopt key:- -binary <<< "$kDate")
kService=$(echo -n "$SERVICE" | openssl dgst -sha256 -mac HMAC -macopt key:- -binary <<< "$kRegion")
kSigning=$(echo -n "aws4_request" | openssl dgst -sha256 -mac HMAC -macopt key:- -binary <<< "$kService")

# Final Signature
SIGNATURE=$(echo -n "$STRING_TO_SIGN" | openssl dgst -sha256 -mac HMAC -macopt key:- <<< "$kSigning" | sed 's/^.* //')

# Authorization Header
AUTH_HEADER="$ALGORITHM Credential=$AWS_ACCESS_KEY_ID/$CREDENTIAL_SCOPE, SignedHeaders=$SIGNED_HEADERS, Signature=$SIGNATURE"

# Upload File with curl
curl -X PUT -T "$FILE_PATH" \
  -H "Host: $BUCKET.s3.$REGION.amazonaws.com" \
  -H "x-amz-date: $REQUEST_DATE" \
  -H "x-amz-content-sha256: $PAYLOAD_HASH" \
  -H "Authorization: $AUTH_HEADER" \
  "https://$BUCKET.s3.$REGION.amazonaws.com/$KEY"
