// static/js/main.js
import { uploadPDF, openDocumentLibrary, viewDocument } from './documents.js';
import { sendMessage, newChat } from './chat.js';

let selectedFile = null;

document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 App Loaded - Events Initialized");

    // --- 1. SỰ KIỆN CHUNG ---
    const btnLibrary = document.getElementById('library-btn');
    const btnNewChat = document.getElementById('new-chat-btn');
    const btnSettings = document.getElementById('settings-btn');
    
    if (btnLibrary) btnLibrary.addEventListener('click', openDocumentLibrary);
    if (btnNewChat) btnNewChat.addEventListener('click', newChat);
    if (btnSettings) btnSettings.addEventListener('click', () => alert("Tính năng đang phát triển"));


// --- KHAI BÁO BIẾN ---
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');

    // --- HÀM XỬ LÝ GỬI TIN NHẮN (Dùng chung) ---
    const handleSendMessage = () => {
        // 1. Lấy nội dung và cắt khoảng trắng thừa
        const text = userInput.value.trim();
        
        // 2. Nếu rỗng thì không làm gì cả
        if (!text) return;

        // 3. Xóa ô nhập liệu ngay lập tức (để UI phản hồi nhanh)
        userInput.value = '';

        // 4. Gọi hàm gửi tin nhắn của bạn (hàm này gọi API xuống server)
        sendMessage(text);

        // 5. QUAN TRỌNG: Chỉnh lại chiều cao ô input về mặc định (nếu bạn dùng textarea)
        userInput.style.height = 'auto'; 

        // 6. QUAN TRỌNG: Focus lại vào ô nhập để gõ tiếp luôn
        userInput.focus();
    };

    // --- GẮN SỰ KIỆN ---
    if (sendBtn && userInput) {
        
        // 1. Sự kiện Click vào nút mũi tên
        sendBtn.addEventListener('click', (e) => {
            e.preventDefault(); // Chặn reload trang nếu nút nằm trong form
            handleSendMessage();
        });

        // 2. Sự kiện nhấn phím trên bàn phím
        userInput.addEventListener('keydown', (e) => {
            // Nếu nhấn Enter (mà không giữ Shift)
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // Chặn xuống dòng
                handleSendMessage(); // Gửi luôn
            }
        });
    }

    // --- 3. SỰ KIỆN UPLOAD FILE (QUAN TRỌNG) ---
    const fileInput = document.getElementById('pdf-file');
    const btnSelectFile = document.getElementById('btn-select-file');
    const btnConfirmUpload = document.getElementById('btn-confirm');
    const modalPreview = document.getElementById('preview-modal');

    // Nút "Select PDF"
    if (btnSelectFile && fileInput) {
        btnSelectFile.addEventListener('click', () => {
            // [FIX] Reset giá trị input để có thể chọn lại file cũ nếu muốn
            fileInput.value = ''; 
            fileInput.click();
        });
    }

    // Khi file được chọn từ máy tính
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                selectedFile = e.target.files[0];

                // Hiển thị Modal Preview
                const fileURL = URL.createObjectURL(selectedFile);
                const previewIframe = document.getElementById('pdf-preview');
                const modalTitle = document.querySelector("#preview-modal h2");
                
                if (previewIframe) previewIframe.src = fileURL;
                if (modalTitle) modalTitle.innerText = "📄 Review: " + selectedFile.name;
                
                if (btnConfirmUpload) btnConfirmUpload.style.display = 'block';
                modalPreview.classList.add('show');
                modalPreview.classList.remove('hidden');
                modalPreview.classList.add('flex');
            }
        });
    }

    // Nút "Upload & Xử lý" trong Modal
    if (btnConfirmUpload) {
        btnConfirmUpload.addEventListener('click', () => {
            if (!selectedFile) return;

            uploadPDF(selectedFile, () => {
                // Callback thành công:
                newChat(); // Reset chat
                
                // [FIX] Reset sạch sẽ trạng thái
                selectedFile = null;
                fileInput.value = '';
            });
        });
    }


    // --- 4. SỰ KIỆN ĐÓNG MODAL (Tất cả các nút đóng/hủy) ---
    const closeButtons = document.querySelectorAll('.modal-btn-close, .modal-btn-cancel');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Ẩn tất cả modal
            document.querySelectorAll('#preview-modal, #library-modal').forEach(m => {
                m.classList.remove('show');
                m.classList.add('hidden');
                m.classList.remove('flex');
            });

            // Reset iframe preview để tiết kiệm bộ nhớ
            const iframe = document.getElementById('pdf-preview');
            if(iframe) iframe.src = '';

            // Reset file đã chọn
            selectedFile = null;
            if (fileInput) fileInput.value = '';
        });
    });


    // --- 5. SỰ KIỆN XEM TÀI LIỆU (Event Delegation) ---
    // Bắt sự kiện click vào các nút file sinh ra động trong đoạn chat
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
        chatHistory.addEventListener('click', (e) => {
            const btn = e.target.closest('.view-doc-btn');
            if (btn) {
                const filename = btn.dataset.filename;
                if (filename) viewDocument(filename);
            }
        });
    }
});