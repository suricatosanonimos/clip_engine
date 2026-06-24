/**
 * ═══════════════════════════════════════════════════════════
 *  NEW PROJECT — Clip Engine
 *  Gerencia a página de novo projeto
 * ═══════════════════════════════════════════════════════════
 * 
 *  Rotas da API:
 *  - POST /api/info          → informações do vídeo
 *  - POST /api/info/titles   → gera títulos virais com IA
 *  - POST /api/video/process → inicia processamento do vídeo
 *  - GET  /api/status/{id}   → status do processamento
 *  - POST /api/jobs          → cria job no banco
 *  - GET  /api/clips         → lista clipes do usuário
 * ═══════════════════════════════════════════════════════════
 */

class NewProjectManager {
    constructor(config = {}) {
        // ── Configurações ──────────────────────────────────
        this.config = {
            apiBaseUrl: config.apiBaseUrl || 'http://localhost:8000',
            inputSelector: '#video-url-input',
            buttonSelector: '#search-info-btn',
            previewSelector: '#video-preview',
            processButtonSelector: '#process-video-btn'
        };

        // ── Endpoints da API ──────────────────────────────
        this.api = {
            videoInfo: `${this.config.apiBaseUrl}/api/info`,
            titles: `${this.config.apiBaseUrl}/api/info/titles`,
            process: `${this.config.apiBaseUrl}/api/video/process`,
            jobs: `${this.config.apiBaseUrl}/api/jobs`,
            clips: `${this.config.apiBaseUrl}/api/clips`,
            status: (taskId) => `${this.config.apiBaseUrl}/api/status/${taskId}`,
            statusStream: (taskId) => `${this.config.apiBaseUrl}/api/status/${taskId}/stream`
        };

        // ── DOM Elements ──────────────────────────────────
        this.input = document.querySelector(this.config.inputSelector);
        this.searchBtn = document.querySelector(this.config.buttonSelector);
        this.preview = document.querySelector(this.config.previewSelector);
        this.processBtn = document.querySelector(this.config.processButtonSelector);

        // ── Estado ─────────────────────────────────────────
        this.state = {
            isLoading: false,
            isGeneratingTitles: false,
            isProcessing: false,
            currentUrl: '',
            videoInfo: null,
            titles: [],
            jobId: null,
            taskId: null,
            userId: 'user_test_001',
            settings: {
                numClips: 3,
                clipDuration: 60,
                format: '9:16',
                tracking: true,
                subtitles: true,
                subtitleColor: 'white',
                sourceType: 'youtube'
            }
        };

        // ── Bind ──────────────────────────────────────────
        this.handleSearch = this.handleSearch.bind(this);
        this.handleKeyPress = this.handleKeyPress.bind(this);
        this.handleGenerateTitles = this.handleGenerateTitles.bind(this);
        this.handleProcessVideo = this.handleProcessVideo.bind(this);

        // ── Init ──────────────────────────────────────────
        this.init();
    }

    // ──────────────────────────────────────────────────────────────
    //  INIT
    // ──────────────────────────────────────────────────────────────

    init() {
        console.log('🎬 [NewProjectManager] Inicializando...');

        // Fallback para elementos DOM
        if (!this.input) this.input = document.querySelector('.input-field');
        if (!this.searchBtn) this.searchBtn = document.querySelector('.source-input .btn-primary');
        if (!this.preview) this.preview = document.querySelector('.video-preview-placeholder');
        if (!this.processBtn) this.processBtn = document.querySelector('.submit-section .btn-primary');

        // Event Listeners
        if (this.searchBtn) {
            this.searchBtn.addEventListener('click', this.handleSearch);
        }
        if (this.input) {
            this.input.addEventListener('keypress', this.handleKeyPress);
        }
        if (this.processBtn) {
            this.processBtn.addEventListener('click', this.handleProcessVideo);
        }

        this._setupSettingsListeners();
        this.showEmptyState();

        // Verifica se veio task_id da URL
        this._checkTaskIdFromUrl();

        console.log('✅ [NewProjectManager] Inicializado!');
        console.log('📊 Estado inicial:', this.state.settings);
    }

    // ──────────────────────────────────────────────────────────────
    //  SETTINGS LISTENERS - CORRIGIDO COM IDs E DATA ATTRIBUTES
    // ──────────────────────────────────────────────────────────────

    _setupSettingsListeners() {
        // ── Range de clipes ──
        const range = document.getElementById('num-clips-range');
        if (range) {
            range.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                this.state.settings.numClips = value;
                const display = document.getElementById('num-clips-value');
                if (display) display.textContent = value;
                console.log(`📊 Clipes: ${value}`);
            });
        }

        // ── Duração ──
        document.querySelectorAll('#duration-group .btn-option').forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active de todos
                document.querySelectorAll('#duration-group .btn-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const duration = parseInt(btn.dataset.duration);
                this.state.settings.clipDuration = duration;
                console.log(`⏱️ Duração: ${duration}s`);
            });
        });

        // ── Formato ──
        document.querySelectorAll('#format-group .btn-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#format-group .btn-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const format = btn.dataset.format;
                this.state.settings.format = format;
                console.log(`📱 Formato: ${format}`);
            });
        });

        // ── Tracking ──
        document.querySelectorAll('#tracking-group .btn-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#tracking-group .btn-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const tracking = btn.dataset.tracking === 'true';
                this.state.settings.tracking = tracking;
                console.log(`🎯 Tracking: ${tracking ? 'Ativado' : 'Desativado'}`);
            });
        });

        // ── Legendas ──
        document.querySelectorAll('#subtitles-group .btn-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#subtitles-group .btn-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const subtitles = btn.dataset.subtitles === 'true';
                this.state.settings.subtitles = subtitles;
                console.log(`📝 Legendas: ${subtitles ? 'Ativado' : 'Desativado'}`);
            });
        });

        // ── Cores ──
        document.querySelectorAll('#color-picker .color-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#color-picker .color-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const color = btn.dataset.color;
                this.state.settings.subtitleColor = color;
                console.log(`🎨 Cor: ${color}`);
            });
        });

        // ── Fonte (Tabs) ──
        document.querySelectorAll('#source-tabs .source-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('#source-tabs .source-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const source = tab.dataset.source;
                this.state.settings.sourceType = source;
                console.log(`📤 Fonte: ${source}`);
                
                // Muda placeholder do input
                if (this.input) {
                    if (source === 'youtube') {
                        this.input.placeholder = 'https://www.youtube.com/watch?v=...';
                    } else {
                        this.input.placeholder = 'Selecione um arquivo de vídeo...';
                    }
                }
            });
        });

        console.log('✅ Settings listeners configurados!');
    }

    // ──────────────────────────────────────────────────────────────
    //  CHECK TASK ID FROM URL
    // ──────────────────────────────────────────────────────────────

    _checkTaskIdFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const taskId = params.get('task_id');
        if (taskId) {
            console.log(`📋 Task ID encontrado na URL: ${taskId}`);
            this.state.taskId = taskId;
        }
    }

    // ──────────────────────────────────────────────────────────────
    //  EVENT HANDLERS
    // ──────────────────────────────────────────────────────────────

    handleKeyPress(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            this.handleSearch();
        }
    }

    async handleSearch() {
        if (this.state.isLoading) return;

        const url = this.input?.value?.trim();
        if (!url) return this.showError('Cole uma URL do YouTube.');

        if (!this._isYouTubeUrl(url)) {
            return this.showError('URL inválida. Insira uma URL do YouTube válida.');
        }

        this.state.currentUrl = url;
        this.state.isLoading = true;
        this.state.titles = [];
        this.showLoading();

        try {
            const info = await this._fetchVideoInfo(url);
            this.state.videoInfo = info;
            this.showVideoPreview(info);
        } catch (err) {
            this.showError(err.message || 'Erro ao buscar informações.');
        } finally {
            this.state.isLoading = false;
        }
    }

    async handleGenerateTitles() {
        if (this.state.isGeneratingTitles) return;
        if (!this.state.currentUrl) {
            return this.showError('Busque as informações do vídeo primeiro.');
        }

        this.state.isGeneratingTitles = true;

        const container = this.preview?.querySelector('.video-preview-actions');
        if (container) {
            container.innerHTML = `
                <div class="titles-loading">
                    <span class="material-icons loading-icon spin">sync</span>
                    <span>Gerando títulos com IA...</span>
                    <small>Isso pode levar alguns segundos</small>
                </div>
            `;
        }

        try {
            const result = await this._fetchTitles(this.state.currentUrl, 5);
            if (result.titles?.length) {
                this.state.titles = result.titles;
                this.showTitles(result.titles);
            } else {
                this.showTitlesError('Não foi possível gerar títulos. Tente novamente.');
            }
        } catch (err) {
            this.showTitlesError(err.message || 'Erro ao gerar títulos.');
        } finally {
            this.state.isGeneratingTitles = false;
        }
    }

    async handleProcessVideo() {
        if (this.state.isProcessing) return;
        if (!this.state.currentUrl) {
            return this.showError('Busque as informações do vídeo primeiro.');
        }

        // Mostra as configurações atuais
        const settings = this.state.settings;
        const msg = `Processar "${this.state.videoInfo?.title || 'Vídeo'}"?\n\n` +
            `Clipes: ${settings.numClips}\n` +
            `Duração: ${settings.clipDuration}s\n` +
            `Formato: ${settings.format}\n` +
            `Tracking: ${settings.tracking ? 'Ativado' : 'Desativado'}\n` +
            `Legendas: ${settings.subtitles ? 'Ativado' : 'Desativado'}\n` +
            `Cor da legenda: ${settings.subtitleColor}`;

        if (!confirm(msg)) return;

        this.state.isProcessing = true;

        if (this.processBtn) {
            this.processBtn.innerHTML = `<span class="material-icons spin">sync</span> Processando...`;
            this.processBtn.disabled = true;
        }

        try {
            // ── Passo 1: Criar job no banco ──
            const job = await this._createJob();
            this.state.jobId = job.id;
            console.log(`📋 Job criado: ${this.state.jobId}`);

            // ── Passo 2: Processar vídeo ──
            const result = await this._processVideo(this.state.currentUrl, this.state.jobId);
            this.state.taskId = result.task_id;
            
            console.log(`✅ Processamento iniciado! Task ID: ${result.task_id}`);

            // ── Passo 3: Redirecionar para página de status ──
            window.location.href = `processing.html?task_id=${result.task_id}&job_id=${this.state.jobId}`;

        } catch (err) {
            console.error('❌ Erro:', err);
            alert(`❌ Erro ao processar vídeo:\n\n${err.message || 'Erro desconhecido'}`);
            
            if (this.processBtn) {
                this.processBtn.innerHTML = `<span class="material-icons">play_arrow</span> Processar Vídeo`;
                this.processBtn.disabled = false;
            }
            this.state.isProcessing = false;
        }
    }

    // ──────────────────────────────────────────────────────────────
    //  API CALLS
    // ──────────────────────────────────────────────────────────────

    async _fetchVideoInfo(url) {
        const res = await fetch(this.api.videoInfo, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ${res.status}`);
        }

        return res.json();
    }

    async _fetchTitles(url, count = 5) {
        const res = await fetch(this.api.titles, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, count })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ${res.status}`);
        }

        const data = await res.json();
        return {
            titles: data.titles || [],
            video_title: data.video_title || ''
        };
    }

    async _createJob() {
        const payload = {
            user_id: this.state.userId,
            source_type: this.state.settings.sourceType,
            source_url: this.state.currentUrl,
            num_clips: this.state.settings.numClips,
            clip_duration: this.state.settings.clipDuration,
            tracking: this.state.settings.tracking
        };

        console.log('📤 Criando job:', payload);

        const res = await fetch(this.api.jobs, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ao criar job: ${res.status}`);
        }

        return res.json();
    }

    async _processVideo(url, jobId) {
        const payload = {
            url: url,
            user_id: this.state.userId,
            job_id: jobId,
            num_clips: this.state.settings.numClips,
            clip_duration: this.state.settings.clipDuration,
            tracking: this.state.settings.tracking,
            subtitles: this.state.settings.subtitles,
            source_type: this.state.settings.sourceType,
            cor_legenda: this.state.settings.subtitleColor
        };

        console.log('📤 Processando vídeo:', payload);

        const res = await fetch(this.api.process, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ao processar: ${res.status}`);
        }

        return res.json();
    }

    async _getStatus(taskId) {
        const res = await fetch(this.api.status(taskId));

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ao buscar status: ${res.status}`);
        }

        return res.json();
    }

    // ──────────────────────────────────────────────────────────────
    //  SSE - STATUS STREAM
    // ──────────────────────────────────────────────────────────────

    _connectStatusStream(taskId, onUpdate, onComplete) {
        const eventSource = new EventSource(this.api.statusStream(taskId));

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('📡 Status update:', data);
                
                if (onUpdate) onUpdate(data);
                
                if (data.status === 'done' || data.status === 'error') {
                    eventSource.close();
                    if (onComplete) onComplete(data);
                }
            } catch (e) {
                console.error('Erro ao parsear SSE:', e);
            }
        };

        eventSource.onerror = (error) => {
            console.error('❌ Erro no SSE:', error);
            eventSource.close();
            if (onComplete) onComplete({ status: 'error', error: 'Conexão perdida' });
        };

        return eventSource;
    }

    // ──────────────────────────────────────────────────────────────
    //  VALIDAÇÃO
    // ──────────────────────────────────────────────────────────────

    _isYouTubeUrl(url) {
        return /(?:youtube\.com\/watch\?v=)([\w-]+)/.test(url) ||
               /(?:youtu\.be\/)([\w-]+)/.test(url) ||
               /(?:youtube\.com\/shorts\/)([\w-]+)/.test(url) ||
               /(?:youtube\.com\/embed\/)([\w-]+)/.test(url);
    }

    // ──────────────────────────────────────────────────────────────
    //  UI RENDER
    // ──────────────────────────────────────────────────────────────

    showEmptyState() {
        if (!this.preview) return;
        this.preview.className = 'video-preview-placeholder';
        this.preview.innerHTML = `
            <span class="material-icons preview-icon">play_circle_outline</span>
            <span>Nenhum vídeo carregado</span>
            <small>Cole a URL para ver as informações</small>
        `;
    }

    showLoading() {
        if (!this.preview) return;
        this.preview.className = 'video-preview-placeholder loading';
        this.preview.innerHTML = `
            <div class="loading-spinner">
                <span class="material-icons loading-icon spin">sync</span>
            </div>
            <span>Buscando informações...</span>
            <small>Isso pode levar alguns segundos</small>
        `;
    }

    showError(msg) {
        if (!this.preview) return;
        this.preview.className = 'video-preview-placeholder error';
        this.preview.innerHTML = `
            <span class="material-icons preview-icon error-icon">error_outline</span>
            <span class="error-message">${this._escapeHtml(msg)}</span>
            <small>Tente novamente com uma URL válida</small>
        `;
    }

    showVideoPreview(info) {
        if (!this.preview) return;

        this.preview.className = 'video-preview-placeholder success';

        const duration = this._formatDuration(info.duration || 0);
        const views = this._formatNumber(info.view_count || 0);

        const thumb = info.thumbnail
            ? `<img src="${this._escapeHtml(info.thumbnail)}" class="video-thumbnail-img" />`
            : `<span class="material-icons preview-thumbnail-icon">play_circle_filled</span>`;

        this.preview.innerHTML = `
            <div class="video-preview-content">
                <div class="video-preview-thumbnail">
                    ${thumb}
                    <span class="video-duration">${duration}</span>
                </div>
                <div class="video-preview-details">
                    <h3 class="video-title">${this._escapeHtml(info.title || 'Sem título')}</h3>
                    <div class="video-meta">
                        <span class="video-channel">
                            <span class="material-icons meta-icon">person</span>
                            ${this._escapeHtml(info.uploader || 'Desconhecido')}
                        </span>
                        <span class="video-views">
                            <span class="material-icons meta-icon">visibility</span>
                            ${views} visualizações
                        </span>
                    </div>
                    ${info.description ? `
                        <p class="video-description">${this._truncateText(this._escapeHtml(info.description), 120)}</p>
                    ` : ''}
                </div>
            </div>
            <div class="video-preview-actions">
                <button class="btn btn-outline btn-sm" id="fetch-titles-btn">
                    <span class="material-icons">auto_awesome</span>
                    Gerar Títulos com IA
                </button>
            </div>
        `;

        const btn = this.preview.querySelector('#fetch-titles-btn');
        if (btn) btn.addEventListener('click', this.handleGenerateTitles);
    }

    showTitles(titles) {
        const container = this.preview?.querySelector('.video-preview-actions');
        if (!container) return;

        container.innerHTML = `
            <div class="titles-result">
                <div class="titles-header">
                    <span class="titles-label">
                        <span class="material-icons">auto_awesome</span>
                        Títulos sugeridos pela IA
                    </span>
                    <span class="titles-count">${titles.length} títulos</span>
                </div>
                <ul class="titles-list">
                    ${titles.map((t, i) => `
                        <li class="title-item">
                            <span class="title-number">${i + 1}</span>
                            <span class="title-text">${this._escapeHtml(t)}</span>
                            <button class="title-copy-btn" data-title="${this._escapeHtml(t)}">
                                <span class="material-icons">content_copy</span>
                            </button>
                        </li>
                    `).join('')}
                </ul>
                <div class="titles-actions">
                    <button class="btn btn-outline btn-sm" id="refresh-titles-btn">
                        <span class="material-icons">refresh</span>
                        Gerar Novos
                    </button>
                    <button class="btn btn-primary btn-sm" id="use-titles-btn">
                        <span class="material-icons">check</span>
                        Usar Títulos
                    </button>
                </div>
            </div>
        `;

        container.querySelector('#refresh-titles-btn')?.addEventListener('click', this.handleGenerateTitles);

        container.querySelectorAll('.title-copy-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const title = btn.dataset.title;
                this._copyToClipboard(title);
                btn.querySelector('.material-icons').textContent = 'check';
                setTimeout(() => {
                    btn.querySelector('.material-icons').textContent = 'content_copy';
                }, 2000);
            });
        });

        container.querySelector('#use-titles-btn')?.addEventListener('click', () => {
            const titlesList = this.state.titles;
            alert(`✅ ${titlesList.length} títulos prontos!\n\n${titlesList.map((t, i) => `${i+1}. ${t}`).join('\n')}`);
        });
    }

    showTitlesError(msg) {
        const container = this.preview?.querySelector('.video-preview-actions');
        if (!container) return;

        container.innerHTML = `
            <div class="titles-error">
                <span class="material-icons error-icon">error_outline</span>
                <div class="titles-error-content">
                    <span class="error-message">${this._escapeHtml(msg)}</span>
                    <small>Tente novamente</small>
                </div>
                <button class="btn btn-outline btn-sm" id="retry-titles-btn">
                    <span class="material-icons">refresh</span>
                    Tentar Novamente
                </button>
            </div>
        `;

        container.querySelector('#retry-titles-btn')?.addEventListener('click', this.handleGenerateTitles);
    }

    // ──────────────────────────────────────────────────────────────
    //  UTILS
    // ──────────────────────────────────────────────────────────────

    _formatDuration(seconds) {
        if (!seconds || seconds <= 0) return '00:00';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    _formatNumber(num) {
        if (!num || num <= 0) return '0';
        if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
        if (num >= 1_000) return (num / 1_000).toFixed(1) + 'K';
        return num.toString();
    }

    _escapeHtml(text) {
        if (!text) return '';
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    _truncateText(text, max = 120) {
        if (!text || text.length <= max) return text;
        return text.substring(0, max) + '...';
    }

    _copyToClipboard(text) {
        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(text).catch(() => this._fallbackCopy(text));
        } else {
            this._fallbackCopy(text);
        }
    }

    _fallbackCopy(text) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (e) { console.warn('Erro ao copiar:', e); }
        document.body.removeChild(ta);
    }

    // ──────────────────────────────────────────────────────────────
    //  MÉTODOS PÚBLICOS
    // ──────────────────────────────────────────────────────────────

    getTaskId() {
        return this.state.taskId;
    }

    getJobId() {
        return this.state.jobId;
    }

    getStatus(taskId) {
        return this._getStatus(taskId);
    }

    connectStatusStream(taskId, onUpdate, onComplete) {
        return this._connectStatusStream(taskId, onUpdate, onComplete);
    }

    getSettings() {
        return { ...this.state.settings };
    }
}

// ──────────────────────────────────────────────────────────────
//  INIT
// ──────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 [NewProject] Inicializando...');
    window.newProject = new NewProjectManager({
        apiBaseUrl: 'http://localhost:8000'
    });
    console.log('✅ [NewProject] Pronto!');
});