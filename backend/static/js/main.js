/* static/js/main.js */

const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
let selectedFile = null;

// Hàm xử lý khi nhấn Enter
function handleEnter(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        sendMessage();
    }
}

// 1. Hàm Upload PDF (Đã tách ra dùng reader để stream progress nếu cần)
async function uploadPDF() {
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
        const res = await fetch("/documents/ingest", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            alert(`✅ Thành công! Đã thêm ${data.chunks_inserted} đoạn văn vào dữ liệu.`);
            document.getElementById('preview-modal').classList.remove('show');
            document.getElementById('pdf-preview').src = '';
            // Reset sau khi upload
            closeModal();
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

/// 2. Hàm Gửi Tin Nhắn (Cập nhật xử lý hiển thị)
async function sendMessage() {
    const question = userInput.value.trim();
    if (!question) return;

    // Hiển thị câu hỏi User
    appendMessage(question, 'user');
    userInput.value = '';
    sendBtn.disabled = true;

    // Tạo bong bóng chat "Thinking..."
    // Lưu ý: isLoading = true để nó có hiệu ứng nhấp nháy
    const loadingId = appendMessage("Thinking...", 'ai', true);
    const aiMessageDiv = document.getElementById(loadingId);

    try {
        const res = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                topk: 10,
                rerank_topn: 5
            })
        });

        if (!res.ok) throw new Error(`Server Error: ${res.status}`);

        // --- BẮT ĐẦU ĐỌC STREAM ---
        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let isFirstToken = true; // Cờ quan trọng để tránh xóa mất chữ Thinking quá sớm

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // Giữ lại phần thừa

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const json = JSON.parse(line);

                    // Xử lý: Câu trả lời (Answer)
                    if (json.type === "answer") {
                        // Chỉ khi nhận được chữ cái đầu tiên, ta mới xóa chữ "Thinking..."
                        if (isFirstToken) {
                            if (aiMessageDiv) {
                                aiMessageDiv.innerHTML = ""; // Xóa sạch "Thinking..."
                                aiMessageDiv.classList.remove("animate-pulse"); // Tắt hiệu ứng nháy
                            }
                            isFirstToken = false;
                        }

                        // Cộng dồn chữ vào
                        if (aiMessageDiv) {
                            // Xử lý xuống dòng cho đẹp
                            const text = (json.payload || "").replace(/\n/g, '<br>');
                            aiMessageDiv.innerHTML += text;
                        }
                        // Tự động cuộn xuống cuối
                        chatHistory.scrollTop = chatHistory.scrollHeight;
                    }

                    // Xử lý: Context (Nguồn)
                    else if (json.type === "context") {
                        console.log("Context received:", json.payload);
                        // Nếu muốn hiển thị nguồn ngay lập tức thì gọi hàm render ở đây
                        // (Hiện tại code appendMessage đã hỗ trợ render context nếu truyền vào lúc đầu,
                        //  nhưng vì streaming nên context đến trước, ta có thể lưu lại để render sau hoặc render ngay)
                    }

                    // Xử lý: Lỗi
                    else if (json.type === "error") {
                        if (aiMessageDiv) {
                            aiMessageDiv.innerHTML = `<span class="text-red-500 font-bold">❌ ${json.message}</span>`;
                        }
                        isFirstToken = false; // Đã xử lý xong, coi như không còn là first token
                    }

                } catch (e) {
                    console.error("JSON Parse Error:", e);
                }
            }
        }

        // Nếu kết thúc vòng lặp mà vẫn là FirstToken (tức là Server không trả về chữ nào cả)
        if (isFirstToken && aiMessageDiv) {
            aiMessageDiv.innerHTML = "<span class='text-gray-500 italic'>(Server đã phản hồi nhưng không có nội dung)</span>";
        }

    } catch (err) {
        console.error("Chat Error:", err);
        if (aiMessageDiv) {
            aiMessageDiv.innerHTML = `<span class="text-red-500 font-bold">❌ Lỗi kết nối: ${err.message}</span>`;
        }
    } finally {
        sendBtn.disabled = false;
        userInput.focus();
    }
}

async function loadDocuments() {
    try {
        const res = await fetch("/documents");
        const data = await res.json();

        // Giả sử bạn có thẻ <div id="file-list"></div>
        const listDiv = document.getElementById("file-list");
        listDiv.innerHTML = ""; // Clear cũ

        data.files.forEach(file => {
            const item = document.createElement("div");
            item.className = "file-item cursor-pointer p-2 hover:bg-gray-100 border-b";
            item.innerText = `📄 ${file.filename} (${formatBytes(file.size)})`;

            // Bắt sự kiện click để xem file
            item.onclick = () => previewPDF(file.filename);

            listDiv.appendChild(item);
        });
    } catch (err) {
        console.error("Lỗi tải danh sách:", err);
    }
}
function previewPDF(filename) {
    // Gọi vào API view chúng ta vừa viết
    // encodeURIComponent để xử lý tên file có dấu cách hoặc ký tự đặc biệt
    const url = `/documents/view/${encodeURIComponent(filename)}`;

    // Cách 1: Hiển thị trong thẻ Iframe (như cái Modal của bạn)
    const iframe = document.getElementById("pdf-preview");
    if (iframe) {
        iframe.src = url;
        // Mở modal lên nếu đang ẩn
        document.getElementById('preview-modal').classList.add('show');
    }

    // Cách 2: Mở tab mới (nếu muốn)
    // window.open(url, '_blank');
}
// Hàm vẽ tin nhắn (Có sử dụng class Tailwind)
function appendMessage(text, role, isLoading = false, context = []) {
    const div = document.createElement('div');
    const id = 'msg-' + Date.now() + Math.random();
    div.id = id;

    if (role === 'user') {
        div.className = 'message-user bg-gray-100 text-gray-900 p-3 rounded-lg max-w-3xl mb-2 self-end text-right ml-auto';
    } else {
        div.className = 'message-ai bg-gray-100 text-gray-800 p-3 rounded-lg max-w-3xl mb-2 self-start border border-gray-200 mr-auto';
    }

    const safeText = text ? text.replace(/\n/g, '<br>') : "";
    let htmlContent = `<p>${safeText}</p>`;

    // Render Context (Giữ nguyên logic của bạn)
    if (context && context.length > 0) {
        htmlContent += `
            <div class="mt-3 border-t border-gray-200 pt-3 text-left">
                <details class="group">
                    <summary class="list-none cursor-pointer flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 font-medium transition-colors">
                        <span class="transform group-open:rotate-90 transition-transform duration-200">▶</span>
                        <span>📚 Nguồn tham khảo (${context.length} đoạn)</span>
                    </summary>
                    <div class="mt-3 grid gap-3 max-h-80 overflow-y-auto pr-2 custom-scrollbar">
                        ${context.map(ctx => `
                            <div class="bg-gray-50 p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-sm transition-all text-xs text-gray-700 relative group/item">
                                <div class="flex justify-between items-center mb-2 border-b border-gray-100 pb-2">
                                    <span class="font-bold text-blue-800 bg-blue-100 px-2 py-0.5 rounded">#${ctx.chunk_id}</span>
                                    <div class="flex gap-2 items-center">
                                        <span class="text-[10px] uppercase tracking-wider text-gray-400 font-bold border border-gray-200 px-1 rounded">${ctx.level || 'Unknown'}</span>
                                        <span class="${ctx.rerank_score > 2 ? 'text-green-600 bg-green-50' : 'text-orange-500 bg-orange-50'} font-mono font-bold px-1 rounded">
                                            ${ctx.rerank_score.toFixed(2)}
                                        </span>
                                    </div>
                                </div>
                                <div class="relative">
                                    <div class="line-clamp-3 group-hover/item:line-clamp-none transition-all duration-300 text-justify leading-relaxed opacity-80 group-hover/item:opacity-100">
                                        ${ctx.text}
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </details>
            </div>
        `;
    }

    if (isLoading) {
        div.innerHTML = `<span class="animate-pulse">⏳ ${safeText}</span>`;
    } else {
        div.innerHTML = htmlContent;
    }

    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    return id;
}

// Helper: Xử lý file
function handleFileSelect(input) {
    if (input.files && input.files[0]) {
        selectedFile = input.files[0];
        document.getElementById('file-name').textContent = selectedFile.name;
        document.getElementById('file-size').textContent = formatBytes(selectedFile.size);
        const fileURL = URL.createObjectURL(selectedFile);
        document.getElementById('pdf-preview').src = fileURL;
        document.getElementById('preview-modal').classList.add('show');
    }
}

function closeModal() {
    document.getElementById('preview-modal').classList.remove('show');
    document.getElementById('pdf-file').value = '';
    document.getElementById('pdf-preview').src = '';
    selectedFile = null;
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function newChat() {
    chatHistory.innerHTML = `
        <div class="message message-ai">
            <div class="message-content">
                👋 Xin chào! Hãy upload tài liệu PDF và đặt câu hỏi cho tôi.
            </div>
        </div>
    `;
}

function openSettings() {
    alert('Settings functionality is not implemented yet.');
}
/* --- LOGIC QUẢN LÝ TÀI LIỆU (MỚI) --- */

// 1. Mở Modal và tải danh sách
async function openDocumentLibrary() {
    const modal = document.getElementById('library-modal');
    const listContainer = document.getElementById('document-list-container');

    // Hiển thị modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    try {
        const res = await fetch("/documents");
        const data = await res.json();

        console.log("Dữ liệu từ API /documents:", data); // Debug: Xem nó in ra cái gì

        listContainer.innerHTML = ""; // Xóa loading cũ

        // --- SỬA LỖI Ở ĐÂY: Tự động phát hiện cấu trúc dữ liệu ---
        let files = [];
        if (Array.isArray(data)) {
            // Trường hợp 1: API trả về trực tiếp danh sách [file1, file2...]
            files = data;
        } else if (data.files && Array.isArray(data.files)) {
            // Trường hợp 2: API trả về object { files: [...], count: 10 }
            files = data.files;
        } else {
            console.warn("API không trả về mảng file hợp lệ.", data);
            listContainer.innerHTML = `<div class="text-center text-red-500 py-4">Dữ liệu không hợp lệ.</div>`;
            return;
        }
        // ---------------------------------------------------------

        // ... (phần trên giữ nguyên)
        if (files.length === 0) {
            listContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full py-10 opacity-50">
            <span class="text-4xl mb-2">📭</span>
            <p class="text-gray-600">Chưa có tài liệu nào được upload.</p>
        </div>`;
            return;
        }

        files.forEach(file => {
            const div = document.createElement("div");
            // SỬA CLASS TẠI ĐÂY: Dùng bg-white, shadow-sm, rounded-xl để tạo hình cái thẻ
            div.className = "flex items-center justify-between p-4 mb-3 bg-white hover:shadow-md border border-gray-100 hover:border-blue-200 transition-all rounded-xl group cursor-pointer";

            const dateStr = file.last_modified ? new Date(file.last_modified).toLocaleDateString() : "N/A";

            div.innerHTML = `
        <div class="flex items-center gap-4 overflow-hidden">
            <div class="w-12 h-12 rounded-xl bg-red-50 text-red-500 flex items-center justify-center shadow-sm shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
            </div>
            <div class="flex flex-col overflow-hidden">
                <span class="font-semibold text-gray-800 truncate text-[15px] group-hover:text-blue-700 transition-colors" title="${file.filename}">
                    ${file.filename}
                </span>
                <div class="flex items-center gap-2 text-xs text-gray-400 mt-1">
                    <span class="bg-gray-100 px-2 py-0.5 rounded-md">${formatBytes(file.size)}</span>
                    <span>•</span>
                    <span>${dateStr}</span>
                </div>
            </div>
        </div>
        <button class="opacity-0 group-hover:opacity-100 scale-90 group-hover:scale-100 px-4 py-2 bg-blue-100 text-blue-700 text-sm font-medium rounded-lg hover:bg-blue-200 transition-all duration-300">
            Xem file
        </button>
    `;

            div.onclick = () => viewDocument(file.filename);
            listContainer.appendChild(div);
        });
        // ... (phần catch lỗi giữ nguyên)

    } catch (err) {
        console.error(err);
        listContainer.innerHTML = `<div class="text-red-500 text-center">❌ Lỗi tải danh sách: ${err.message}</div>`;
    }
}

// 2. Đóng Modal Library
function closeLibraryModal() {
    const modal = document.getElementById('library-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

// 3. Xem File (Sử dụng lại Modal Preview có sẵn)
function viewDocument(filename) {
    // Ẩn modal danh sách đi để hiện modal preview
    closeLibraryModal();

    // Thay đổi tiêu đề modal preview
    const modalTitle = document.querySelector("#preview-modal h2");
    if (modalTitle) modalTitle.innerText = "📄 Đang xem: " + filename;

    // Ẩn nút "Confirm & Ingest" vì đây là file đã có rồi, không cần upload lại
    const btnConfirm = document.getElementById("btn-confirm");
    if (btnConfirm) btnConfirm.style.display = "none";

    // Set src cho iframe gọi vào API Stream
    const iframe = document.getElementById('pdf-preview');
    // encodeURIComponent để xử lý tên file có dấu cách
    iframe.src = `/documents/view/${encodeURIComponent(filename)}`;

    // Hiện modal preview
    document.getElementById('preview-modal').classList.add('show');

    // Sửa lại nút Cancel thành "Quay lại" để mở lại danh sách
    const btnCancel = document.querySelector(".modal-btn-cancel");
    btnCancel.onclick = () => {
        closeModal(); // Đóng preview
        openDocumentLibrary(); // Mở lại danh sách

        // Reset lại giao diện modal (cho chức năng upload bình thường)
        setTimeout(() => {
            if (modalTitle) modalTitle.innerText = "📄 Review File Before Upload";
            if (btnConfirm) btnConfirm.style.display = "block";
            btnCancel.onclick = closeModal; // Trả lại hàm đóng bình thường
        }, 500);
    };
}