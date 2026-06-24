// ═══════════════════════════════════════════════════════════
// CLIP ENGINE — JavaScript (Estrutura apenas)
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Clip Engine — Frontend carregado');

    // ── Mobile Toggle ──────────────────────────────────────
    const toggle = document.querySelector('.mobile-toggle');
    if (toggle) {
        toggle.addEventListener('click', function() {
            const nav = document.querySelector('.nav-links');
            if (nav) {
                nav.style.display = nav.style.display === 'flex' ? 'none' : 'flex';
            }
        });
    }

    // ── Source Tabs ────────────────────────────────────────
    const tabs = document.querySelectorAll('.source-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // ── Range Input ────────────────────────────────────────
    const range = document.querySelector('.range-input');
    if (range) {
        range.addEventListener('input', function() {
            const value = document.querySelector('.range-value');
            if (value) {
                value.textContent = this.value;
            }
        });
    }

    // ── Button Groups ──────────────────────────────────────
    const btnGroups = document.querySelectorAll('.btn-group, .toggle-group');
    btnGroups.forEach(group => {
        const btns = group.querySelectorAll('.btn-option');
        btns.forEach(btn => {
            btn.addEventListener('click', function() {
                btns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            });
        });
    });

    // ── Color Picker ───────────────────────────────────────
    const colorOptions = document.querySelectorAll('.color-option');
    colorOptions.forEach(opt => {
        opt.addEventListener('click', function() {
            colorOptions.forEach(o => o.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // ── Filter Buttons ─────────────────────────────────────
    const filters = document.querySelectorAll('.filter-btn');
    filters.forEach(filter => {
        filter.addEventListener('click', function() {
            filters.forEach(f => f.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // ── Gallery Play Button ────────────────────────────────
    const playBtns = document.querySelectorAll('.gallery-play, .play-overlay');
    playBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            alert('🎬 Preview do clipe (em breve)');
        });
    });

    // ── Download Buttons ───────────────────────────────────
    const downloadBtns = document.querySelectorAll('.gallery-actions .btn-primary');
    downloadBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            alert('⬇️ Download iniciado! (em breve)');
        });
    });

    // ── Processing Logs — Simular updates ────────────────
    const logContainer = document.querySelector('.processing-logs');
    if (logContainer) {
        const logs = [
            '📥 Download concluído (14.2 MB)',
            '🔄 Processando tracking de rosto...',
            '🎯 Rosto detectado em 342 quadros',
            '✂️ Cortando clipes...'
        ];
        let logIndex = 0;
        setInterval(() => {
            if (logIndex < logs.length) {
                const newLog = document.createElement('div');
                newLog.className = 'log-line active';
                newLog.textContent = logs[logIndex];
                logContainer.appendChild(newLog);
                logIndex++;
            }
        }, 2000);
    }

    // ── Progress Bar ───────────────────────────────────────
    const progressFill = document.querySelector('.progress-fill');
    if (progressFill) {
        let progress = 0;
        setInterval(() => {
            if (progress < 100) {
                progress += Math.random() * 5;
                if (progress > 100) progress = 100;
                progressFill.style.width = progress + '%';
                const label = document.querySelector('.progress-label');
                if (label) {
                    label.textContent = Math.round(progress) + '% — Processando...';
                }
            }
        }, 1500);
    }

    // ── Redirects simulados ───────────────────────────────
    document.querySelectorAll('.sidebar-nav a').forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') {
                e.preventDefault();
                console.log('🔗 Navegando para:', this.textContent.trim());
                alert('🚀 Navegação para "' + this.textContent.trim() + '" (em breve)');
            }
        });
    });

    // ── Botão Processar ─────────────────────────────────────
    const processBtn = document.querySelector('.submit-section .btn-primary');
    if (processBtn) {
        processBtn.addEventListener('click', function() {
            alert('🚀 Processamento iniciado! Redirecionando para status...');
            // Simular redirecionamento
            window.location.href = 'processing.html';
        });
    }

    // ── Botão Novo Projeto ─────────────────────────────────
    const newProjectBtns = document.querySelectorAll('.header-right .btn-primary, .hero-actions .btn-primary');
    newProjectBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            alert('🚀 Redirecionando para Novo Projeto...');
            window.location.href = 'new-project.html';
        });
    });

    // ── Botão Ver Galeria ──────────────────────────────────
    const galleryBtns = document.querySelectorAll('.processing-actions .btn-outline');
    galleryBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            alert('📸 Redirecionando para Galeria...');
            window.location.href = 'gallery.html';
        });
    });

    console.log('✅ Clip Engine — Interações configuradas');
});