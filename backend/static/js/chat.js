// static/js/chat.js
import { renderContextHTML } from './utils.js';

let currentSessionId = localStorage.getItem("rag_session_id");

export function getSessionId() { return currentSessionId; }

export function newChat() {
    localStorage.removeItem("rag_session_id");
    currentSessionId = null;
    const chatHistory = document.getElementById('chat-history');
    chatHistory.innerHTML = `
        <div class="message-ai bg-gray-100 text-gray-800 p-3 rounded-lg max-w-3xl mb-2 self-start border border-gray-200">
            👋 Xin chào! Phiên chat mới đã được tạo.
        </div>`;
    console.log("🧹 New Chat Created");
}

function updateMessageBadge(msgId, mode) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;
    let badge = msgDiv.querySelector(".mode-badge");
    if (!badge) {
        badge = document.createElement("div");
        badge.className = "mode-badge text-[10px] font-bold px-2 py-0.5 rounded-full mb-1 inline-block border";
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

export function appendMessage(text, role, isLoading = false, context = []) {
    const chatHistory = document.getElementById('chat-history');
    const div = document.createElement('div');
    const id = 'msg-' + Date.now() + Math.random();
    div.id = id;
    
    div.className = role === 'user' 
        ? 'bg-gray-100 text-gray-900 p-3 rounded-lg max-w-3xl mb-2 self-end text-right ml-auto'
        : 'bg-gray-100 text-gray-800 p-3 rounded-lg max-w-3xl mb-2 self-start border border-gray-200 mr-auto';

    let htmlContent = `<p>${text ? text.replace(/\n/g, '<br>') : ""}</p>`;
    if (context.length > 0) htmlContent += renderContextHTML(context);

    div.innerHTML = isLoading ? `<p class="animate-pulse">⏳ ${text}</p>` : htmlContent;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return id;
}

export async function sendMessage(question) {
    if (!question) return;
    appendMessage(question, 'user');
    const loadingId = appendMessage("Thinking...", 'ai', true);
    
    const aiMessageDiv = document.getElementById(loadingId);
    const aiContentDiv = aiMessageDiv.querySelector("p");

    try {
        const res = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                question: question, 
                session_id: currentSessionId, 
                topk: 10, rerank_topn: 5 
            })
        });

        if (!res.ok) throw new Error(res.status);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let isFirstToken = true;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const lines = decoder.decode(value, { stream: true }).split("\n");
            
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const json = JSON.parse(line);
                    
                    if (json.type === "meta_info") {
                        if (json.session_id) {
                            currentSessionId = json.session_id;
                            localStorage.setItem("rag_session_id", currentSessionId);
                        }
                        if (json.mode) updateMessageBadge(loadingId, json.mode);
                    } 
                    else if (json.type === "answer") {
                        if (isFirstToken) {
                            aiContentDiv.innerHTML = "";
                            aiContentDiv.classList.remove("animate-pulse");
                            isFirstToken = false;
                        }
                        aiContentDiv.innerHTML += (json.payload || "").replace(/\n/g, '<br>');
                    }
                    else if (json.type === "context") {
                        if (json.payload && json.payload.length > 0) {
                            aiMessageDiv.insertAdjacentHTML('beforeend', renderContextHTML(json.payload));
                        }
                    }
                } catch (e) { console.error(e); }
            }
        }
    } catch (err) {
        aiContentDiv.innerHTML = `<span class="text-red-500">❌ Lỗi: ${err.message}</span>`;
    }
}