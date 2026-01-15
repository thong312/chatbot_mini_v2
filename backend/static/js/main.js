/* static/js/main.js */

const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
let selectedFile = null;

// --- [MỚI] 1. KHỞI TẠO SESSION ID TỪ LOCALSTORAGE ---
// Nếu user F5 lại trang, biến này sẽ lấy lại ID cũ để chat tiếp
let currentSessionId = localStorage.getItem("rag_session_id");
console.log("🔹 Current Session ID:", currentSessionId);


// Hàm xử lý khi nhấn Enter
function handleEnter(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        sendMessage();
    }
}

// 1. Hàm Upload PDF (Giữ nguyên logic của bạn)
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
            closeModal();
            // [MỚI] Sau khi upload, nên clear session cũ để AI cập nhật kiến thức mới tốt hơn
            newChat();
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
let currentMsgMode = "RAG";
// Biến lưu mode hiện tại của câu trả lời đang stream
async function sendMessage() {
    const question = userInput.value.trim();
    if (!question) return;

    // Hiển thị câu hỏi User
    appendMessage(question, 'user');
    userInput.value = '';
    sendBtn.disabled = true;

    // Tạo bong bóng chat "Thinking..."
    // loadingId chính là ID của cái thẻ div tin nhắn đang chờ
    const loadingId = appendMessage("Thinking...", 'ai', true);

    const aiMessageDiv = document.getElementById(loadingId);
    const aiContentDiv = aiMessageDiv.querySelector("p") || aiMessageDiv;

    try {
        const res = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                session_id: currentSessionId,
                topk: 10,
                rerank_topn: 5
            })
        });

        if (!res.ok) throw new Error(`Server Error: ${res.status}`);

        // --- BẮT ĐẦU ĐỌC STREAM ---
        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let isFirstToken = true;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const json = JSON.parse(line);

                    // --- [SỬA ĐOẠN NÀY] XỬ LÝ META INFO (SESSION + MODE) ---
                    // Backend trả về type là "meta_info", không phải "session_info" nữa
                    if (json.type === "meta_info") {
                        console.log("ℹ️ Meta Info:", json);

                        // 1. Cập nhật Session ID
                        if (json.session_id) {
                            currentSessionId = json.session_id;
                            localStorage.setItem("rag_session_id", currentSessionId);
                        }

                        // 2. Cập nhật Badge (General hay RAG)
                        if (json.mode) {
                            updateMessageBadge(loadingId, json.mode);
                        }
                    }

                    // Fallback: Nếu backend cũ vẫn trả về session_info
                    else if (json.type === "session_info") {
                        currentSessionId = json.payload;
                        localStorage.setItem("rag_session_id", currentSessionId);
                    }

                    // Xử lý: Câu trả lời (Answer)
                    else if (json.type === "answer") {
                        if (isFirstToken) {
                            if (aiMessageDiv) {
                                aiContentDiv.innerHTML = ""; // Xóa chữ Thinking
                                aiContentDiv.classList.remove("animate-pulse");
                            }
                            isFirstToken = false;
                        }

                        if (aiMessageDiv) {
                            const text = (json.payload || "").replace(/\n/g, '<br>');
                            aiContentDiv.innerHTML += text;
                        }
                        chatHistory.scrollTop = chatHistory.scrollHeight;
                    }

                    // Xử lý: Context (Nguồn)
                    else if (json.type === "context") {
                        if (json.payload && json.payload.length > 0) {
                            const contextHTML = renderContextHTML(json.payload);
                            aiMessageDiv.insertAdjacentHTML('beforeend', contextHTML);
                        }
                    }

                    // Xử lý: Lỗi
                    else if (json.type === "error") {
                        if (aiMessageDiv) {
                            aiContentDiv.innerHTML = `<span class="text-red-500 font-bold">❌ ${json.message}</span>`;
                        }
                        isFirstToken = false;
                    }

                } catch (e) {
                    console.error("JSON Parse Error:", e);
                }
            }
        }

        if (isFirstToken && aiMessageDiv) {
            aiContentDiv.innerHTML = "<span class='text-gray-500 italic'>(Server đã phản hồi nhưng không có nội dung)</span>";
        }

    } catch (err) {
        console.error("Chat Error:", err);
        if (aiMessageDiv) {
            aiContentDiv.innerHTML = `<span class="text-red-500 font-bold">❌ Lỗi kết nối: ${err.message}</span>`;
        }
    } finally {
        sendBtn.disabled = false;
        userInput.focus();
    }
}
// Kiểm tra mode
function updateMessageBadge(msgId, mode) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;

    // Kiểm tra xem đã có badge chưa, chưa có thì tạo
    let badge = msgDiv.querySelector(".mode-badge");
    if (!badge) {
        badge = document.createElement("div");
        badge.className = "mode-badge text-[10px] font-bold px-2 py-0.5 rounded-full mb-1 inline-block border";
        // Chèn badge vào đầu tin nhắn
        msgDiv.insertBefore(badge, msgDiv.firstChild);
    }

    if (mode === "GENERAL") {
        badge.innerText = "🌐 General Knowledge";
        badge.className += " bg-purple-100 text-purple-700 border-purple-200";
    } else {
        badge.innerText = "📄 Document Context";
        badge.className += " bg-blue-100 text-blue-700 border-blue-200";
    }
}


// --- [FIX] HIỂN THỊ NGUỒN (DEBUG & FALLBACK) ---
function renderContextHTML(context) {
    // 1. Debug: In ra console để xem Backend trả về cái gì
    console.log("🔍 Context Data received:", context);

    if (!context || context.length === 0) return "";

    const uniqueFiles = new Set();

    context.forEach(ctx => {
        // 2. Lấy metadata an toàn
        const meta = ctx.metadata || {};

        // 3. Thử tìm tên file ở nhiều trường khác nhau (đề phòng backend lưu lệch key)
        // Ưu tiên: source > filename > file_name > title
        let filename = meta.source || meta.filename || meta.file_name || meta.title;

        // Nếu vẫn không có tên, thử lấy ID hoặc báo Unknown
        if (!filename) {
            console.warn("⚠️ Chunk này không có tên file trong metadata:", ctx);
            filename = "Tài liệu không tên";
        }

        uniqueFiles.add(filename);
    });

    if (uniqueFiles.size === 0) return "";

    // 4. Render HTML
    const fileListHTML = Array.from(uniqueFiles).map(filename => {
        // Xử lý tên file để tránh lỗi khi truyền vào hàm onclick (ví dụ có dấu nháy đơn)
        const safeFilename = filename.replace(/'/g, "\\'");

        return `
            <div 
                class="flex items-center gap-3 p-3 mt-2 bg-white border border-gray-200 rounded-lg cursor-pointer hover:shadow-md hover:border-blue-400 transition-all group"
                onclick="viewDocument('${safeFilename}')"
            >
                <div class="w-8 h-8 flex items-center justify-center bg-red-50 text-red-500 rounded group-hover:scale-110 transition-transform">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                </div>

                <div class="flex-1 overflow-hidden">
                    <div class="text-sm font-medium text-blue-700 truncate group-hover:underline" title="${filename}">
                        ${filename}
                    </div>
                    <div class="text-[10px] text-gray-400">Bấm để xem tài liệu gốc</div>
                </div>

                <div class="text-gray-300 group-hover:text-blue-500">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="mt-4 pt-3 border-t border-gray-100">
            <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">📚 Nguồn tham khảo</span>
                <span class="bg-gray-100 text-gray-600 text-[10px] font-bold px-1.5 py-0.5 rounded-full">${uniqueFiles.size}</span>
            </div>
            <div class="flex flex-col">
                ${fileListHTML}
            </div>
        </div>
    `;
}


// 3. Hàm Appned Message (Đã tối ưu để hỗ trợ tách context)
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

    // Lưu nội dung vào thẻ <p> để lát dễ thay đổi mà không mất context
    let htmlContent = `<p>${safeText}</p>`;

    // Nếu có context ngay từ đầu (ít khi xảy ra với streaming, nhưng cứ để)
    if (context && context.length > 0) {
        htmlContent += renderContextHTML(context);
    }

    if (isLoading) {
        div.innerHTML = `<p class="animate-pulse">⏳ ${safeText}</p>`;
    } else {
        div.innerHTML = htmlContent;
    }

    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    return id;
}

// 4. [MỚI] Hàm New Chat - Xóa Session cũ
function newChat() {
    // Xóa LocalStorage
    localStorage.removeItem("rag_session_id");
    currentSessionId = null;

    // Reset giao diện
    chatHistory.innerHTML = `
        <div class="message message-ai bg-gray-100 text-gray-800 p-3 rounded-lg max-w-3xl mb-2 self-start border border-gray-200 mr-auto">
            <div class="message-content">
                👋 Xin chào! Phiên chat mới đã được tạo. Hãy hỏi tôi gì đó đi!
            </div>
        </div>
    `;
    console.log("🧹 New Chat Created - Session Cleared");
}


/* --- CÁC HÀM XỬ LÝ DOCUMENT (GIỮ NGUYÊN CODE CỦA BẠN) --- */

async function openDocumentLibrary() {
    const modal = document.getElementById('library-modal');
    const listContainer = document.getElementById('document-list-container');
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    try {
        const res = await fetch("/documents");
        const data = await res.json();
        listContainer.innerHTML = "";

        let files = [];
        if (Array.isArray(data)) files = data;
        else if (data.files && Array.isArray(data.files)) files = data.files;

        if (files.length === 0) {
            listContainer.innerHTML = `<div class="flex flex-col items-center justify-center h-full py-10 opacity-50"><p class="text-gray-600">Chưa có tài liệu nào.</p></div>`;
            return;
        }

        files.forEach(file => {
            const div = document.createElement("div");
            div.className = "flex items-center justify-between p-4 mb-3 bg-white hover:shadow-md border border-gray-100 hover:border-blue-200 transition-all rounded-xl group cursor-pointer";
            const dateStr = file.last_modified ? new Date(file.last_modified).toLocaleDateString() : "N/A";

            div.innerHTML = `
                <div class="flex items-center gap-4 overflow-hidden">
                    <div class="w-12 h-12 rounded-xl bg-red-50 text-red-500 flex items-center justify-center shadow-sm shrink-0">
                         <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
                    </div>
                    <div class="flex flex-col overflow-hidden">
                        <span class="font-semibold text-gray-800 truncate text-[15px] group-hover:text-blue-700 transition-colors" title="${file.filename}">${file.filename}</span>
                        <div class="flex items-center gap-2 text-xs text-gray-400 mt-1">
                            <span class="bg-gray-100 px-2 py-0.5 rounded-md">${formatBytes(file.size)}</span><span>•</span><span>${dateStr}</span>
                        </div>
                    </div>
                </div>
                <button class="opacity-0 group-hover:opacity-100 scale-90 group-hover:scale-100 px-4 py-2 bg-blue-100 text-blue-700 text-sm font-medium rounded-lg hover:bg-blue-200 transition-all duration-300">Xem file</button>
            `;
            div.onclick = () => viewDocument(file.filename);
            listContainer.appendChild(div);
        });
    } catch (err) {
        console.error(err);
        listContainer.innerHTML = `<div class="text-red-500 text-center">❌ Lỗi tải danh sách: ${err.message}</div>`;
    }
}

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

function closeLibraryModal() {
    const modal = document.getElementById('library-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

function viewDocument(filename) {
    closeLibraryModal();
    const modalTitle = document.querySelector("#preview-modal h2");
    if (modalTitle) modalTitle.innerText = "📄 Đang xem: " + filename;
    const btnConfirm = document.getElementById("btn-confirm");
    if (btnConfirm) btnConfirm.style.display = "none";
    const iframe = document.getElementById('pdf-preview');
    iframe.src = `/documents/view/${encodeURIComponent(filename)}`;
    document.getElementById('preview-modal').classList.add('show');
    const btnCancel = document.querySelector(".modal-btn-cancel");
    btnCancel.onclick = () => {
        closeModal();
        openDocumentLibrary();
        setTimeout(() => {
            if (modalTitle) modalTitle.innerText = "📄 Review File Before Upload";
            if (btnConfirm) btnConfirm.style.display = "block";
            btnCancel.onclick = closeModal;
        }, 500);
    };
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function openSettings() {
    alert('Settings functionality is not implemented yet.');
}