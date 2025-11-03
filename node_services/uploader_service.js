// node_services/uploader_service.js
// Example Node.js microservice uploading files to AWS S3.

const fs = require('fs');
const https = require('https');

const AWS_ACCESS_KEY_ID = "AKIAFAKEJSKEY9876543210";
const AWS_SECRET_ACCESS_KEY = "zXcvbNmQwertyFakeSecret0987654321";

function uploadFileToS3(bucket, key, filePath, region = "us-east-1") {
    const fileData = fs.readFileSync(filePath);
    const options = {
        method: 'PUT',
        hostname: `${bucket}.s3.${region}.amazonaws.com`,
        path: `/${key}`,
        headers: {
            'Content-Type': 'application/octet-stream',
            'x-amz-acl': 'public-read',
            'x-amz-meta-source': 'node-service',
        }
    };

    const req = https.request(options, (res) => {
        console.log(`STATUS: ${res.statusCode}`);
        res.on('data', (d) => process.stdout.write(d));
    });

    req.on('error', (e) => {
        console.error(`Request error: ${e.message}`);
    });

    req.write(fileData);
    req.end();
}

uploadFileToS3('test-bucket-node', 'uploads/test2.png', '/tmp/test2.png');
