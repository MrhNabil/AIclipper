/**
 * AIClipper Reusable UI Components
 * Toast notifications, modals, progress bars, cards, dropzones, etc.
 */

// ─────────────────────────────────────────────
// Toast Notification System
// ─────────────────────────────────────────────

const Toast = {
    _container: null,

    _getContainer() {
        if (!this._container) {
            this._container = document.getElementById('toastContainer');
        }
        return this._container;
    },

    show(message, type = 'info', duration = 4000) {
        const container = this._getContainer();
        const icons = { info: 'ℹ️', success: '✅', warning: '⚠️', error: '❌' };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
        `;

        container.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => toast.classList.add('toast-show'));

        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('toast-show');
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    },

    info(msg, duration)    { this.show(msg, 'info', duration); },
    success(msg, duration) { this.show(msg, 'success', duration); },
    warning(msg, duration) { this.show(msg, 'warning', duration); },
    error(msg, duration)   { this.show(msg, 'error', duration); },
};


// ─────────────────────────────────────────────
// Modal Dialog
// ─────────────────────────────────────────────

const Modal = {
    _overlay: null,
    _title: null,
    _body: null,
    _footer: null,

    _init() {
        this._overlay = document.getElementById('modalOverlay');
        this._title = document.getElementById('modalTitle');
        this._body = document.getElementById('modalBody');
        this._footer = document.getElementById('modalFooter');

        document.getElementById('modalClose').addEventListener('click', () => this.close());
        this._overlay.addEventListener('click', (e) => {
            if (e.target === this._overlay) this.close();
        });
    },

    open(title, bodyHtml, footerHtml = '') {
        if (!this._overlay) this._init();
        this._title.textContent = title;
        this._body.innerHTML = bodyHtml;
        this._footer.innerHTML = footerHtml;
        this._overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    },

    close() {
        if (this._overlay) {
            this._overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    },

    confirm(title, message, onConfirm) {
        this.open(
            title,
            `<p style="color: var(--text-secondary); line-height: 1.6;">${message}</p>`,
            `<button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
             <button class="btn btn-danger" id="modalConfirmBtn">Confirm</button>`
        );
        document.getElementById('modalConfirmBtn').addEventListener('click', () => {
            this.close();
            onConfirm();
        });
    },
};


// ─────────────────────────────────────────────
// Component Renderers
// ─────────────────────────────────────────────

function renderStatsCard(icon, label, value, color = 'var(--accent-primary)') {
    return `
        <div class="stats-card">
            <div class="stats-icon" style="background: ${color}20; color: ${color};">${icon}</div>
            <div class="stats-info">
                <span class="stats-value">${value}</span>
                <span class="stats-label">${label}</span>
            </div>
        </div>
    `;
}

function renderProgressBar(percent, label = '', animated = false) {
    const clampedPct = Math.max(0, Math.min(100, percent));
    return `
        <div class="progress-container">
            ${label ? `<div class="progress-label"><span>${label}</span><span>${clampedPct}%</span></div>` : ''}
            <div class="progress-bar">
                <div class="progress-fill ${animated ? 'progress-animated' : ''}" style="width: ${clampedPct}%"></div>
            </div>
        </div>
    `;
}

function renderStatusBadge(status) {
    const statusMap = {
        pending:    { class: 'badge-warning',  icon: '⏳' },
        processing: { class: 'badge-info',     icon: '⚙️' },
        completed:  { class: 'badge-success',  icon: '✅' },
        failed:     { class: 'badge-danger',   icon: '❌' },
        published:  { class: 'badge-success',  icon: '🚀' },
        uploading:  { class: 'badge-info',     icon: '⬆️' },
        scheduled:  { class: 'badge-warning',  icon: '📅' },
        generating: { class: 'badge-info',     icon: '🔄' },
    };
    const info = statusMap[status] || { class: 'badge-default', icon: '❓' };
    return `<span class="badge ${info.class}">${info.icon} ${status}</span>`;
}

function renderClipCard(clip) {
    const thumbSrc = clip.thumbnails && clip.thumbnails.length > 0
        ? `/thumbnails/${clip.thumbnails[0].filepath.split(/[/\\]/).pop()}`
        : '';
    const score = clip.total_score != null ? (clip.total_score * 100).toFixed(0) : '—';
    const duration = clip.duration ? formatDuration(clip.duration) : '—';

    return `
        <div class="clip-card" data-clip-id="${clip.id}" onclick="App.viewClip(${clip.id})">
            <div class="clip-thumbnail">
                ${thumbSrc
                    ? `<img src="${thumbSrc}" alt="Clip ${clip.clip_number}" loading="lazy">`
                    : `<div class="clip-thumb-placeholder">🎬</div>`
                }
                <div class="clip-duration-badge">${duration}</div>
                <div class="clip-play-overlay">▶</div>
            </div>
            <div class="clip-info">
                <h3 class="clip-title">${clip.title || `Clip #${clip.clip_number}`}</h3>
                <div class="clip-meta">
                    <span class="clip-score" title="AI Score">🎯 ${score}%</span>
                    ${renderStatusBadge(clip.status)}
                </div>
            </div>
        </div>
    `;
}

function renderVideoCard(video) {
    const duration = video.duration ? formatDuration(video.duration) : '—';
    const size = video.filesize ? formatFileSize(video.filesize) : '—';

    return `
        <div class="video-card" data-video-id="${video.id}">
            <div class="video-card-header">
                <span class="video-icon">🎥</span>
                <div class="video-card-info">
                    <h3 class="video-title">${escapeHtml(video.filename)}</h3>
                    <p class="video-meta">${duration} · ${size} · ${video.width || '?'}×${video.height || '?'}</p>
                </div>
                ${renderStatusBadge(video.status)}
            </div>
            ${video.status === 'processing'
                ? renderProgressBar(video.processing_progress || 0, video.processing_step || 'Processing...', true)
                : ''}
            <div class="video-card-actions">
                ${video.status === 'pending'
                    ? `<button class="btn btn-primary btn-sm" onclick="App.processVideo(${video.id})">🚀 Process</button>`
                    : ''}
                ${video.status === 'completed'
                    ? `<button class="btn btn-secondary btn-sm" onclick="App.navigate('clips', {video_id: ${video.id}})">🎞️ View Clips</button>`
                    : ''}
            </div>
        </div>
    `;
}

function renderDropzone() {
    return `
        <div class="dropzone" id="dropzone">
            <div class="dropzone-content">
                <div class="dropzone-icon">📁</div>
                <h3>Drag & Drop Video Here</h3>
                <p>or click to browse</p>
                <p class="dropzone-formats">Supports MP4, MKV, AVI, MOV · Max 4GB</p>
            </div>
            <input type="file" id="fileInput" accept=".mp4,.mkv,.avi,.mov" hidden>
        </div>
    `;
}

function renderSpinner(text = 'Loading...') {
    return `
        <div class="loading-container">
            <div class="spinner"></div>
            <p>${text}</p>
        </div>
    `;
}

function renderEmptyState(icon, message, actionHtml = '') {
    return `
        <div class="empty-state">
            <div class="empty-icon">${icon}</div>
            <p>${message}</p>
            ${actionHtml}
        </div>
    `;
}

function renderPagination(currentPage, totalPages, onPageChange) {
    if (totalPages <= 1) return '';
    let html = '<div class="pagination">';
    html += `<button class="btn btn-sm btn-secondary" ${currentPage <= 1 ? 'disabled' : ''} onclick="${onPageChange}(${currentPage - 1})">← Prev</button>`;
    html += `<span class="page-info">Page ${currentPage} of ${totalPages}</span>`;
    html += `<button class="btn btn-sm btn-secondary" ${currentPage >= totalPages ? 'disabled' : ''} onclick="${onPageChange}(${currentPage + 1})">Next →</button>`;
    html += '</div>';
    return html;
}


// ─────────────────────────────────────────────
// Utility Functions
// ─────────────────────────────────────────────

function formatDuration(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return m > 0 ? `${m}:${s.toString().padStart(2, '0')}` : `${s}s`;
}

function formatFileSize(bytes) {
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return bytes + ' B';
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function debounce(fn, delay = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}
