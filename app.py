from flask import Flask, request, jsonify, send_file
import boto3, os, io

app = Flask(__name__)

BUCKET = "dealereye"
ENDPOINT = "https://s3.us-east-1.wasabisys.com"

s3 = boto3.client("s3", endpoint_url=ENDPOINT)

@app.route("/")
def home():
    return "✅ LotGuard connected to Wasabi bucket: " + BUCKET

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    s3.upload_fileobj(file, BUCKET, file.filename)
    return jsonify({"message": f"Uploaded {file.filename} to {BUCKET}"}), 200

@app.route("/list")
def list_files():
    response = s3.list_objects_v2(Bucket=BUCKET)
    files = [obj["Key"] for obj in response.get("Contents", [])]
    return jsonify(files)

@app.route("/download/<path:filename>")
def download(filename):
    obj = s3.get_object(Bucket=BUCKET, Key=filename)
    return send_file(io.BytesIO(obj["Body"].read()), download_name=filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
