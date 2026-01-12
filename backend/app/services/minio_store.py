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

def list_files_in_minio():
    """
    Lấy danh sách tất cả các file trong Bucket bằng Boto3
    """
    s3 = get_s3_client()
    
    try:
        # Boto3 dùng list_objects_v2 để liệt kê file
        # Lưu ý: Tôi dùng settings.MINIO_BUCKET cho đồng bộ với các hàm trên
        response = s3.list_objects_v2(Bucket=settings.MINIO_BUCKET)
        
        file_list = []
        
        # Kiểm tra xem bucket có file nào không (key 'Contents')
        if 'Contents' in response:
            for obj in response['Contents']:
                file_list.append({
                    "filename": obj['Key'],          # Boto3 trả về dict, không phải object
                    "size": obj['Size'],
                    "last_modified": obj['LastModified']
                })
            
            # Sắp xếp file mới nhất lên đầu
            file_list.sort(key=lambda x: x['last_modified'], reverse=True)
            
        return file_list

    except Exception as e:
        print(f"Lỗi lấy danh sách MinIO: {e}")
        return []

def get_file_stream(filename: str):
    """
    Lấy luồng dữ liệu file từ MinIO để trả về cho Client xem
    """
    s3 = get_s3_client()
    try:
        # Lấy object từ S3
        response = s3.get_object(Bucket=settings.MINIO_BUCKET, Key=filename)
        # Trả về Body (StreamingBody)
        return response['Body']
    except Exception as e:
        print(f"❌ Lỗi đọc file {filename}: {e}")
        return None        