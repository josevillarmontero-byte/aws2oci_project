provider "oci" {
        tenancy_ocid     = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
        user_ocid        = "ocid1.user.oc1..aaaaaaaaexampleuser"
        fingerprint      = "20:3b:97:13:example:fingerprint"
        private_key_path = "~/.oci/oci_api_key.pem"
        region           = "eu-frankfurt-1"
        }

resource "aws_s3_bucket_object" "object" {
  bucket = "mybucket"
  key    = "app.zip"
  source = "app.zip"
}
