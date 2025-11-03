
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
