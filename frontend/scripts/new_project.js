/**
 * ═══════════════════════════════════════════════════════════
 *  NEW PROJECT — Clip Engine
 *  Gerencia a página de novo projeto
 * ═══════════════════════════════════════════════════════════
 * 
 *  Funcionalidades:
 *  - Buscar informações do vídeo via API (/api/info)
 *  - Exibir preview com título, duração, canal e views
 *  - Gerar títulos virais via IA (/api/info/titles)
 *  - Gerenciar estado de loading/erro/sucesso
 *  - Interface totalmente integrada com a DOM
 * ═══════════════════════════════════════════════════════════
 */

class NewProjectManager {
    /**
     * Construtor da classe
     * @param {Object} config - Configurações do gerenciador
     * @param {string} config.apiBaseUrl - URL base da API
     * @param {string} config.inputSelector - Seletor do campo de input URL
     * @param {string} config.buttonSelector - Seletor do botão de busca
     * @param {string} config.previewSelector - Seletor do container de preview
     */
    constructor(config = {}) {
        // ── Configurações padrão ──────────────────────────
        this.config = {
            apiBaseUrl: config.apiBaseUrl || 'http://localhost:8000',
            inputSelector: config.inputSelector || '#video-url-input',
            buttonSelector: config.buttonSelector || '#search-info-btn',
            previewSelector: config.previewSelector || '.video-preview-placeholder',
            titlesButtonSelector: '#fetch-titles-btn',
            refreshTitlesSelector: '#refresh-titles-btn',
            retryTitlesSelector: '#retry-titles-btn'
        };

        // ── Referências DOM ──────────────────────────────
        this.input = document.querySelector(this.config.inputSelector);
        this.button = document.querySelector(this.config.buttonSelector);
        this.preview = document.querySelector(this.config.previewSelector);

        // ── Estado interno ───────────────────────────────
        this.state = {
            isLoading: false,
            isGeneratingTitles: false,
            currentUrl: '',
            videoInfo: null,
            titles: null,
            hasTitles: false
        };

        // ── Bind dos métodos ─────────────────────────────
        this.handleSearch = this.handleSearch.bind(this);
        this.handleKeyPress = this.handleKeyPress.bind(this);
        this.handleGenerateTitles = this.handleGenerateTitles.bind(this);

        // ── Inicialização ────────────────────────────────
        this.init();
    }

    /**
     * Inicializa o gerenciador: configura event listeners e estado inicial
     */
    init() {
        console.log('🎬 [NewProjectManager] Inicializando...');

        // Verifica se os elementos necessários existem
        if (!this.input) {
            console.warn('⚠️ [NewProjectManager] Campo de input não encontrado. Usando .input-field como fallback');
            this.input = document.querySelector('.input-field');
        }

        if (!this.button) {
            console.warn('⚠️ [NewProjectManager] Botão de busca não encontrado. Usando .source-input .btn-primary como fallback');
            this.button = document.querySelector('.source-input .btn-primary');
        }

        if (!this.preview) {
            console.warn('⚠️ [NewProjectManager] Preview não encontrado. Usando .video-preview-placeholder como fallback');
            this.preview = document.querySelector('.video-preview-placeholder');
        }

        // Configura os event listeners
        if (this.button) {
            this.button.addEventListener('click', this.handleSearch);
            console.log('✅ [NewProjectManager] Event listener adicionado ao botão de busca');
        }

        if (this.input) {
            this.input.addEventListener('keypress', this.handleKeyPress);
            console.log('✅ [NewProjectManager] Event listener adicionado ao input (Enter)');
        }

        // Estado inicial: limpa preview
        this.showEmptyState();

        console.log('✅ [NewProjectManager] Inicializado com sucesso!');
    }

    // ──────────────────────────────────────────────────────────────
    //  EVENT HANDLERS
    // ──────────────────────────────────────────────────────────────

    /**
     * Manipula o evento de pressionar tecla no input
     * @param {KeyboardEvent} event 
     */
    handleKeyPress(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            this.handleSearch();
        }
    }

    /**
     * Manipula o clique no botão de busca
     */
    async handleSearch() {
        // Previne múltiplas requisições simultâneas
        if (this.state.isLoading) {
            console.log('⏳ [NewProjectManager] Já existe uma requisição em andamento');
            return;
        }

        // Obtém a URL do input
        const url = this.input?.value?.trim();
        if (!url) {
            this.showError('Por favor, cole uma URL do YouTube.');
            return;
        }

        // Valida se é uma URL do YouTube
        if (!this.isYouTubeUrl(url)) {
            this.showError('URL inválida. Insira uma URL do YouTube válida.');
            return;
        }

        console.log(`🔍 [NewProjectManager] Buscando informações para: ${url}`);

        // Atualiza estado
        this.state.currentUrl = url;
        this.state.isLoading = true;
        this.state.hasTitles = false;
        this.state.titles = null;

        // Mostra estado de loading
        this.showLoading();

        try {
            // Busca informações do vídeo
            const videoInfo = await this.fetchVideoInfo(url);
            
            // Armazena no estado
            this.state.videoInfo = videoInfo;

            // Atualiza o preview com as informações
            this.showVideoPreview(videoInfo);

            console.log('✅ [NewProjectManager] Informações carregadas com sucesso!', videoInfo);

        } catch (error) {
            console.error('❌ [NewProjectManager] Erro ao buscar informações:', error);
            this.showError(error.message || 'Erro ao buscar informações do vídeo.');
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Gera títulos via IA e exibe no preview
     */
    async handleGenerateTitles() {
        if (this.state.isGeneratingTitles) {
            console.log('⏳ [NewProjectManager] Já está gerando títulos');
            return;
        }

        if (!this.state.currentUrl) {
            this.showError('Nenhum vídeo carregado. Busque as informações primeiro.');
            return;
        }

        this.state.isGeneratingTitles = true;

        // Mostra loading nos títulos
        const titlesContainer = this.preview?.querySelector('.video-preview-actions');
        if (titlesContainer) {
            titlesContainer.innerHTML = `
                <div class="titles-loading">
                    <span class="material-icons loading-icon spin">sync</span>
                    <span>Gerando títulos com IA...</span>
                    <small>Isso pode levar alguns segundos</small>
                </div>
            `;
        }

        try {
            const result = await this.fetchTitles(this.state.currentUrl, 5);
            
            if (result.titles && result.titles.length > 0) {
                this.state.titles = result.titles;
                this.state.hasTitles = true;
                this.showTitles(result.titles);
            } else {
                this.showTitlesError('Não foi possível gerar títulos. Tente novamente.');
            }
        } catch (error) {
            console.error('❌ [NewProjectManager] Erro ao gerar títulos:', error);
            this.showTitlesError(error.message || 'Erro ao gerar títulos.');
        } finally {
            this.state.isGeneratingTitles = false;
        }
    }

    // ──────────────────────────────────────────────────────────────
    //  API CALLS
    // ──────────────────────────────────────────────────────────────

    /**
     * Busca informações do vídeo na API
     * @param {string} url 
     * @returns {Promise<Object>}
     */
    async fetchVideoInfo(url) {
        const endpoint = `${this.config.apiBaseUrl}/api/info`;
        
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Erro ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (!data || typeof data !== 'object') {
                throw new Error('Resposta da API inválida');
            }

            return data;

        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Não foi possível conectar à API. Verifique se o servidor está rodando.');
            }
            throw error;
        }
    }

    /**
     * Busca títulos via IA na API
     * @param {string} url 
     * @param {number} count 
     * @returns {Promise<Object>}
     */
    async fetchTitles(url, count = 5) {
        const endpoint = `${this.config.apiBaseUrl}/api/info/titles`;
        
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url, count })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Erro ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            // Verifica diferentes formatos de retorno
            let titles = [];
            if (data.titles) {
                titles = data.titles;
            } else if (data.data && data.data.titles) {
                titles = data.data.titles;
            } else if (Array.isArray(data)) {
                titles = data;
            }

            this.state.titles = titles;
            return { titles, count: titles.length, video_title: data.video_title || '' };

        } catch (error) {
            console.warn('⚠️ [NewProjectManager] Erro ao buscar títulos:', error);
            return { titles: [], error: error.message };
        }
    }

    // ──────────────────────────────────────────────────────────────
    //  VALIDAÇÃO
    // ──────────────────────────────────────────────────────────────

    /**
     * Verifica se a URL é do YouTube
     * @param {string} url 
     * @returns {boolean}
     */
    isYouTubeUrl(url) {
        const patterns = [
            /(?:youtube\.com\/watch\?v=)([\w-]+)/,
            /(?:youtu\.be\/)([\w-]+)/,
            /(?:youtube\.com\/shorts\/)([\w-]+)/,
            /(?:youtube\.com\/embed\/)([\w-]+)/
        ];
        return patterns.some(pattern => pattern.test(url));
    }

    /**
     * Extrai o ID do vídeo do YouTube
     * @param {string} url 
     * @returns {string|null}
     */
    extractVideoId(url) {
        const patterns = [
            /(?:youtube\.com\/watch\?v=)([\w-]+)/,
            /(?:youtu\.be\/)([\w-]+)/,
            /(?:youtube\.com\/shorts\/)([\w-]+)/,
            /(?:youtube\.com\/embed\/)([\w-]+)/
        ];
        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match) return match[1];
        }
        return null;
    }

    // ──────────────────────────────────────────────────────────────
    //  UI RENDER
    // ──────────────────────────────────────────────────────────────

    /**
     * Mostra o estado vazio no preview
     */
    showEmptyState() {
        if (!this.preview) return;

        this.preview.className = 'video-preview-placeholder';
        this.preview.innerHTML = `
            <span class="material-icons preview-icon">play_circle_outline</span>
            <span>Nenhum vídeo carregado</span>
            <small>Cole a URL para ver as informações</small>
        `;
    }

    /**
     * Mostra o estado de loading no preview
     */
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

    /**
     * Mostra erro no preview
     * @param {string} message 
     */
    showError(message) {
        if (!this.preview) return;

        this.preview.className = 'video-preview-placeholder error';
        this.preview.innerHTML = `
            <span class="material-icons preview-icon error-icon">error_outline</span>
            <span class="error-message">${this.escapeHtml(message)}</span>
            <small>Tente novamente com uma URL válida</small>
        `;
    }

    /**
     * Mostra o preview do vídeo com as informações
     * @param {Object} info 
     */
    showVideoPreview(info) {
        if (!this.preview) return;

        this.preview.className = 'video-preview-placeholder success';

        // Formata duração (segundos -> MM:SS)
        const duration = this.formatDuration(info.duration || 0);

        // Formata views (ex: 1.2M, 34K)
        const views = this.formatNumber(info.view_count || 0);

        // Gera thumbnail (se tiver)
        const thumbnailHtml = info.thumbnail ? 
            `<img src="${this.escapeHtml(info.thumbnail)}" alt="Thumbnail" class="video-thumbnail-img" />` :
            `<span class="material-icons preview-thumbnail-icon">play_circle_filled</span>`;

        this.preview.innerHTML = `
            <div class="video-preview-content">
                <div class="video-preview-thumbnail">
                    ${thumbnailHtml}
                    <span class="video-duration">${duration}</span>
                </div>
                <div class="video-preview-details">
                    <h3 class="video-title">${this.escapeHtml(info.title || 'Sem título')}</h3>
                    <div class="video-meta">
                        <span class="video-channel">
                            <span class="material-icons meta-icon">person</span>
                            ${this.escapeHtml(info.uploader || 'Desconhecido')}
                        </span>
                        <span class="video-views">
                            <span class="material-icons meta-icon">visibility</span>
                            ${views} visualizações
                        </span>
                    </div>
                    ${info.description ? `
                        <p class="video-description">${this.truncateText(this.escapeHtml(info.description), 120)}</p>
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

        // Adiciona event listener para o botão de gerar títulos
        const titlesBtn = this.preview.querySelector('#fetch-titles-btn');
        if (titlesBtn) {
            titlesBtn.addEventListener('click', this.handleGenerateTitles);
        }
    }

    /**
     * Exibe os títulos gerados pela IA
     * @param {string[]} titles 
     */
    showTitles(titles) {
        const actions = this.preview?.querySelector('.video-preview-actions');
        if (!actions) return;

        actions.innerHTML = `
            <div class="titles-result">
                <div class="titles-header">
                    <span class="titles-label">
                        <span class="material-icons">auto_awesome</span>
                        Títulos sugeridos pela IA
                    </span>
                    <span class="titles-count">${titles.length} títulos</span>
                </div>
                <ul class="titles-list">
                    ${titles.map((title, index) => `
                        <li class="title-item">
                            <span class="title-number">${index + 1}</span>
                            <span class="title-text">${this.escapeHtml(title)}</span>
                            <button class="title-copy-btn" data-title="${this.escapeHtml(title)}">
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

        // Adiciona event listener para gerar novos títulos
        const refreshBtn = actions.querySelector('#refresh-titles-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', this.handleGenerateTitles);
        }

        // Adiciona event listener para copiar títulos
        const copyBtns = actions.querySelectorAll('.title-copy-btn');
        copyBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const title = btn.getAttribute('data-title');
                this.copyToClipboard(title);
                btn.querySelector('.material-icons').textContent = 'check';
                setTimeout(() => {
                    btn.querySelector('.material-icons').textContent = 'content_copy';
                }, 2000);
            });
        });

        // Adiciona event listener para usar títulos
        const useBtn = actions.querySelector('#use-titles-btn');
        if (useBtn) {
            useBtn.addEventListener('click', () => {
                this.useTitles(titles);
            });
        }
    }

    /**
     * Mostra erro na geração de títulos
     * @param {string} message 
     */
    showTitlesError(message) {
        const actions = this.preview?.querySelector('.video-preview-actions');
        if (!actions) return;

        actions.innerHTML = `
            <div class="titles-error">
                <span class="material-icons error-icon">error_outline</span>
                <div class="titles-error-content">
                    <span class="error-message">${this.escapeHtml(message)}</span>
                    <small>Tente novamente ou verifique sua conexão</small>
                </div>
                <button class="btn btn-outline btn-sm" id="retry-titles-btn">
                    <span class="material-icons">refresh</span>
                    Tentar Novamente
                </button>
            </div>
        `;

        const retryBtn = actions.querySelector('#retry-titles-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', this.handleGenerateTitles);
        }
    }

    // ──────────────────────────────────────────────────────────────
    //  UTILITÁRIOS
    // ──────────────────────────────────────────────────────────────

    /**
     * Formata duração em segundos para MM:SS
     * @param {number} seconds 
     * @returns {string}
     */
    formatDuration(seconds) {
        if (!seconds || seconds <= 0) return '00:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    /**
     * Formata números grandes (ex: 1234567 -> 1.2M)
     * @param {number} num 
     * @returns {string}
     */
    formatNumber(num) {
        if (!num || num <= 0) return '0';
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    /**
     * Escapa caracteres HTML para prevenir XSS
     * @param {string} text 
     * @returns {string}
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Trunca texto para um tamanho máximo
     * @param {string} text 
     * @param {number} maxLength 
     * @returns {string}
     */
    truncateText(text, maxLength = 120) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    /**
     * Copia texto para a área de transferência
     * @param {string} text 
     */
    copyToClipboard(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).catch(() => {
                this.fallbackCopyToClipboard(text);
            });
        } else {
            this.fallbackCopyToClipboard(text);
        }
    }

    /**
     * Fallback para copiar texto (usando textarea)
     * @param {string} text 
     */
    fallbackCopyToClipboard(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
        } catch (err) {
            console.warn('Erro ao copiar:', err);
        }
        document.body.removeChild(textarea);
    }

    /**
     * Usa os títulos gerados (callback)
     * @param {string[]} titles 
     */
    useTitles(titles) {
        // Aqui você pode implementar a lógica para usar os títulos
        // Por exemplo: preencher um campo de título ou salvar no estado
        console.log('📝 Títulos selecionados:', titles);
        alert(`✅ ${titles.length} títulos prontos para uso!\n\nPrimeiro título: "${titles[0]}"`);
    }
}

// ──────────────────────────────────────────────────────────────
//  CSS ANIMATIONS (adicionar ao main.css)
// ──────────────────────────────────────────────────────────────

/*
.spin {
    animation: spin 1s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.titles-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.title-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--bg-primary);
    margin-bottom: 6px;
    transition: background 0.2s;
}

.title-item:hover {
    background: var(--border);
}

.title-number {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-light);
    min-width: 24px;
}

.title-text {
    flex: 1;
    font-size: 0.9rem;
}

.title-copy-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-light);
    padding: 4px;
    border-radius: 4px;
    transition: color 0.2s;
}

.title-copy-btn:hover {
    color: var(--primary);
}

.titles-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.titles-count {
    font-size: 0.75rem;
    color: var(--text-light);
    background: var(--bg-primary);
    padding: 2px 10px;
    border-radius: 12px;
}

.titles-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
}

.titles-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 16px;
    color: var(--text-secondary);
}

.titles-loading .loading-icon {
    font-size: 32px;
    color: var(--primary);
}

.titles-error {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: #FFEBEE;
    border-radius: 8px;
}

.titles-error-content {
    flex: 1;
}

.titles-error .error-message {
    display: block;
    color: var(--secondary);
    font-weight: 500;
}

.titles-error small {
    color: var(--text-secondary);
}

.video-preview-content {
    display: flex;
    gap: 16px;
    padding: 12px;
}

.video-preview-thumbnail {
    position: relative;
    width: 160px;
    height: 90px;
    border-radius: 8px;
    overflow: hidden;
    background: #2A2A4E;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}

.video-thumbnail-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.video-duration {
    position: absolute;
    bottom: 4px;
    right: 4px;
    background: rgba(0,0,0,0.8);
    color: #fff;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
}

.video-preview-details {
    flex: 1;
    min-width: 0;
}

.video-title {
    font-size: 1rem;
    font-weight: 600;
    margin: 0 0 4px 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.video-meta {
    display: flex;
    gap: 16px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 4px;
}

.video-channel, .video-views {
    display: flex;
    align-items: center;
    gap: 4px;
}

.meta-icon {
    font-size: 16px;
}

.video-description {
    font-size: 0.8rem;
    color: var(--text-light);
    margin: 4px 0 0 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.video-preview-actions {
    padding: 12px;
    border-top: 1px solid var(--border);
}
*/

// ──────────────────────────────────────────────────────────────
//  INICIALIZAÇÃO — Aguarda o DOM estar pronto
// ──────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 [NewProject] Inicializando página...');

    // Cria uma instância do gerenciador
    const manager = new NewProjectManager({
        apiBaseUrl: 'http://localhost:8000',
        inputSelector: '#video-url-input',
        buttonSelector: '#search-info-btn',
        previewSelector: '.video-preview-placeholder'
    });

    // Torna o manager acessível globalmente para debugging
    window.newProjectManager = manager;

    console.log('✅ [NewProject] Página inicializada!');
});