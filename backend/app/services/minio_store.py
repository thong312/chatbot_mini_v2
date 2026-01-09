import boto3
from botocore.client import Config
from app.core.settings import settings

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )

def ensure_bucket():
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.MINIO_BUCKET)
    except:
        # Nếu bucket chưa có thì tạo mới
        s3.create_bucket(Bucket=settings.MINIO_BUCKET)

def upload_pdf_to_minio(file_bytes: bytes, file_name: str, content_type: str = "application/pdf") -> str:
    """
    Upload file lên MinIO và trả về đường dẫn (Key)
    """
    s3 = get_s3_client()
    ensure_bucket()
    
    # Upload
    s3.put_object(
        Bucket=settings.MINIO_BUCKET,
        Key=file_name,
        Body=file_bytes,
        ContentType=content_type
    )
    
    return file_name