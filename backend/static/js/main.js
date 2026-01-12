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
    alert('Settings functionality would go here');
}