// static/js/documents.js
import { formatBytes } from './utils.js';

// Quản lý Modal Xem File
export function viewDocument(filename) {
    // Đóng library modal trước nếu đang mở
    document.getElementById('library-modal').classList.add('hidden');
    document.getElementById('library-modal').classList.remove('flex');

    const modalTitle = document.querySelector("#preview-modal h2");
    if (modalTitle) modalTitle.innerText = "📄 Đang xem: " + filename;
    
    // Ẩn nút confirm upload nếu đang xem từ thư viện
    const btnConfirm = document.getElementById("btn-confirm");
    if (btnConfirm) btnConfirm.style.display = "none";

    const iframe = document.getElementById('pdf-preview');
    iframe.src = `/documents/view/${encodeURIComponent(filename)}`;
    
    document.getElementById('preview-modal').classList.add('show');
}

// Quản lý Upload
export async function uploadPDF(selectedFile, callbackSuccess) {
    if (!selectedFile) return alert("Vui lòng chọn file PDF!");

    const formData = new FormData();
    formData.append("file", selectedFile);

    const btn = document.getElementById("btn-confirm");
    let originalText = "Upload";
    if (btn) {
        originalText = btn.innerText;
        btn.innerText = "Processing...";
        btn.disabled = true;
    }

    try {
        const res = await fetch("/documents/ingest", { method: "POST", body: formData });
        const data = await res.json();

        if (res.ok) {
            alert(`✅ Thành công! Đã thêm ${data.chunks_inserted} đoạn văn.`);
            document.getElementById('preview-modal').classList.remove('show');
            document.getElementById('pdf-preview').src = '';
            
            if (callbackSuccess) callbackSuccess(); // Gọi hàm reset chat
        } else {
            alert(`❌ Lỗi server: ${JSON.stringify(data)}`);
        }
    } catch (err) {
        console.error(err);
        alert("Lỗi kết nối server!");
    } finally {
        if (btn) {
            btn.innerText = originalText;
            btn.disabled = false;
        }
    }
}

// Quản lý Thư viện
export async function openDocumentLibrary() {
    const modal = document.getElementById('library-modal');
    const listContainer = document.getElementById('document-list-container');
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    try {
        const res = await fetch("/documents");
        const data = await res.json();
        listContainer.innerHTML = "";

        let files = Array.isArray(data) ? data : (data.files || []);

        if (files.length === 0) {
            listContainer.innerHTML = `<div class="py-10 text-center opacity-50">Chưa có tài liệu nào.</div>`;
            return;
        }

        files.forEach(file => {
            const div = document.createElement("div");
            div.className = "flex items-center justify-between p-4 mb-3 bg-white hover:shadow-md border border-gray-100 rounded-xl cursor-pointer group";
            div.innerHTML = `
                <div class="flex items-center gap-4">
                    <div class="w-10 h-10 rounded bg-red-50 text-red-500 flex items-center justify-center">PDF</div>
                    <div>
                        <div class="font-semibold text-gray-800">${file.filename}</div>
                        <div class="text-xs text-gray-400">${formatBytes(file.size)}</div>
                    </div>
                </div>
            `;
            // Gán sự kiện click
            div.onclick = () => viewDocument(file.filename);
            listContainer.appendChild(div);
        });
    } catch (err) {
        listContainer.innerHTML = `<div class="text-red-500">❌ Lỗi: ${err.message}</div>`;
    }
}