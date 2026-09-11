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
        const statusBadge = document.getElementById(`course-status-${channelId}`);
        const saveBtn = document.getElementById(`save-btn-${channelId}`);
        if (statusBadge) {
          statusBadge.className = 'badge evolars-status-tag';
          statusBadge.style.cssText = 'background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; font-weight: 600;';
          statusBadge.innerHTML = '<i class="fa fa-cloud me-1"></i>Catálogo Online';
        }
        if (saveBtn) {
          saveBtn.className = 'btn btn-outline-primary btn-sm evolars-action-save-btn';
          saveBtn.title = 'Salvar no aparelho para estudo offline';
          saveBtn.innerHTML = '<i class="fa fa-download"></i>';
          saveBtn.onclick = function () { window.evolarsDownloadCourseOffline(channelId, this); };
        }
        alert('Curso removido da memória do aparelho com sucesso.');
      };
    } catch (err) {
      console.error('[Evolars Offline] Erro ao remover curso:', err);
    }
  };

  // 7. Expansão/Visualização das Lições do Curso
  window.evolarsToggleCourseSlides = function (channelId) {
    channelId = parseInt(channelId, 10);
    const target = document.getElementById(`offline-slides-list-${channelId}`);
    if (target) {
      target.classList.toggle('d-none');
    }
  };

  // 8. Pesquisa e Filtro em Tempo Real
  window.evolarsFilterOfflineCourses = function (query) {
    const term = (query || '').toLowerCase().trim();
    const items = document.querySelectorAll('.evolars-offline-item');
    let visibleCount = 0;

    items.forEach((item) => {
      const card = item.querySelector('.evolars-offline-course-card');
      const title = (card ? card.getAttribute('data-course-name') : '') || '';
      const text = item.textContent || '';
      if (!term || title.toLowerCase().includes(term) || text.toLowerCase().includes(term)) {
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
        noResultsEl.innerHTML = `<p class="text-muted mb-0">Nenhum curso ou lição encontrada para "<strong>${query}</strong>".</p>`;
        if (container) container.appendChild(noResultsEl);
      }
    } else if (noResultsEl) {
      noResultsEl.remove();
    }
  };

  // 9. Sincronização dos Cursos Salvos no Aparelho
  async function renderOfflineLibrary() {
    const container = document.getElementById('evolars-offline-library-list');
    if (!container) return;

    try {
      const db = await openDB();
      const tx = db.transaction('courses', 'readonly');
      const savedCourses = await new Promise((resolve) => {
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

      const savedMap = new Map();
      for (const c of savedCourses) {
        savedMap.set(parseInt(c.id, 10), c);
      }

      const items = container.querySelectorAll('.evolars-offline-item');
      items.forEach((item) => {
        const channelId = parseInt(item.getAttribute('data-channel-id'), 10);
        const statusBadge = document.getElementById(`course-status-${channelId}`);
        const saveBtn = document.getElementById(`save-btn-${channelId}`);

        if (savedMap.has(channelId)) {
          const savedData = savedMap.get(channelId);
          if (statusBadge) {
            statusBadge.className = 'badge';
            statusBadge.style.cssText = 'background-color: #dcfce7; color: #14532d; border: 1px solid #86efac; font-weight: 700;';
            statusBadge.innerHTML = `<i class="fa fa-check-circle me-1"></i>Salvo no Aparelho (${savedData.size_mb || '0'} MB)`;
          }
          if (saveBtn) {
            saveBtn.className = 'btn btn-outline-danger btn-sm';
            saveBtn.title = 'Remover da memória do aparelho';
            saveBtn.innerHTML = '<i class="fa fa-trash"></i>';
            saveBtn.onclick = function () { window.evolarsRemoveCourseOffline(channelId); };
          }
        }
      });
    } catch (e) {
      console.warn('[Evolars Offline] Aviso ao sincronizar status:', e);
    }
  }

  // 10. Leitor Integrado no App (Canvas / PDF.js - Zero Download Externo)
  let currentDoc = null;
  let currentPageNum = 1;
  let currentScale = 1.0;
  let isRendering = false;
  let renderPendingNum = null;

  async function ensurePdfJs() {
    if (window.pdfjsLib) return window.pdfjsLib;
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/web/static/lib/pdfjs/build/pdf.js';
      script.onload = () => {
        if (window.pdfjsLib) {
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = '/web/static/lib/pdfjs/build/pdf.worker.js';
          resolve(window.pdfjsLib);
        } else {
          reject(new Error('PDF.js não carregado'));
        }
      };
      script.onerror = () => reject(new Error('Falha ao carregar leitor'));
      document.head.appendChild(script);
    });
  }

  async function renderPage(num) {
    if (!currentDoc) return;
    isRendering = true;

    try {
      const page = await currentDoc.getPage(num);
      const canvas = document.getElementById('evolars-viewer-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');

      const container = document.getElementById('evolars-viewer-body');
      const containerWidth = container ? Math.min(container.clientWidth - 40, 960) : 800;
      const unscaledViewport = page.getViewport({ scale: 1.0 });
      const fitScale = (containerWidth / unscaledViewport.width) * currentScale;
      const viewport = page.getViewport({ scale: fitScale });

      canvas.height = viewport.height;
      canvas.width = viewport.width;

      await page.render({ canvasContext: ctx, viewport: viewport }).promise;
      isRendering = false;

      if (renderPendingNum !== null) {
        const nextNum = renderPendingNum;
        renderPendingNum = null;
        renderPage(nextNum);
      }
    } catch (e) {
      console.warn('[Evolars Viewer] Render error:', e);
      isRendering = false;
    }

    const currEl = document.getElementById('evolars-viewer-curr-page');
    if (currEl) currEl.textContent = String(num);

    const prevBtn = document.getElementById('evolars-viewer-btn-prev');
    const nextBtn = document.getElementById('evolars-viewer-btn-next');
    if (prevBtn) prevBtn.disabled = (num <= 1);
    if (nextBtn) nextBtn.disabled = (num >= currentDoc.numPages);
  }

  function queueRenderPage(num) {
    if (isRendering) {
      renderPendingNum = num;
    } else {
      renderPage(num);
    }
  }

  window.evolarsOpenLessonInApp = async function (slideId, slideName, channelId) {
    slideId = parseInt(slideId, 10);
    const modal = document.getElementById('evolars-inapp-viewer-modal');
    if (!modal) return;

    modal.classList.remove('d-none');
    document.body.style.overflow = 'hidden';

    const titleEl = document.getElementById('evolars-viewer-title');
    if (titleEl) titleEl.textContent = slideName || 'Apostila Oficial';

    const loadingEl = document.getElementById('evolars-viewer-loading');
    const canvasWrap = document.getElementById('evolars-viewer-canvas-wrap');
    if (loadingEl) {
      loadingEl.classList.remove('d-none');
      loadingEl.innerHTML = `
        <span class="fa fa-circle-o-notch fa-spin fa-3x" style="color: #38bdf8;"></span>
        <p class="text-white mt-3 fw-semibold">Carregando conteúdo no leitor seguro...</p>
      `;
    }
    if (canvasWrap) canvasWrap.classList.add('d-none');

    try {
      await ensurePdfJs();

      const cache = await caches.open(COURSES_CACHE);
      let cachedResp = await cache.match(`/slides/slide/${slideId}/pdf_content`);
      let arrayBuf;

      if (cachedResp) {
        arrayBuf = await cachedResp.arrayBuffer();
      } else {
        const resp = await fetch(`/slides/slide/${slideId}/pdf_content`);
        if (!resp.ok) throw new Error('Não foi possível carregar o material da aula');
        const blob = await resp.blob();
        arrayBuf = await blob.arrayBuffer();
        try {
          await cache.put(`/slides/slide/${slideId}/pdf_content`, new Response(blob, {
            headers: { 'Content-Type': 'application/pdf', 'Content-Length': blob.size }
          }));
        } catch (_) {}
      }

      currentDoc = await window.pdfjsLib.getDocument({ data: arrayBuf }).promise;
      currentPageNum = 1;
      currentScale = 1.0;

      const totalEl = document.getElementById('evolars-viewer-total-pages');
      if (totalEl) totalEl.textContent = String(currentDoc.numPages);

      if (loadingEl) loadingEl.classList.add('d-none');
      if (canvasWrap) canvasWrap.classList.remove('d-none');

      renderPage(currentPageNum);
    } catch (err) {
      console.error('[Evolars Viewer] Falha ao abrir apostila:', err);
      if (loadingEl) {
        loadingEl.innerHTML = `
          <div class="text-danger py-4">
            <i class="fa fa-exclamation-triangle fa-2x mb-2"></i>
            <p class="mb-2 text-white">Não foi possível exibir esta apostila no momento.</p>
            <button type="button" class="btn btn-sm btn-outline-light" onclick="window.evolarsCloseInAppViewer()">Fechar</button>
          </div>
        `;
      }
    }
  };

  window.evolarsCloseInAppViewer = function () {
    const modal = document.getElementById('evolars-inapp-viewer-modal');
    if (modal) {
      modal.classList.add('d-none');
      modal.classList.remove('evolars-viewer-maximized');
    }
    document.body.style.overflow = '';
    currentDoc = null;
    currentPageNum = 1;

    const exitFs = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen || document.msExitFullscreen;
    const isFs = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
    if (isFs && typeof exitFs === 'function') {
      try {
        const p = exitFs.call(document);
        if (p && typeof p.catch === 'function') p.catch(() => {});
      } catch (_) {}
    }
  };

  window.evolarsViewerPrevPage = function () {
    if (!currentDoc || currentPageNum <= 1) return;
    currentPageNum--;
    queueRenderPage(currentPageNum);
  };

  window.evolarsViewerNextPage = function () {
    if (!currentDoc || currentPageNum >= currentDoc.numPages) return;
    currentPageNum++;
    queueRenderPage(currentPageNum);
  };

  window.evolarsViewerZoom = function (delta) {
    if (!currentDoc) return;
    const newScale = currentScale + delta;
    if (newScale >= 0.6 && newScale <= 2.5) {
      currentScale = newScale;
      queueRenderPage(currentPageNum);
    }
  };

  window.evolarsViewerToggleFullscreen = function () {
    const modal = document.getElementById('evolars-inapp-viewer-modal');
    if (!modal) return;

    const requestFs = modal.requestFullscreen || modal.webkitRequestFullscreen || modal.mozRequestFullScreen || modal.msRequestFullscreen;
    const exitFs = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen || document.msExitFullscreen;
    const isFs = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;

    if (!isFs && typeof requestFs === 'function') {
      try {
        const p = requestFs.call(modal);
        if (p && typeof p.catch === 'function') {
          p.catch(() => {
            modal.classList.toggle('evolars-viewer-maximized');
            if (currentDoc) queueRenderPage(currentPageNum);
          });
        }
      } catch (_) {
        modal.classList.toggle('evolars-viewer-maximized');
        if (currentDoc) queueRenderPage(currentPageNum);
      }
    } else if (isFs && typeof exitFs === 'function') {
      try {
        const p = exitFs.call(document);
        if (p && typeof p.catch === 'function') p.catch(() => {});
      } catch (_) {}
    } else {
      modal.classList.toggle('evolars-viewer-maximized');
      if (currentDoc) queueRenderPage(currentPageNum);
    }
  };

  document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('evolars-inapp-viewer-modal');
    if (!modal || modal.classList.contains('d-none')) return;

    if (e.key === 'Escape') {
      window.evolarsCloseInAppViewer();
    } else if (e.key === 'ArrowLeft') {
      window.evolarsViewerPrevPage();
    } else if (e.key === 'ArrowRight') {
      window.evolarsViewerNextPage();
    }
  });

  // 11. Suporte a clique suave em botões com âncora #channels
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

  // 12. Inicialização Imediata e Resiliente
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
