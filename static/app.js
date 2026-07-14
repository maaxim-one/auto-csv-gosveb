(function() {
  const t = localStorage.getItem('theme');
  if (t) document.documentElement.setAttribute('data-theme', t);
  const em = localStorage.getItem('exportMode');
  if (em) document.documentElement.setAttribute('data-export-mode', em);

  setTimeout(function() {
    document.querySelectorAll('#flash-area .flash-message:not(.flash-info)').forEach(function(el) {
      el.style.transition = 'opacity 0.3s, transform 0.3s';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-8px)';
      setTimeout(function() { el.remove(); }, 3000);
    });
  }, 5000);
})();

document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('theme-toggle');
  function applyTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }
  toggle.addEventListener('click', () => {
    applyTheme(document.documentElement.getAttribute('data-theme') !== 'dark');
  });

  fetch('/api/version').then(r => r.json()).then(data => {
    if (data.update && data.url) {
      const area = document.getElementById('flash-area');
      const div = document.createElement('div');
      div.className = 'flash-message flash-info';
      div.innerHTML = `
        <span class="flash-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg></span>
        <span>Доступна новая версия <strong>${data.latest}</strong>. <a href="${data.url}" target="_blank" rel="noopener">Скачать обновление</a></span>
        <button type="button" class="flash-close" onclick="this.parentElement.remove()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>`;
      area.appendChild(div);
    }
  }).catch(() => {});

  const FLASH_ICONS = {
    error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
  };

  const CLOSE_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

  function showFlash(messages) {
    const area = document.getElementById('flash-area');
    area.innerHTML = '';
    messages.forEach(m => {
      const div = document.createElement('div');
      div.className = 'flash-message flash-' + m.category;

      const icon = document.createElement('span');
      icon.className = 'flash-icon';
      icon.innerHTML = FLASH_ICONS[m.category] || FLASH_ICONS.success;
      div.appendChild(icon);

      const text = document.createElement('span');
      text.textContent = m.text;
      div.appendChild(text);

      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'flash-close';
      closeBtn.innerHTML = CLOSE_ICON;
      closeBtn.addEventListener('click', () => div.remove());
      div.appendChild(closeBtn);

      area.appendChild(div);

      setTimeout(() => {
        if (div.parentNode) {
          div.style.transition = 'opacity 0.3s, transform 0.3s';
          div.style.opacity = '0';
          div.style.transform = 'translateY(-8px)';
          setTimeout(() => div.remove(), 300);
        }
      }, 10000);
    });
  }

  function setLoading(btn, loading) {
    if (loading) {
      btn.classList.add('loading');
      btn._origHTML = btn.innerHTML;
      btn.innerHTML = '<span class="spinner"></span>';
    } else {
      btn.classList.remove('loading');
      if (btn._origHTML) btn.innerHTML = btn._origHTML;
    }
  }

  function restoreExportMode() {
    const saved = localStorage.getItem('exportMode');
    const select = document.getElementById('export_mode');
    if (select && saved) {
      select.value = saved;
    }
  }

  function bindExportModeSave() {
    const select = document.getElementById('export_mode');
    if (select) {
      select.addEventListener('change', () => {
        localStorage.setItem('exportMode', select.value);
      });
    }
  }

  restoreExportMode();
  bindExportModeSave();

  const uploadForm = document.getElementById('upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('upload-btn');
      const fileInput = document.getElementById('file-input');
      if (!fileInput.files.length) return;

      setLoading(btn, true);
      const fd = new FormData();
      fd.append('archive', fileInput.files[0]);

      try {
        const res = await fetch('/upload', {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: fd
        });
        const data = await res.json();
        if (data.ok) {
          showFlash(data.messages || []);
          updateDataSection(data.preview_html, data.total_count, data.export_mode, data.categories);
        } else {
          showFlash(data.messages || [{category:'error', text:'Ошибка загрузки'}]);
        }
      } catch(err) {
        showFlash([{category:'error', text:'Ошибка сети'}]);
      }
      setLoading(btn, false);
    });
  }

  const downloadForm = document.getElementById('download-form');
  if (downloadForm) {
    downloadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('download-btn');
      setLoading(btn, true);

      try {
        const fd = new FormData(downloadForm);
        const res = await fetch('/download_zip', {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: fd
        });
        const data = await res.json();
        if (data.ok && data.redirect) {
          window.location.href = data.redirect;
          return;
        }
        showFlash([{category:'error', text:'Ошибка формирования архива'}]);
      } catch(err) {
        showFlash([{category:'error', text:'Ошибка сети'}]);
      }
      setLoading(btn, false);
    });
  }

  const clearBtn = document.getElementById('clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
      setLoading(clearBtn, true);
      try {
        const res = await fetch('/clear', {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const data = await res.json();
        if (data.ok) {
          showFlash([{category: 'success', text: 'Документы очищены'}]);
          clearDataSection();
        } else {
          showFlash([{category: 'error', text: 'Ошибка очистки'}]);
        }
      } catch(err) {
        showFlash([{category: 'error', text: 'Ошибка сети'}]);
      }
      setLoading(clearBtn, false);
    });
  }

  function clearDataSection() {
    const section = document.getElementById('data-section');
    section.innerHTML = `
      <div class="empty-state animate-in" id="empty-state">
        <p>Загрузите ZIP-архив выше, чтобы сформировать CSV.</p>
      </div>`;
  }

  function updateDataSection(previewHtml, totalCount, exportMode, categories) {
    const section = document.getElementById('data-section');
    const empty = document.getElementById('empty-state');
    if (empty) empty.remove();

    const statsBar = document.getElementById('stats-bar');
    if (statsBar) statsBar.textContent = 'Файлов: ' + totalCount;

    const tableContainer = document.getElementById('table-container');
    if (tableContainer) {
      tableContainer.innerHTML = previewHtml;
    } else {
      const card = document.createElement('div');
      card.className = 'card animate-in';
      card.innerHTML = `
        <div class="card-header">
          <span class="card-title">Данные</span>
          <span class="stats-bar" id="stats-bar">Файлов: ${totalCount}</span>
        </div>
        <p class="text-muted">Редактируйте поля в таблице. При скачивании правки сохранятся в CSV.</p>
        <form id="download-form" action="/download_zip" method="post">
          <div style="margin-bottom:16px; display:flex; align-items:center; gap:12px;">
            <span class="label-inline">Режим экспорта:</span>
            <select name="export_mode" id="export_mode">
              <option value="school" ${exportMode === 'school' ? 'selected' : ''}>Школа</option>
              <option value="kindergarten" ${exportMode === 'kindergarten' ? 'selected' : ''}>Детский сад</option>
            </select>
          </div>
          <div id="category-filter" class="category-filter" style="display:${categories && categories.length ? 'flex' : 'none'}">
            <span>Нормативный правовой документ по категориям:</span>
            <label class="checkbox-label"><input type="checkbox" id="cat-filter-all" checked> Все</label>
          </div>
          <div id="table-container">${previewHtml}</div>
          <div class="download-actions">
            <button type="button" class="btn btn-secondary" id="clear-btn">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
              Очистить
            </button>
            <button type="submit" class="btn btn-success" id="download-btn">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              Скачать архив
            </button>
          </div>
        </form>`;
      section.appendChild(card);

      if (categories && categories.length) {
        const filterDiv = card.querySelector('#category-filter');
        categories.forEach(cat => {
          const lbl = document.createElement('label');
          lbl.className = 'checkbox-label';
          lbl.innerHTML = `<input type="checkbox" class="cat-filter-checkbox" value="${cat}" checked> ${cat}`;
          filterDiv.appendChild(lbl);
        });
      }

      rebindDownloadForm();
      rebindCategoryFilter();
      rebindClearBtn();
      bindExportModeSave();
      restoreExportMode();
    }
  }

  function rebindDownloadForm() {
    const df = document.getElementById('download-form');
    if (!df) return;
    df.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('download-btn');
      setLoading(btn, true);
      try {
        const fd = new FormData(df);
        const res = await fetch('/download_zip', {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: fd
        });
        const data = await res.json();
        if (data.ok && data.redirect) {
          window.location.href = data.redirect;
          return;
        }
        showFlash([{category:'error', text:'Ошибка формирования архива'}]);
      } catch(err) {
        showFlash([{category:'error', text:'Ошибка сети'}]);
      }
      setLoading(btn, false);
    });
  }

  function rebindClearBtn() {
    const clearBtn = document.getElementById('clear-btn');
    if (!clearBtn) return;
    clearBtn.addEventListener('click', async () => {
      setLoading(clearBtn, true);
      try {
        const res = await fetch('/clear', {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const data = await res.json();
        if (data.ok) {
          showFlash([{category: 'success', text: 'Документы очищены'}]);
          clearDataSection();
        } else {
          showFlash([{category: 'error', text: 'Ошибка очистки'}]);
        }
      } catch(err) {
        showFlash([{category: 'error', text: 'Ошибка сети'}]);
      }
      setLoading(clearBtn, false);
    });
  }

  function rebindCategoryFilter() {
    const catAll = document.getElementById('cat-filter-all');
    const catCbs = document.querySelectorAll('.cat-filter-checkbox');
    if (!catAll) return;
    catAll.addEventListener('change', () => {
      catCbs.forEach(cb => { cb.checked = catAll.checked; });
      document.querySelectorAll('.reg-checkbox').forEach(cb => { cb.checked = catAll.checked; });
    });
    catCbs.forEach(cb => {
      cb.addEventListener('change', () => {
        document.querySelectorAll('tbody tr').forEach(tr => {
          if (tr.getAttribute('data-category') === cb.value) {
            const r = tr.querySelector('.reg-checkbox');
            if (r) r.checked = cb.checked;
          }
        });
        catAll.checked = catCbs.length > 0 && Array.from(catCbs).every(c => c.checked);
      });
    });
  }

  rebindCategoryFilter();
  rebindClearBtn();
});
