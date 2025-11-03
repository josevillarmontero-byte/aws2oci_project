provider "aws" {
  region     = "us-west-2"
  access_key = "AWS_ACCESS_KEY_ID"
  secret_key = "AWS_SECRET_ACCESS_KEY"
}

resource "aws_s3_bucket_object" "object" {
  bucket = "mybucket"
  key    = "app.zip"
  source = "app.zip"
}
