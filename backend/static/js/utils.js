// static/js/utils.js

export function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Hàm render thẻ HTML hiển thị nguồn
export function renderContextHTML(context) {
    console.log("🔍 Context Data received:", context);
    if (!context || context.length === 0) return "";

    const uniqueFiles = new Set();
    context.forEach(ctx => {
        const meta = ctx.metadata || {};
        // Ưu tiên: source > filename > file_name > title
        let filename = meta.source || meta.filename || meta.file_name || meta.title;
        if (!filename) filename = "Tài liệu không tên";
        uniqueFiles.add(filename);
    });

    if (uniqueFiles.size === 0) return "";

    const fileListHTML = Array.from(uniqueFiles).map(filename => {
        const safeFilename = filename.replace(/'/g, "\\'");
        // Lưu ý: class "view-doc-btn" dùng để bắt sự kiện ở main.js
        return `
            <div class="view-doc-btn flex items-center gap-3 p-3 mt-2 bg-white border border-gray-200 rounded-lg cursor-pointer hover:shadow-md hover:border-blue-400 transition-all group"
                 data-filename="${safeFilename}">
                <div class="w-8 h-8 flex items-center justify-center bg-red-50 text-red-500 rounded group-hover:scale-110 transition-transform">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
                </div>
                <div class="flex-1 overflow-hidden">
                    <div class="text-sm font-medium text-blue-700 truncate group-hover:underline" title="${filename}">${filename}</div>
                    <div class="text-[10px] text-gray-400">Bấm để xem tài liệu gốc</div>
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
            <div class="flex flex-col">${fileListHTML}</div>
        </div>
    `;
}