/**
 * Evolars Angola - Módulo de Aprendizado Offline & Sincronização
 * Otimizado para conexões instáveis e economia de dados móveis em Angola.
 */

(function () {
  'use strict';

  const DB_NAME = 'EvolarsAngolaOffline';
  const DB_VERSION = 1;
  const COURSES_CACHE = 'evolars-angola-courses-v1';

  // 1. Registro do Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then((reg) => console.log('[Evolars Offline] ServiceWorker ativo:', reg.scope))
        .catch((err) => console.warn('[Evolars Offline] Erro no ServiceWorker:', err));
    });
  }

  // 2. Inicialização do IndexedDB
  function openDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('courses')) {
          db.createObjectStore('courses', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('slides')) {
          const slideStore = db.createObjectStore('slides', { keyPath: 'id' });
          slideStore.createIndex('channel_id', 'channel_id', { unique: false });
        }
        if (!db.objectStoreNames.contains('sync_queue')) {
          db.createObjectStore('sync_queue', { autoIncrement: true });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // 3. Monitoramento de Conectividade
  function updateNetworkStatus() {
    const statusEl = document.getElementById('evolars-network-status');
    const isOnline = navigator.onLine;

    if (statusEl) {
      if (isOnline) {
        statusEl.className = 'evolars-status-pill evolars-status-online';
        statusEl.innerHTML = '<span class="status-dot"></span><span>Online</span>';
      } else {
        statusEl.className = 'evolars-status-pill evolars-status-offline';
        statusEl.innerHTML = '<span class="status-dot"></span><span>Modo Offline (Zero Dados)</span>';
      }
    }

    if (isOnline) {
      syncOfflineProgress();
    }
  }

  window.addEventListener('online', updateNetworkStatus);
  window.addEventListener('offline', updateNetworkStatus);

  // 4. Sincronização de Progresso
  async function syncOfflineProgress() {
    try {
      const db = await openDB();
      const tx = db.transaction('sync_queue', 'readonly');
      const store = tx.objectStore('sync_queue');
      const getAllReq = store.getAll();

      getAllReq.onsuccess = async () => {
        const queue = getAllReq.result;
        if (!queue || queue.length === 0) return;

        const slideIds = [...new Set(queue.map((item) => item.slide_id))];

        try {
          const response = await fetch('/slides/sync_progress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { slide_ids: slideIds } }),
          });
          const data = await response.json();

          if (data && !data.error) {
            // Limpar fila
            const clearTx = db.transaction('sync_queue', 'readwrite');
            clearTx.objectStore('sync_queue').clear();
            console.log('[Evolars Offline] Progresso sincronizado com sucesso:', slideIds.length, 'lições');
          }
        } catch (err) {
          console.warn('[Evolars Offline] Falha ao sincronizar agora, tentando na próxima reconexão:', err);
        }
      };
    } catch (e) {
      console.warn('[Evolars Offline] Erro ao verificar fila de sincronização:', e);
    }
  }

  // Marcar lição concluída localmente
  window.evolarsMarkSlideCompleted = async function (slideId) {
    try {
      const db = await openDB();
      const tx = db.transaction('sync_queue', 'readwrite');
      tx.objectStore('sync_queue').add({ slide_id: slideId, completed_at: new Date().toISOString() });

      if (navigator.onLine) {
        syncOfflineProgress();
      } else {
        alert('Lição marcada como concluída! Seu progresso foi salvo offline e será sincronizado quando houver internet.');
      }
    } catch (err) {
      console.error('[Evolars Offline] Erro ao registrar conclusão offline:', err);
    }
  };

  // 5. Download de Curso para Acesso Offline
  window.evolarsDownloadCourseOffline = async function (channelId, btnElement) {
    channelId = parseInt(channelId, 10);
    if (!btnElement) btnElement = document.querySelector(`[data-channel-id="${channelId}"]`);

    const originalText = btnElement ? btnElement.innerHTML : '';
    if (btnElement) {
      btnElement.disabled = true;
      btnElement.innerHTML = '<span class="fa fa-spinner fa-spin me-1"></span> Preparando download...';
    }

    try {
      // Obter manifesto do curso
      const resp = await fetch(`/slides/channel/${channelId}/offline_manifest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
      });
      const resJson = await resp.json();
      const manifest = resJson.result;

      if (manifest && manifest.error === 'login_required') {
        window.location.href = manifest.redirect || `/web/login?redirect=${encodeURIComponent(window.location.pathname)}`;
        return;
      }

      if (!manifest || !manifest.slides) {
        throw new Error(manifest?.error || 'Não foi possível obter os materiais do curso.');
      }

      const total = manifest.slides.length;
      let downloaded = 0;
      let totalBytes = 0;

      const cache = await caches.open(COURSES_CACHE);
      const appCache = await caches.open('evolars-angola-shell-v1');
      const db = await openDB();

      // Pré-cache da página do curso para navegação offline
      try {
        const pageResp = await fetch(`/slides/${channelId}`);
        if (pageResp.ok) {
          await appCache.put(`/slides/${channelId}`, pageResp.clone());
        }
      } catch (pageErr) {
        console.warn('[Evolars Offline] Aviso: Não foi possível pré-cachear página do curso:', pageErr);
      }

      for (const slide of manifest.slides) {
        if (btnElement) {
          const percent = Math.round((downloaded / total) * 100);
          btnElement.innerHTML = `<span class="fa fa-arrow-down me-1"></span> Baixando ${downloaded + 1}/${total} (${percent}%)...`;
        }

        try {
          const pdfResp = await fetch(slide.pdf_url);
          if (pdfResp.ok) {
            const blob = await pdfResp.blob();
            totalBytes += blob.size;
            // Salvar no CacheStorage
            await cache.put(slide.pdf_url, new Response(blob, {
              headers: { 'Content-Type': 'application/pdf', 'Content-Length': blob.size }
            }));

            // Salvar metadados no IndexedDB
            const slideTx = db.transaction('slides', 'readwrite');
            slideTx.objectStore('slides').put({
              id: parseInt(slide.id, 10),
              channel_id: channelId,
              name: slide.name,
              sequence: slide.sequence,
              pdf_url: slide.pdf_url,
              size: blob.size,
            });
          }
        } catch (fErr) {
          console.warn('[Evolars Offline] Erro ao baixar slide:', slide.name, fErr);
        }
        downloaded++;
      }

      // Salvar metadados do curso
      const courseTx = db.transaction('courses', 'readwrite');
      const mbSize = (totalBytes / (1024 * 1024)).toFixed(1);
      courseTx.objectStore('courses').put({
        id: channelId,
        name: manifest.name,
        description: manifest.description,
        total_slides: total,
        size_mb: mbSize,
        saved_at: new Date().toLocaleDateString('pt-AO'),
      });

      if (btnElement) {
        btnElement.disabled = false;
        btnElement.className = 'btn btn-success btn-sm';
        btnElement.innerHTML = `<span class="fa fa-check-circle me-1"></span> Salvo Offline (${mbSize} MB)`;
      }

      alert(`Sucesso! O curso "${manifest.name}" foi salvo localmente (${mbSize} MB). Agora você pode estudá-lo mesmo sem conexão!`);
    } catch (err) {
      console.error('[Evolars Offline] Erro no download do curso:', err);
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.innerHTML = originalText || 'Tentar Baixar Novamente';
      }
      alert('Houve uma falha durante o download. Verifique sua conexão e tente novamente.');
    }
  };

  // 6. Remoção de Cache do Curso
  window.evolarsRemoveCourseOffline = async function (channelId) {
    channelId = parseInt(channelId, 10);
    if (!confirm('Deseja remover este curso do armazenamento offline do seu aparelho?')) return;

    try {
      const db = await openDB();
      const tx = db.transaction(['courses', 'slides'], 'readwrite');
      tx.objectStore('courses').delete(channelId);
      tx.objectStore('courses').delete(String(channelId));

      const slideStore = tx.objectStore('slides');
      const allReq = slideStore.getAll();
      allReq.onsuccess = () => {
        const slides = allReq.result || [];
        for (const s of slides) {
          if (parseInt(s.channel_id, 10) === channelId) {
            slideStore.delete(s.id);
          }
        }
      };

      tx.oncomplete = () => {
        alert('Curso removido da memória do aparelho com sucesso.');
        renderOfflineLibrary();
      };
    } catch (err) {
      console.error('[Evolars Offline] Erro ao remover curso:', err);
    }
  };

  // 7. Expansão/Visualização das Apostilas do Curso Salvo
  window.evolarsToggleCourseSlides = async function (channelId) {
    channelId = parseInt(channelId, 10);
    const target = document.getElementById(`offline-slides-list-${channelId}`);
    if (!target) return;

    if (!target.classList.contains('d-none')) {
      target.classList.add('d-none');
      return;
    }

    target.classList.remove('d-none');
    target.innerHTML = '<div class="py-2 text-center text-muted small"><span class="fa fa-spinner fa-spin me-1"></span> Carregando apostilas salvas...</div>';

    try {
      const db = await openDB();
      const tx = db.transaction('slides', 'readonly');
      const store = tx.objectStore('slides');
      const allReq = store.getAll();

      allReq.onsuccess = () => {
        const allSlides = allReq.result || [];
        const slides = allSlides.filter((s) => parseInt(s.channel_id, 10) === channelId);
        if (!slides.length) {
          target.innerHTML = '<div class="text-muted small py-2 text-center">Nenhuma apostila individual vinculada a este curso no aparelho.</div>';
          return;
        }

        slides.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
        let html = '<ul class="list-group list-group-flush mt-2">';
        for (const s of slides) {
          html += `
            <li class="list-group-item d-flex flex-column flex-sm-row justify-content-between align-items-start align-items-sm-center py-2 px-0 bg-transparent gap-2">
              <div class="d-flex align-items-center text-break me-2" style="max-width: 72%;">
                <i class="fa fa-file-pdf-o text-danger me-2" style="font-size: 1.1rem;"></i>
                <span class="fw-semibold" style="color: #0f172a; font-size: 0.9rem;">${s.name}</span>
              </div>
              <div class="d-flex gap-1 flex-shrink-0 align-self-end align-self-sm-center">
                <a href="${s.pdf_url}" target="_blank" class="btn btn-sm btn-primary py-1 px-2 fw-bold" style="background-color: #1d4ed8; border-color: #1d4ed8; font-size: 12px;">
                  <i class="fa fa-book me-1"></i> Ler PDF
                </a>
                <button type="button" class="btn btn-sm btn-outline-success py-1 px-2" style="font-size: 12px;" onclick="window.evolarsMarkSlideCompleted(${s.id})" title="Marcar como concluída">
                  <i class="fa fa-check"></i>
                </button>
              </div>
            </li>
          `;
        }
        html += '</ul>';
        target.innerHTML = html;
      };
      allReq.onerror = () => {
        target.innerHTML = '<div class="text-danger small py-2">Erro ao ler apostilas salvas.</div>';
      };
    } catch (err) {
      target.innerHTML = '<div class="text-danger small py-2">Falha ao acessar armazenamento offline.</div>';
    }
  };

  // 8. Pesquisa e Filtro em Tempo Real de Cursos Salvos
  window.evolarsFilterOfflineCourses = function (query) {
    const term = (query || '').toLowerCase().trim();
    const items = document.querySelectorAll('.evolars-offline-item');
    let visibleCount = 0;
    items.forEach((item) => {
      const card = item.querySelector('.evolars-offline-course-card');
      const title = (card ? card.getAttribute('data-course-name') : '') || '';
      if (!term || title.toLowerCase().includes(term)) {
        item.classList.remove('d-none');
        visibleCount++;
      } else {
        item.classList.add('d-none');
      }
    });

    let noResultsEl = document.getElementById('evolars-offline-search-no-results');
    if (term && visibleCount === 0) {
      if (!noResultsEl) {
        const container = document.getElementById('evolars-offline-library-list');
        noResultsEl = document.createElement('div');
        noResultsEl.id = 'evolars-offline-search-no-results';
        noResultsEl.className = 'col-12 text-center py-4';
        noResultsEl.innerHTML = `<p class="text-muted mb-0">Nenhum curso salvo encontrado para "<strong>${query}</strong>".</p>`;
        container.appendChild(noResultsEl);
      }
    } else if (noResultsEl) {
      noResultsEl.remove();
    }
  };

  // 9. Renderização da Biblioteca Offline em /slides/offline
  async function renderOfflineLibrary() {
    const container = document.getElementById('evolars-offline-library-list');
    if (!container) return;

    try {
      const db = await openDB();
      const tx = db.transaction('courses', 'readonly');
      const courses = await new Promise((resolve) => {
        const timer = setTimeout(() => resolve([]), 2000);
        const req = tx.objectStore('courses').getAll();
        req.onsuccess = () => {
          clearTimeout(timer);
          resolve(req.result || []);
        };
        req.onerror = () => {
          clearTimeout(timer);
          resolve([]);
        };
      });

      if (courses.length === 0) {
        container.innerHTML = `
          <div class="col-12 text-center py-5">
            <div class="mb-3"><span class="fa fa-folder-open-o fa-3x text-muted"></span></div>
            <h4 class="fw-bold" style="color: #0f172a;">Nenhum curso salvo offline ainda</h4>
            <p class="max-w-md mx-auto mb-4" style="color: #334155; font-size: 0.95rem; max-width: 500px;">
              Você pode salvar cursos completos com todas as apostilas em PDF direto no seu aparelho para estudar sem internet móvel.
            </p>
            <div class="p-3 rounded-3 mb-4 mx-auto text-start" style="background-color: #f8fafc; border: 1px solid #e2e8f0; max-width: 480px;">
              <div class="fw-bold mb-2" style="color: #0f172a; font-size: 0.9rem;"><i class="fa fa-info-circle text-primary me-1"></i> Como salvar um curso:</div>
              <ol class="mb-0 ps-3 small" style="color: #334155; line-height: 1.6;">
                <li>Navegue até qualquer curso no catálogo.</li>
                <li>Na barra lateral, clique em <strong>"Estudar Offline (Salvar no Aparelho)"</strong>.</li>
                <li>As apostilas em PDF serão salvas na memória local para leitura imediata.</li>
              </ol>
            </div>
            <a href="/slides/all" class="btn btn-primary fw-semibold px-4 py-2" style="background-color: #1d4ed8; border-color: #1d4ed8;">
              <i class="fa fa-book me-1"></i> Explorar Catálogo de Cursos
            </a>
          </div>
        `;
        return;
      }

      let html = '';
      for (const c of courses) {
        const id = parseInt(c.id, 10);
        html += `
          <div class="col-md-6 col-lg-4 mb-4 evolars-offline-item">
            <div class="card h-100 shadow-sm border evolars-offline-course-card" data-course-name="${(c.name || '').replace(/"/g, '&quot;')}">
              <div class="card-body d-flex flex-column justify-content-between p-4">
                <div>
                  <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="badge" style="background-color: #dcfce7; color: #14532d; border: 1px solid #86efac; font-weight: 700;">
                      <i class="fa fa-check-circle me-1"></i>Salvo Offline
                    </span>
                    <span class="badge" style="background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; font-weight: 600;">
                      ${c.size_mb || '0'} MB
                    </span>
                  </div>
                  <h5 class="card-title font-weight-bold mb-2" style="color: #0f172a;">${c.name}</h5>
                  <p class="small mb-3" style="color: #475569;">
                    <i class="fa fa-file-pdf-o text-danger me-1"></i>
                    ${c.total_slides || 'Várias'} apostilas disponíveis sem consumo de internet móvel.
                  </p>
                </div>
                <div class="pt-3 border-top mt-auto d-flex flex-wrap gap-2">
                  <button type="button" class="btn btn-primary btn-sm flex-grow-1 fw-bold" onclick="window.evolarsToggleCourseSlides(${id})">
                    <i class="fa fa-folder-open-o me-1"></i> Ver Apostilas
                  </button>
                  <a href="/slides/${id}" class="btn btn-outline-secondary btn-sm" title="Abrir página do curso">
                    <i class="fa fa-external-link"></i>
                  </a>
                  <button type="button" onclick="window.evolarsRemoveCourseOffline(${id})" class="btn btn-outline-danger btn-sm" title="Remover do aparelho para liberar espaço">
                    <i class="fa fa-trash"></i>
                  </button>
                </div>
                <div id="offline-slides-list-${id}" class="d-none mt-3 pt-3 border-top"></div>
              </div>
            </div>
          </div>
        `;
      }
      container.innerHTML = html;
    } catch (e) {
      console.warn('[Evolars Offline] Erro ao renderizar biblioteca offline:', e);
      container.innerHTML = `
        <div class="col-12 text-center py-4">
          <p class="text-danger mb-2">Não foi possível carregar os cursos offline neste momento.</p>
          <button type="button" class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
            <i class="fa fa-refresh me-1"></i> Tentar Novamente
          </button>
        </div>
      `;
    }
  }

  // 10. Suporte a clique suave em botões com âncora #channels
  document.addEventListener('click', (e) => {
    const anchor = e.target.closest('a[href="#channels"], a[href$="/slides#channels"]');
    if (anchor) {
      const target = document.getElementById('channels');
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
      } else if (!window.location.pathname.startsWith('/slides')) {
        window.location.href = '/slides#channels';
      }
    }
  });

  // 11. Inicialização Imediata e Resiliente
  function initEvolarsOffline() {
    updateNetworkStatus();
    renderOfflineLibrary();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEvolarsOffline);
  } else {
    initEvolarsOffline();
  }
})();
