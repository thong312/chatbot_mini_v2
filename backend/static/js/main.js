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


    // --- 2. SỰ KIỆN CHAT ---
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');

    if (sendBtn && userInput) {
        sendBtn.addEventListener('click', () => {
            const text = userInput.value.trim();
            if (!text) return;
            userInput.value = '';
            sendMessage(text);
        });

        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendBtn.click();
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