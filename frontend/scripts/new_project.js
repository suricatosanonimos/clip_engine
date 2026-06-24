/**
 * ═══════════════════════════════════════════════════════════
 *  NEW PROJECT — Clip Engine
 *  Gerencia a página de novo projeto
 * ═══════════════════════════════════════════════════════════
 * 
 *  Rotas da API:
 *  - POST /api/info         → informações do vídeo
 *  - POST /api/info/titles  → gera títulos virais com IA
 *  - POST /api/video/process → inicia processamento do vídeo
 *  - GET  /api/status/{id}  → status do processamento
 * ═══════════════════════════════════════════════════════════
 */

class NewProjectManager {
    constructor(config = {}) {
        // ── Configurações ──────────────────────────────────
        this.config = {
            apiBaseUrl: config.apiBaseUrl || 'http://localhost:8000',
            inputSelector: '#video-url-input',
            buttonSelector: '#search-info-btn',
            previewSelector: '.video-preview-placeholder',
            processButtonSelector: '.submit-section .btn-primary'
        };

        // ── Endpoints da API ──────────────────────────────
        this.api = {
            videoInfo: `${this.config.apiBaseUrl}/api/info`,
            titles: `${this.config.apiBaseUrl}/api/info/titles`,
            process: `${this.config.apiBaseUrl}/api/video/process`,
            status: (taskId) => `${this.config.apiBaseUrl}/api/status/${taskId}`
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
            settings: {
                numClips: 3,
                clipDuration: 60,
                tracking: true,
                subtitles: true,
                subtitleColor: 'white'
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

        console.log('✅ [NewProjectManager] Inicializado!');
    }

    // ──────────────────────────────────────────────────────────────
    //  SETTINGS LISTENERS
    // ──────────────────────────────────────────────────────────────

    _setupSettingsListeners() {
        // Range de clipes
        const range = document.querySelector('.range-input');
        if (range) {
            range.addEventListener('input', (e) => {
                this.state.settings.numClips = parseInt(e.target.value);
                const display = document.querySelector('.range-value');
                if (display) display.textContent = this.state.settings.numClips;
            });
        }

        // Duração
        document.querySelectorAll('.setting-group .btn-group:first-child .btn-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.setting-group .btn-group:first-child .btn-option')
                    .forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.state.settings.clipDuration = parseInt(btn.textContent.replace('s', ''));
            });
        });

        // Tracking
        document.querySelectorAll('.setting-group .toggle-group:first-child .btn-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.setting-group .toggle-group:first-child .btn-option')
                    .forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.state.settings.tracking = btn.textContent.includes('Ativado');
            });
        });

        // Legendas
        document.querySelectorAll('.setting-group .toggle-group:nth-child(2) .btn-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.setting-group .toggle-group:nth-child(2) .btn-option')
                    .forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.state.settings.subtitles = btn.textContent.includes('Ativado');
            });
        });

        // Cores
        const colorMap = { '#FFFFFF': 'white', '#FFD93D': 'yellow', '#6C63FF': 'blue', '#6BCB77': 'green' };
        document.querySelectorAll('.color-option').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.color-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const bg = btn.style.backgroundColor || '#FFFFFF';
                this.state.settings.subtitleColor = colorMap[bg] || 'white';
            });
        });
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
                </div>
            `;
        }

        try {
            const result = await this._fetchTitles(this.state.currentUrl, 5);
            if (result.titles?.length) {
                this.state.titles = result.titles;
                this.showTitles(result.titles);
            } else {
                this.showTitlesError('Não foi possível gerar títulos.');
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

        const msg = `Processar "${this.state.videoInfo?.title || 'Vídeo'}"?\n\n` +
            `Clipes: ${this.state.settings.numClips}\n` +
            `Duração: ${this.state.settings.clipDuration}s\n` +
            `Tracking: ${this.state.settings.tracking ? 'Ativado' : 'Desativado'}\n` +
            `Legendas: ${this.state.settings.subtitles ? 'Ativado' : 'Desativado'}`;

        if (!confirm(msg)) return;

        this.state.isProcessing = true;

        if (this.processBtn) {
            this.processBtn.innerHTML = `<span class="material-icons spin">sync</span> Processando...`;
            this.processBtn.disabled = true;
        }

        try {
            const result = await this._processVideo(this.state.currentUrl);
            alert(`✅ Processamento iniciado!\nTask ID: ${result.task_id}`);
            window.location.href = `processing.html?task_id=${result.task_id}`;
        } catch (err) {
            alert(`❌ Erro: ${err.message || 'Erro desconhecido'}`);
        } finally {
            this.state.isProcessing = false;
            if (this.processBtn) {
                this.processBtn.innerHTML = `<span class="material-icons">play_arrow</span> Processar Vídeo`;
                this.processBtn.disabled = false;
            }
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

    async _processVideo(url) {
        const payload = {
            url: url,
            user_id: null,
            job_id: null,
            num_clips: this.state.settings.numClips,
            clip_duration: this.state.settings.clipDuration,
            tracking: this.state.settings.tracking,
            subtitles: this.state.settings.subtitles,
            source_type: 'youtube',
            cor_legenda: this.state.settings.subtitleColor
        };

        const res = await fetch(this.api.process, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ${res.status}`);
        }

        return res.json();
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

    _isYouTubeUrl(url) {
        return /(?:youtube\.com\/watch\?v=)([\w-]+)/.test(url) ||
               /(?:youtu\.be\/)([\w-]+)/.test(url) ||
               /(?:youtube\.com\/shorts\/)([\w-]+)/.test(url) ||
               /(?:youtube\.com\/embed\/)([\w-]+)/.test(url);
    }

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