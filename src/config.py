AWS_REGION = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-20250514-v1:0"
DATA_DIR = "data"
OUTPUT_DIR = "output"

# S3 integration — set S3_BUCKET to a bucket name to enable S3 as data source/destination.
S3_BUCKET = None
S3_PREFIX = "multi-agent"
S3_ENABLED = S3_BUCKET is not None
