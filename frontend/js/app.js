/**
 * AIClipper Main Application
 * SPA router, page renderers, event handling.
 */

const App = {
    currentPage: 'dashboard',
    state: {},

    // ─────────────────────────────────────────────
    // Initialization
    // ─────────────────────────────────────────────

    async init() {
        this._setupNavigation();
        this._setupSidebar();
        this._setupKeyboard();

        // Route to current hash or default
        const hash = window.location.hash.slice(1) || 'dashboard';
        await this.navigate(hash);

        // Hide loading
        const loading = document.getElementById('loadingScreen');
        if (loading) loading.style.display = 'none';
    },

    _setupNavigation() {
        window.addEventListener('hashchange', () => {
            const hash = window.location.hash.slice(1) || 'dashboard';
            this.navigate(hash);
        });

        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                window.location.hash = page;
            });
        });
    },

    _setupSidebar() {
        const toggle = document.getElementById('sidebarToggle');
        const sidebar = document.getElementById('sidebar');
        const mobile = document.getElementById('mobileMenuBtn');

        if (toggle) toggle.addEventListener('click', () => sidebar.classList.toggle('collapsed'));
        if (mobile) mobile.addEventListener('click', () => sidebar.classList.toggle('mobile-open'));
    },

    _setupKeyboard() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') Modal.close();
        });
    },

    // ─────────────────────────────────────────────
    // Router
    // ─────────────────────────────────────────────

    async navigate(page, params = {}) {
        this.state = params;
        this.currentPage = page;

        // Update active nav
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        const activeNav = document.querySelector(`.nav-item[data-page="${page}"]`);
        if (activeNav) activeNav.classList.add('active');

        // Update title
        const titles = {
            dashboard: 'Dashboard', projects: 'Projects', upload: 'Upload Video',
            processing: 'Processing', clips: 'Generated Clips',
            publishing: 'Publishing Center', settings: 'Settings',
        };
        document.getElementById('pageTitle').textContent = titles[page] || page;

        // Close mobile sidebar
        document.getElementById('sidebar')?.classList.remove('mobile-open');

        // Render page
        const content = document.getElementById('contentArea');
        content.innerHTML = renderSpinner('Loading...');

        try {
            switch (page) {
                case 'dashboard':  await this._renderDashboard(content); break;
                case 'projects':   await this._renderProjects(content); break;
                case 'upload':     await this._renderUpload(content); break;
                case 'processing': await this._renderProcessing(content); break;
                case 'clips':      await this._renderClips(content); break;
                case 'publishing': await this._renderPublishing(content); break;
                case 'settings':   await this._renderSettings(content); break;
                default:           content.innerHTML = renderEmptyState('🔍', 'Page not found');
            }
        } catch (err) {
            content.innerHTML = renderEmptyState('❌', `Error: ${err.message}`);
            Toast.error(err.message);
        }
    },

    // ─────────────────────────────────────────────
    // Dashboard Page
    // ─────────────────────────────────────────────

    async _renderDashboard(el) {
        let stats = { total_videos: 0, total_clips: 0, completed_clips: 0, published_uploads: 0, total_projects: 0 };
        try { stats = await api.getAnalytics(); } catch { /* use defaults */ }

        const successRate = stats.total_clips > 0
            ? Math.round((stats.completed_clips / stats.total_clips) * 100) : 0;

        el.innerHTML = `
            <div class="dashboard-grid">
                <div class="stats-row">
                    ${renderStatsCard('🎥', 'Total Videos', stats.total_videos, '#3B82F6')}
                    ${renderStatsCard('🎞️', 'Clips Generated', stats.total_clips, '#8B5CF6')}
                    ${renderStatsCard('✅', 'Completed', stats.completed_clips, '#10B981')}
                    ${renderStatsCard('🚀', 'Published', stats.published_uploads, '#F59E0B')}
                </div>

                <div class="dashboard-panels">
                    <div class="panel">
                        <div class="panel-header">
                            <h2>Recent Videos</h2>
                            <button class="btn btn-sm btn-primary" onclick="App.navigate('upload')">+ Upload</button>
                        </div>
                        <div class="panel-body" id="recentVideos">${renderSpinner()}</div>
                    </div>

                    <div class="panel">
                        <div class="panel-header">
                            <h2>Latest Clips</h2>
                            <button class="btn btn-sm btn-secondary" onclick="App.navigate('clips')">View All</button>
                        </div>
                        <div class="panel-body" id="latestClips">${renderSpinner()}</div>
                    </div>
                </div>

                <div class="panel quick-actions-panel">
                    <div class="panel-header"><h2>Quick Actions</h2></div>
                    <div class="quick-actions">
                        <button class="action-card" onclick="App.navigate('upload')">
                            <span class="action-icon">⬆️</span>
                            <span class="action-label">Upload Video</span>
                        </button>
                        <button class="action-card" onclick="App.navigate('clips')">
                            <span class="action-icon">🎞️</span>
                            <span class="action-label">Browse Clips</span>
                        </button>
                        <button class="action-card" onclick="App.navigate('projects')">
                            <span class="action-icon">📁</span>
                            <span class="action-label">New Project</span>
                        </button>
                        <button class="action-card" onclick="App.navigate('settings')">
                            <span class="action-icon">⚡</span>
                            <span class="action-label">Settings</span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Load recent videos
        this._loadRecentVideos();
        this._loadLatestClips();
    },

    async _loadRecentVideos() {
        const container = document.getElementById('recentVideos');
        try {
            const data = await api.listVideos(0, 5);
            const videos = data.videos || [];
            if (videos.length === 0) {
                container.innerHTML = renderEmptyState('🎥', 'No videos yet', '<button class="btn btn-primary btn-sm" onclick="App.navigate(\'upload\')">Upload First Video</button>');
                return;
            }
            container.innerHTML = videos.map(renderVideoCard).join('');
        } catch { container.innerHTML = '<p class="text-muted">Could not load videos</p>'; }
    },

    async _loadLatestClips() {
        const container = document.getElementById('latestClips');
        try {
            const data = await api.listClips(0, 6);
            const clips = data.clips || [];
            if (clips.length === 0) {
                container.innerHTML = renderEmptyState('🎞️', 'No clips generated yet');
                return;
            }
            container.innerHTML = '<div class="clips-grid">' + clips.map(renderClipCard).join('') + '</div>';
        } catch { container.innerHTML = '<p class="text-muted">Could not load clips</p>'; }
    },

    // ─────────────────────────────────────────────
    // Projects Page
    // ─────────────────────────────────────────────

    async _renderProjects(el) {
        const data = await api.listProjects();
        const projects = data.projects || [];

        el.innerHTML = `
            <div class="page-actions">
                <button class="btn btn-primary" onclick="App.createProject()">+ New Project</button>
            </div>
            <div class="projects-grid" id="projectsList">
                ${projects.length === 0
                    ? renderEmptyState('📁', 'No projects yet', '<button class="btn btn-primary" onclick="App.createProject()">Create Project</button>')
                    : projects.map(p => `
                        <div class="project-card">
                            <div class="project-icon">📁</div>
                            <h3>${escapeHtml(p.name)}</h3>
                            <p class="text-muted">${escapeHtml(p.description || 'No description')}</p>
                            <div class="project-meta">
                                ${renderStatusBadge(p.status)}
                                <span class="text-muted">${formatDate(p.created_at)}</span>
                            </div>
                        </div>
                    `).join('')
                }
            </div>
        `;
    },

    createProject() {
        Modal.open('Create Project', `
            <div class="form-group">
                <label>Project Name</label>
                <input type="text" class="form-input" id="newProjectName" placeholder="My Project" autofocus>
            </div>
            <div class="form-group">
                <label>Description (optional)</label>
                <textarea class="form-input" id="newProjectDesc" placeholder="Project description..." rows="3"></textarea>
            </div>
        `, `
            <button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
            <button class="btn btn-primary" onclick="App._doCreateProject()">Create</button>
        `);
    },

    async _doCreateProject() {
        const name = document.getElementById('newProjectName').value.trim();
        if (!name) { Toast.warning('Please enter a project name'); return; }
        try {
            await api.createProject(name, document.getElementById('newProjectDesc').value.trim());
            Modal.close();
            Toast.success('Project created!');
            this.navigate('projects');
        } catch (e) { Toast.error(e.message); }
    },

    // ─────────────────────────────────────────────
    // Upload Page
    // ─────────────────────────────────────────────

    async _renderUpload(el) {
        el.innerHTML = `
            <div class="upload-page">
                ${renderDropzone()}
                <div class="upload-status" id="uploadStatus" style="display:none;">
                    <div class="upload-file-info" id="uploadFileInfo"></div>
                    ${renderProgressBar(0, 'Uploading...')}
                    <div id="uploadActions"></div>
                </div>
            </div>
        `;

        this._setupDropzone();
    },

    _setupDropzone() {
        const dropzone = document.getElementById('dropzone');
        const fileInput = document.getElementById('fileInput');

        dropzone.addEventListener('click', () => fileInput.click());

        dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) this._handleUpload(e.dataTransfer.files[0]);
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) this._handleUpload(e.target.files[0]);
        });
    },

    async _handleUpload(file) {
        const status = document.getElementById('uploadStatus');
        const fileInfo = document.getElementById('uploadFileInfo');
        const dropzone = document.getElementById('dropzone');

        dropzone.style.display = 'none';
        status.style.display = 'block';
        fileInfo.innerHTML = `
            <span class="file-icon">🎥</span>
            <div>
                <strong>${escapeHtml(file.name)}</strong>
                <span class="text-muted">${formatFileSize(file.size)}</span>
            </div>
        `;

        try {
            const result = await api.uploadVideo(file, null, (pct) => {
                const fill = status.querySelector('.progress-fill');
                const label = status.querySelector('.progress-label span:last-child');
                if (fill) fill.style.width = pct + '%';
                if (label) label.textContent = pct + '%';
            });

            Toast.success('Video uploaded successfully!');
            document.getElementById('uploadActions').innerHTML = `
                <div class="upload-success">
                    <p>✅ Upload complete! Video ID: <strong>${result.id}</strong></p>
                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="App.processVideo(${result.id})">🚀 Process Now</button>
                        <button class="btn btn-secondary" onclick="App.navigate('upload')">Upload Another</button>
                    </div>
                </div>
            `;
        } catch (err) {
            Toast.error('Upload failed: ' + err.message);
            dropzone.style.display = 'block';
            status.style.display = 'none';
        }
    },

    // ─────────────────────────────────────────────
    // Processing Page
    // ─────────────────────────────────────────────

    async _renderProcessing(el) {
        const data = await api.listVideos(0, 50);
        const allVideos = data.videos || [];
        const processingVideos = allVideos.filter(v => v.status === 'processing');
        const pendingVideos = allVideos.filter(v => v.status === 'pending');
        const completedVideos = allVideos.filter(v => v.status === 'completed' || v.status === 'failed');

        // If there's an active processing video, show the detailed panel
        if (processingVideos.length > 0) {
            const activeVideo = processingVideos[0];
            // Fetch full detail for the active video
            let videoDetail = activeVideo;
            try {
                videoDetail = await api.getVideo(activeVideo.id);
            } catch { /* use list data */ }

            el.innerHTML = `
                <div class="processing-page">
                    ${renderProcessingPanel(videoDetail)}

                    ${pendingVideos.length > 0 ? `
                        <div class="panel" style="margin-top: 1.5rem;">
                            <div class="panel-header"><h2>⏳ Queued (${pendingVideos.length})</h2></div>
                            <div class="panel-body">${pendingVideos.map(renderVideoCard).join('')}</div>
                        </div>
                    ` : ''}

                    ${completedVideos.length > 0 ? `
                        <div class="panel" style="margin-top: 1.5rem;">
                            <div class="panel-header"><h2>📦 History</h2></div>
                            <div class="panel-body">${completedVideos.slice(0, 5).map(renderVideoCard).join('')}</div>
                        </div>
                    ` : ''}
                </div>
            `;

            // Start elapsed timer
            this._processingStartTime = this._processingStartTime || Date.now();
            this._startElapsedTimer();

            // Connect WebSocket for real-time updates
            this._lastLogStep = '';
            this._logCount = 1;
            api.connectProgress(activeVideo.id, (wsData) => {
                const progress = wsData.progress || 0;
                const step = wsData.step || 'Processing...';

                // Update progress bar
                const fill = document.getElementById('progressFill');
                const pct = document.getElementById('progressPct');
                const stepText = document.getElementById('currentStepText');
                if (fill) fill.style.width = progress + '%';
                if (pct) pct.textContent = progress + '%';
                if (stepText) stepText.textContent = step;

                // Update pipeline timeline steps
                const STEP_RANGES = [
                    { key: 'transcription', range: [0, 20] },
                    { key: 'scene_detection', range: [20, 35] },
                    { key: 'audio_analysis', range: [35, 50] },
                    { key: 'face_tracking', range: [50, 65] },
                    { key: 'clip_scoring', range: [65, 70] },
                    { key: 'clip_generation', range: [70, 85] },
                    { key: 'subtitles', range: [85, 90] },
                    { key: 'metadata', range: [90, 95] },
                    { key: 'thumbnails', range: [95, 100] },
                ];

                STEP_RANGES.forEach(s => {
                    const stepEl = document.querySelector(`[data-step="${s.key}"]`);
                    if (!stepEl) return;
                    stepEl.classList.remove('pipeline-step-pending', 'pipeline-step-active', 'pipeline-step-done');
                    if (progress >= s.range[1]) {
                        stepEl.classList.add('pipeline-step-done');
                        const dot = stepEl.querySelector('.step-dot');
                        if (dot) dot.innerHTML = '✓';
                        // Update badges
                        const hdr = stepEl.querySelector('.step-header');
                        if (hdr && !hdr.querySelector('.step-done-badge')) {
                            const activeBadge = hdr.querySelector('.step-active-badge');
                            if (activeBadge) activeBadge.remove();
                            hdr.insertAdjacentHTML('beforeend', '<span class="step-done-badge">Done</span>');
                        }
                    } else if (progress >= s.range[0]) {
                        stepEl.classList.add('pipeline-step-active');
                        const dot = stepEl.querySelector('.step-dot');
                        if (dot && !dot.querySelector('.step-pulse')) dot.innerHTML = '<div class="step-pulse"></div>';
                        const hdr = stepEl.querySelector('.step-header');
                        if (hdr && !hdr.querySelector('.step-active-badge')) {
                            hdr.insertAdjacentHTML('beforeend', '<span class="step-active-badge">Running</span>');
                        }
                    } else {
                        stepEl.classList.add('pipeline-step-pending');
                        const dot = stepEl.querySelector('.step-dot');
                        if (dot) dot.innerHTML = '';
                    }
                });

                // Add activity log entries when step changes
                if (step !== this._lastLogStep) {
                    this._addLogEntry(step, progress);
                    this._lastLogStep = step;
                }

                // Handle completion
                if (wsData.status === 'completed' || wsData.status === 'failed') {
                    api.disconnectProgress(activeVideo.id);
                    this._stopElapsedTimer();
                    this._processingStartTime = null;
                    const isSuccess = wsData.status === 'completed';
                    Toast.show(
                        isSuccess ? '🎉 Processing complete! Check your clips.' : '❌ Processing failed.',
                        isSuccess ? 'success' : 'error',
                        6000
                    );
                    this._addLogEntry(isSuccess ? '✅ Pipeline finished!' : '❌ Pipeline failed: ' + (wsData.error_message || 'Unknown error'), progress);
                    // Refresh page after a delay
                    setTimeout(() => this.navigate(isSuccess ? 'clips' : 'processing'), 3000);
                }
            });

        } else {
            // No active processing — show queue and history
            el.innerHTML = `
                <div class="processing-page">
                    <div class="panel">
                        <div class="panel-header"><h2>Active Processing</h2></div>
                        <div class="panel-body">
                            ${renderEmptyState('⚙️', 'No videos are currently processing',
                                '<button class="btn btn-primary" onclick="App.navigate(\'upload\')">Upload a Video</button>')}
                        </div>
                    </div>
                    ${allVideos.length > 0 ? `
                        <div class="panel" style="margin-top: 1.5rem;">
                            <div class="panel-header"><h2>All Videos</h2></div>
                            <div class="panel-body">${allVideos.map(renderVideoCard).join('')}</div>
                        </div>
                    ` : ''}
                </div>
            `;
        }
    },

    _elapsedInterval: null,

    _startElapsedTimer() {
        this._stopElapsedTimer();
        this._elapsedInterval = setInterval(() => {
            const el = document.getElementById('elapsedTime');
            if (!el || !this._processingStartTime) return;
            const elapsed = Math.floor((Date.now() - this._processingStartTime) / 1000);
            const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
            const s = (elapsed % 60).toString().padStart(2, '0');
            el.textContent = `${m}:${s}`;
        }, 1000);
    },

    _stopElapsedTimer() {
        if (this._elapsedInterval) {
            clearInterval(this._elapsedInterval);
            this._elapsedInterval = null;
        }
    },

    _addLogEntry(message, progress) {
        const feed = document.getElementById('activityFeed');
        const countEl = document.getElementById('logCount');
        if (!feed) return;
        this._logCount = (this._logCount || 0) + 1;
        const time = new Date().toLocaleTimeString();
        const entry = document.createElement('div');
        entry.className = 'activity-entry activity-entry-new';
        entry.innerHTML = `
            <span class="activity-time">${time}</span>
            <span class="activity-progress">${progress}%</span>
            <span class="activity-msg">${message}</span>
        `;
        feed.insertBefore(entry, feed.firstChild);
        if (countEl) countEl.textContent = `${this._logCount} events`;
        // Keep max 50 entries
        while (feed.children.length > 50) feed.removeChild(feed.lastChild);
    },

    // ─────────────────────────────────────────────
    // Clips Page
    // ─────────────────────────────────────────────

    async _renderClips(el) {
        const videoId = this.state.video_id || null;
        const data = await api.listClips(0, 50, videoId);
        const clips = data.clips || [];

        el.innerHTML = `
            <div class="clips-page">
                <div class="page-actions">
                    <span class="text-muted">${clips.length} clip${clips.length !== 1 ? 's' : ''} found</span>
                </div>
                <div class="clips-grid" id="clipsGrid">
                    ${clips.length === 0
                        ? renderEmptyState('🎞️', 'No clips generated yet', '<button class="btn btn-primary" onclick="App.navigate(\'upload\')">Upload & Process a Video</button>')
                        : clips.map(renderClipCard).join('')
                    }
                </div>
            </div>
        `;
    },

    async viewClip(clipId) {
        try {
            const clip = await api.getClip(clipId);
            const downloadUrl = api.getClipDownloadUrl(clipId);
            const score = clip.total_score != null ? (clip.total_score * 100).toFixed(1) : '—';

            // Build score breakdown HTML
            let breakdownHtml = '';
            if (clip.score_breakdown_json) {
                const bd = clip.score_breakdown_json;
                const items = [
                    { label: 'Emotion', val: bd.emotion || 0, icon: '💡' },
                    { label: 'Dialogue', val: bd.dialogue || 0, icon: '💬' },
                    { label: 'Scene', val: bd.scene_change || 0, icon: '🎬' },
                    { label: 'Audio', val: bd.audio || 0, icon: '🔊' },
                    { label: 'Face', val: bd.face || 0, icon: '👤' },
                ];
                breakdownHtml = `
                    <div class="clip-score-breakdown">
                        ${items.map(it => `
                            <div class="clip-score-item">
                                <span class="score-label">${it.icon} ${it.label}</span>
                                <div class="score-bar"><div class="score-fill" style="width:${(it.val * 100).toFixed(0)}%"></div></div>
                            </div>
                        `).join('')}
                    </div>
                `;
            }

            Modal.open(clip.title || `Clip #${clip.clip_number}`, `
                <div class="clip-detail">
                    ${clip.output_path ? `
                        <video controls class="clip-video-player" preload="metadata" autoplay>
                            <source src="/outputs/${clip.output_path.split(/[/\\\\]/).pop()}" type="video/mp4">
                        </video>
                    ` : '<div class="clip-thumb-placeholder" style="height:400px;">🎬 No preview</div>'}

                    <div>
                        <div class="clip-detail-meta">
                            <div class="detail-row"><span>Duration</span><span>${formatDuration(clip.duration)}</span></div>
                            <div class="detail-row"><span>AI Score</span><span>🎯 ${score}%</span></div>
                            <div class="detail-row"><span>Time Range</span><span>${formatDuration(clip.start_time)} → ${formatDuration(clip.end_time)}</span></div>
                            <div class="detail-row"><span>Status</span>${renderStatusBadge(clip.status)}</div>
                        </div>

                        ${breakdownHtml}

                        ${clip.description ? `<p class="clip-description">${escapeHtml(clip.description)}</p>` : ''}
                        ${clip.hashtags ? `<div class="clip-hashtags">${escapeHtml(clip.hashtags)}</div>` : ''}
                    </div>
                </div>
            `, `
                <a href="${downloadUrl}" class="btn btn-primary" download>⬇️ Download</a>
                <button class="btn btn-secondary" onclick="App.publishClipDialog(${clipId})">🚀 Publish</button>
                <button class="btn btn-danger" onclick="App.deleteClip(${clipId})">🗑️ Delete</button>
            `, 'lg');
        } catch (e) { Toast.error(e.message); }
    },

    async deleteClip(clipId) {
        Modal.confirm('Delete Clip', 'Are you sure you want to delete this clip? This cannot be undone.', async () => {
            try {
                await api.deleteClip(clipId);
                Toast.success('Clip deleted');
                this.navigate('clips');
            } catch (e) { Toast.error(e.message); }
        });
    },

    // ─────────────────────────────────────────────
    // Publishing Page
    // ─────────────────────────────────────────────

    async _renderPublishing(el) {
        const data = await api.listClips(0, 100);
        const clips = (data.clips || []).filter(c => c.status === 'completed');

        el.innerHTML = `
            <div class="publishing-page">
                <div class="panel">
                    <div class="panel-header"><h2>Connected Accounts</h2></div>
                    <div class="panel-body accounts-grid">
                        <div class="account-card">
                            <span class="account-icon">📺</span>
                            <h3>YouTube</h3>
                            <p class="text-muted">Upload Shorts via YouTube Data API</p>
                            <span class="badge badge-warning">Requires OAuth Setup</span>
                        </div>
                        <div class="account-card">
                            <span class="account-icon">📘</span>
                            <h3>Facebook</h3>
                            <p class="text-muted">Upload Reels via Graph API</p>
                            <span class="badge badge-warning">Requires Token</span>
                        </div>
                        <div class="account-card account-coming-soon">
                            <span class="account-icon">🎵</span>
                            <h3>TikTok</h3>
                            <p class="text-muted">Coming soon</p>
                            <span class="badge badge-default">Planned</span>
                        </div>
                        <div class="account-card account-coming-soon">
                            <span class="account-icon">📸</span>
                            <h3>Instagram</h3>
                            <p class="text-muted">Coming soon</p>
                            <span class="badge badge-default">Planned</span>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header"><h2>Ready to Publish (${clips.length})</h2></div>
                    <div class="panel-body">
                        ${clips.length === 0
                            ? renderEmptyState('🚀', 'No clips ready to publish')
                            : '<div class="clips-grid">' + clips.map(c => renderClipCard(c)).join('') + '</div>'
                        }
                    </div>
                </div>
            </div>
        `;
    },

    publishClipDialog(clipId) {
        Modal.open('Publish Clip', `
            <div class="form-group">
                <label>Select Platform</label>
                <select class="form-input" id="publishPlatform">
                    <option value="youtube">📺 YouTube Shorts</option>
                    <option value="facebook">📘 Facebook Reels</option>
                </select>
            </div>
        `, `
            <button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
            <button class="btn btn-primary" onclick="App._doPublish(${clipId})">🚀 Publish</button>
        `);
    },

    async _doPublish(clipId) {
        const platform = document.getElementById('publishPlatform').value;
        try {
            await api.publishClip(clipId, platform);
            Modal.close();
            Toast.success(`Clip queued for ${platform} upload!`);
        } catch (e) { Toast.error(e.message); }
    },

    // ─────────────────────────────────────────────
    // Settings Page
    // ─────────────────────────────────────────────

    async _renderSettings(el) {
        el.innerHTML = `
            <div class="settings-page">
                <div class="settings-grid">
                    <div class="panel">
                        <div class="panel-header"><h2>Clip Generation</h2></div>
                        <div class="panel-body">
                            <div class="form-group">
                                <label>Clip Durations (seconds)</label>
                                <input type="text" class="form-input" id="setClipDurations" value="15, 30, 60" placeholder="15, 30, 60">
                            </div>
                            <div class="form-group">
                                <label>Max Clips Per Video</label>
                                <input type="number" class="form-input" id="setMaxClips" value="10" min="1" max="50">
                            </div>
                            <div class="form-group">
                                <label>Min Gap Between Clips (seconds)</label>
                                <input type="number" class="form-input" id="setMinGap" value="10" min="0" max="120">
                            </div>
                        </div>
                    </div>

                    <div class="panel">
                        <div class="panel-header"><h2>Scoring Weights</h2></div>
                        <div class="panel-body">
                            ${this._renderWeightSlider('Emotion', 'weightEmotion', 25)}
                            ${this._renderWeightSlider('Dialogue', 'weightDialogue', 20)}
                            ${this._renderWeightSlider('Scene Change', 'weightScene', 20)}
                            ${this._renderWeightSlider('Audio Energy', 'weightAudio', 20)}
                            ${this._renderWeightSlider('Face Visibility', 'weightFace', 15)}
                            <div class="weight-total">
                                <span>Total:</span>
                                <span id="weightTotal">100%</span>
                            </div>
                        </div>
                    </div>

                    <div class="panel">
                        <div class="panel-header"><h2>Subtitle Style</h2></div>
                        <div class="panel-body">
                            <div class="form-group">
                                <label>Font Family</label>
                                <select class="form-input" id="setSubFont">
                                    <option value="Arial">Arial</option>
                                    <option value="Montserrat">Montserrat</option>
                                    <option value="Roboto">Roboto</option>
                                    <option value="Inter">Inter</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Font Size</label>
                                <input type="number" class="form-input" id="setSubSize" value="24" min="12" max="48">
                            </div>
                            <div class="form-group">
                                <label>Highlight Color</label>
                                <input type="color" class="form-input form-color" id="setSubHighlight" value="#FFD700">
                            </div>
                            <div class="form-group">
                                <label>Position</label>
                                <select class="form-input" id="setSubPosition">
                                    <option value="bottom">Bottom</option>
                                    <option value="center">Center</option>
                                    <option value="top">Top</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div class="panel">
                        <div class="panel-header"><h2>AI Models</h2></div>
                        <div class="panel-body">
                            <div class="form-group">
                                <label>Whisper Model</label>
                                <select class="form-input" id="setWhisperModel">
                                    <option value="tiny.en">Tiny (fastest)</option>
                                    <option value="base.en">Base</option>
                                    <option value="small.en" selected>Small (recommended)</option>
                                    <option value="medium.en">Medium (slow)</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Ollama Model</label>
                                <select class="form-input" id="setOllamaModel">
                                    <option value="qwen2" selected>Qwen 2</option>
                                    <option value="llama3">Llama 3</option>
                                    <option value="gemma2">Gemma 2</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="settings-actions">
                    <button class="btn btn-primary btn-lg" onclick="App._saveSettings()">💾 Save Settings</button>
                </div>
            </div>
        `;

        // Set up weight slider listeners
        document.querySelectorAll('.weight-slider').forEach(slider => {
            slider.addEventListener('input', () => this._updateWeightTotal());
        });
    },

    _renderWeightSlider(label, id, defaultVal) {
        return `
            <div class="form-group slider-group">
                <label>${label} <span class="slider-value" id="${id}Value">${defaultVal}%</span></label>
                <input type="range" class="weight-slider form-range" id="${id}" min="0" max="50" value="${defaultVal}"
                       oninput="document.getElementById('${id}Value').textContent = this.value + '%'">
            </div>
        `;
    },

    _updateWeightTotal() {
        const ids = ['weightEmotion', 'weightDialogue', 'weightScene', 'weightAudio', 'weightFace'];
        const total = ids.reduce((sum, id) => sum + parseInt(document.getElementById(id)?.value || 0), 0);
        const el = document.getElementById('weightTotal');
        if (el) {
            el.textContent = total + '%';
            el.style.color = total === 100 ? 'var(--accent-success)' : 'var(--accent-danger)';
        }
    },

    async _saveSettings() {
        try {
            const settings = {
                clip_durations: document.getElementById('setClipDurations').value,
                max_clips: document.getElementById('setMaxClips').value,
                min_gap: document.getElementById('setMinGap').value,
                weight_emotion: document.getElementById('weightEmotion').value,
                weight_dialogue: document.getElementById('weightDialogue').value,
                weight_scene: document.getElementById('weightScene').value,
                weight_audio: document.getElementById('weightAudio').value,
                weight_face: document.getElementById('weightFace').value,
                subtitle_font: document.getElementById('setSubFont').value,
                subtitle_size: document.getElementById('setSubSize').value,
                subtitle_highlight: document.getElementById('setSubHighlight').value,
                subtitle_position: document.getElementById('setSubPosition').value,
                whisper_model: document.getElementById('setWhisperModel').value,
                ollama_model: document.getElementById('setOllamaModel').value,
            };

            await api.updateSettings(settings);
            Toast.success('Settings saved!');
        } catch (e) {
            Toast.error('Failed to save: ' + e.message);
        }
    },

    // ─────────────────────────────────────────────
    // Actions
    // ─────────────────────────────────────────────

    async processVideo(videoId) {
        try {
            await api.startProcessing(videoId);
            Toast.success('Processing started! This may take a while on CPU.');
            this.navigate('processing');
        } catch (e) { Toast.error(e.message); }
    },
};

// ─────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => App.init());
