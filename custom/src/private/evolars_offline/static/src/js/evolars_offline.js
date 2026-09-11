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

      if (!manifest || !manifest.slides) {
        throw new Error('Não foi possível obter os materiais do curso.');
      }

      const total = manifest.slides.length;
      let downloaded = 0;
      let totalBytes = 0;

      const cache = await caches.open(COURSES_CACHE);
      const db = await openDB();

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
              id: slide.id,
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
    if (!confirm('Deseja remover este curso do armazenamento offline do seu aparelho?')) return;

    try {
      const db = await openDB();
      const tx = db.transaction(['courses', 'slides'], 'readwrite');
      tx.objectStore('courses').delete(channelId);

      const slideStore = tx.objectStore('slides');
      const index = slideStore.index('channel_id');
      const req = index.getAllKeys(channelId);
      req.onsuccess = () => {
        req.result.forEach((key) => slideStore.delete(key));
      };

      alert('Curso removido da memória do aparelho com sucesso.');
      if (window.location.pathname === '/slides/offline') {
        window.location.reload();
      }
    } catch (err) {
      console.error('[Evolars Offline] Erro ao remover curso:', err);
    }
  };

  // 7. Renderização da Biblioteca Offline em /slides/offline
  async function renderOfflineLibrary() {
    const container = document.getElementById('evolars-offline-library-list');
    if (!container) return;

    try {
      const db = await openDB();
      const tx = db.transaction('courses', 'readonly');
      const courses = await new Promise((resolve) => {
        const req = tx.objectStore('courses').getAll();
        req.onsuccess = () => resolve(req.result || []);
      });

      if (courses.length === 0) {
        container.innerHTML = `
          <div class="col-12 text-center py-5">
            <div class="mb-3"><span class="fa fa-download fa-3x text-muted"></span></div>
            <h4 class="text-muted">Nenhum curso salvo offline ainda</h4>
            <p class="text-muted small max-w-md mx-auto">
              Navegue pelos cursos no catálogo e clique em <strong>"Baixar Curso (Offline)"</strong> enquanto tiver conexão para estudar quando estiver sem internet.
            </p>
            <a href="/slides/all" class="btn btn-primary mt-2">Explorar Catálogo de Cursos</a>
          </div>
        `;
        return;
      }

      let html = '';
      for (const c of courses) {
        html += `
          <div class="col-md-6 col-lg-4 mb-4">
            <div class="card h-100 shadow-sm border">
              <div class="card-body d-flex flex-column justify-between p-4">
                <div>
                  <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="badge bg-success"><span class="fa fa-check-circle me-1"></span>Salvo Offline</span>
                    <span class="text-muted small">${c.size_mb} MB</span>
                  </div>
                  <h5 class="card-title font-weight-bold mb-2">${c.name}</h5>
                  <p class="text-muted small mb-3">${c.total_slides} apostilas disponíveis sem internet.</p>
                </div>
                <div class="pt-3 border-top mt-auto d-flex gap-2">
                  <a href="/slides/${c.id}" class="btn btn-primary btn-sm flex-grow-1">
                    <span class="fa fa-book-open me-1"></span> Estudar
                  </a>
                  <button type="button" onclick="evolarsRemoveCourseOffline(${c.id})" class="btn btn-outline-danger btn-sm" title="Liberar Espaço">
                    <span class="fa fa-trash"></span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
      }
      container.innerHTML = html;
    } catch (e) {
      console.warn('[Evolars Offline] Erro ao renderizar biblioteca offline:', e);
    }
  }

  // Inicialização ao carregar o DOM
  document.addEventListener('DOMContentLoaded', () => {
    updateNetworkStatus();
    renderOfflineLibrary();
  });
})();
