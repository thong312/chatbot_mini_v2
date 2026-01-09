from pymilvus import connections, utility

# 1. Cấu hình kết nối (Mặc định của Milvus Docker)
MILVUS_HOST = "127.0.0.1"
MILVUS_PORT = "19530"

# Tên collection bạn muốn xóa (Kiểm tra trong file .env của bạn)
# Nếu bạn không nhớ, script này sẽ tự liệt kê ra để bạn chọn
TARGET_COLLECTION = "pdf_rag" 

def main():
    print(f"🔌 Đang kết nối đến Milvus tại {MILVUS_HOST}:{MILVUS_PORT}...")
    try:
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
        print("✅ Kết nối thành công!")
    except Exception as e:
        print(f"❌ Không thể kết nối Milvus: {e}")
        return

    # Liệt kê tất cả collection đang có
    collections = utility.list_collections()
    print(f"\n📂 Các Collection hiện có trong DB: {collections}")

    if not collections:
        print("⚠️ Database trống rỗng, không có gì để xóa.")
        return

    # Xác định collection cần xóa
    col_name = TARGET_COLLECTION
    if col_name not in collections:
        # Nếu tên mặc định không đúng, lấy cái đầu tiên tìm thấy
        col_name = collections[0]
    
    # Hỏi xác nhận lần cuối
    confirm = input(f"\n🔥 BẠN CÓ CHẮC MUỐN XÓA COLLECTION '{col_name}' KHÔNG? (y/n): ")
    
    if confirm.lower() == 'y':
        utility.drop_collection(col_name)
        print(f"✅ Đã xóa vĩnh viễn collection: '{col_name}'")
        print("👉 Bây giờ bạn có thể Restart Server để code tự tạo lại Schema mới.")
    else:
        print("❌ Đã hủy thao tác.")

if __name__ == "__main__":
    main()