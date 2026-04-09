/* Dashboard JS — SRE Triage Agent */
/* Settings persistence, triage/ack/resolve actions */

(function() {
  'use strict';

  // ==================== SETTINGS ====================
  const STORAGE_KEY = 'sre-dashboard-settings';
  const DEFAULTS = { theme: 'light', fontSize: 'medium', font: 'IBM Plex Sans' };

  function loadSettings() {
    try {
      return Object.assign({}, DEFAULTS, JSON.parse(localStorage.getItem(STORAGE_KEY)));
    } catch { return Object.assign({}, DEFAULTS); }
  }

  function saveSettings(s) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  }

  function applySettings(s) {
    var html = document.documentElement;
    // Theme
    html.classList.remove('light');
    if (s.theme === 'light') html.classList.add('light');
    // Font size
    html.classList.remove('font-small', 'font-medium', 'font-large');
    html.classList.add('font-' + s.fontSize);
    // Font family
    html.style.setProperty('--sans', "'" + s.font + "', sans-serif");

    // Update active buttons
    updateSettingsUI(s);
  }

  function updateSettingsUI(s) {
    // Theme buttons
    document.querySelectorAll('[data-setting="theme"]').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.value === s.theme);
    });
    // Font size buttons
    document.querySelectorAll('[data-setting="fontSize"]').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.value === s.fontSize);
    });
    // Font buttons
    document.querySelectorAll('[data-setting="font"]').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.value === s.font);
    });
  }

  // Toggle settings dropdown
  window.toggleSettings = function() {
    var dd = document.getElementById('settings-dropdown');
    if (dd) dd.classList.toggle('open');
  };

  // Close dropdown on outside click
  document.addEventListener('click', function(e) {
    var dd = document.getElementById('settings-dropdown');
    var btn = document.getElementById('settings-btn');
    if (dd && btn && !dd.contains(e.target) && !btn.contains(e.target)) {
      dd.classList.remove('open');
    }
  });

  // Setting change handler
  window.changeSetting = function(key, value) {
    var s = loadSettings();
    s[key] = value;
    saveSettings(s);
    applySettings(s);
  };

  // Apply on load
  applySettings(loadSettings());

  // ==================== PROVIDER SELECTOR ====================
  window.selectProvider = function(el) {
    if (el.classList.contains('disabled')) return;
    document.querySelectorAll('.provider-card').forEach(function(c) { c.classList.remove('selected'); });
    el.classList.add('selected');
    localStorage.setItem('sre-triage-provider', el.dataset.provider);
  };

  // Restore provider selection on load (for detail page selector)
  (function() {
    var cards = document.querySelectorAll('.provider-card');
    if (cards.length === 0) return;
    var saved = localStorage.getItem('sre-triage-provider') || '';
    var card = saved ? document.querySelector('[data-provider="' + saved + '"]:not(.disabled)') : null;
    if (!card) card = document.querySelector('.provider-card:not(.disabled)');
    if (card) window.selectProvider(card);
  })();

  // ==================== TRIAGE WITH PROGRESS ====================
  var triageSteps = ['ts-guardrail', 'ts-context', 'ts-analysis', 'ts-dispatch'];
  var triageTimers = [];

  function showTriageProgress(engineName) {
    var overlay = document.getElementById('triage-overlay');
    var engineLabel = document.getElementById('triage-progress-engine');
    var statusLabel = document.getElementById('triage-progress-status');
    var fill = document.getElementById('triage-progress-fill');
    if (!overlay) return;

    // Reset steps
    triageSteps.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) { el.classList.remove('active', 'done'); }
    });
    fill.style.width = '0%';
    statusLabel.textContent = 'Starting...';
    engineLabel.textContent = (engineName || 'AI Engine').charAt(0).toUpperCase() + (engineName || '').slice(1);
    overlay.classList.add('open');

    // Animate steps on a timer to show progress
    triageTimers = [];
    var stepMessages = ['Scanning for injection patterns...', 'Searching Solidus codebase...', 'Analyzing root cause...', 'Creating ticket & notifications...'];
    triageSteps.forEach(function(id, i) {
      triageTimers.push(setTimeout(function() {
        // Mark previous done
        if (i > 0) document.getElementById(triageSteps[i - 1]).classList.replace('active', 'done');
        document.getElementById(id).classList.add('active');
        fill.style.width = ((i + 1) * 25) + '%';
        statusLabel.textContent = stepMessages[i];
      }, i * 2500));
    });
  }

  function hideTriageProgress() {
    triageTimers.forEach(clearTimeout);
    triageTimers = [];
    var overlay = document.getElementById('triage-overlay');
    if (overlay) overlay.classList.remove('open');
  }

  window.runTriage = function(incidentId, redirectUrl) {
    var provider = localStorage.getItem('sre-triage-provider') || '';
    var engineNames = { langchain: 'Basic (Gemini)', anthropic: 'Premium (Claude)', managed: 'Managed Agents' };
    showTriageProgress(engineNames[provider] || provider);

    // Disable any triage buttons
    var btn = document.getElementById('btn-triage') || document.querySelector('[data-testid="btn-run-triage"]');
    if (btn) { btn.disabled = true; }

    var url = '/api/incidents/' + incidentId + '/triage';
    if (provider) url += '?provider=' + encodeURIComponent(provider);

    fetch(url, { method: 'POST' })
      .then(function(r) {
        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Triage failed'); });
        return r.json();
      })
      .then(function() {
        // Complete all steps
        triageSteps.forEach(function(id) {
          var el = document.getElementById(id);
          if (el) { el.classList.remove('active'); el.classList.add('done'); }
        });
        document.getElementById('triage-progress-fill').style.width = '100%';
        document.getElementById('triage-progress-status').textContent = 'Triage complete — loading results...';
        setTimeout(function() {
          hideTriageProgress();
          window.location.href = redirectUrl || ('/incidents/' + incidentId);
        }, 800);
      })
      .catch(function(err) {
        hideTriageProgress();
        alert('Triage error: ' + err.message);
        if (btn) { btn.disabled = false; btn.textContent = 'Run Triage'; }
      });
  };

  // ==================== ACKNOWLEDGE ====================
  window.acknowledgeIncident = function(incidentId) {
    fetch('/api/incidents/' + incidentId + '/acknowledge', { method: 'POST' })
      .then(function(r) {
        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Failed'); });
        window.location.reload();
      })
      .catch(function(err) { alert('Acknowledge error: ' + err.message); });
  };

  // ==================== RESOLVE ====================
  window.openResolveDialog = function() {
    var overlay = document.getElementById('resolve-overlay');
    if (overlay) overlay.classList.add('open');
  };

  window.closeResolveDialog = function() {
    var overlay = document.getElementById('resolve-overlay');
    if (overlay) overlay.classList.remove('open');
  };

  window.submitResolve = function(incidentId) {
    var form = document.getElementById('resolve-form');
    if (!form) return;
    var formData = new FormData(form);

    fetch('/api/incidents/' + incidentId + '/resolve', {
      method: 'POST',
      body: formData,
    })
      .then(function(r) {
        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Failed'); });
        window.location.reload();
      })
      .catch(function(err) { alert('Resolve error: ' + err.message); });
  };

  // Close resolve dialog on overlay click
  document.addEventListener('click', function(e) {
    if (e.target.id === 'resolve-overlay') {
      window.closeResolveDialog();
    }
  });

  // Close resolve dialog on Escape
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') window.closeResolveDialog();
  });

  // ==================== PIPELINE TOOLTIPS ====================
  var tooltipTimer = null;

  window.showPipelineTooltip = function(dotEl) {
    // Remove any existing tooltip
    dismissPipelineTooltip();

    var title = dotEl.getAttribute('data-tooltip-title') || '';
    var body = dotEl.getAttribute('data-tooltip-body') || '';
    if (!body) return;

    var tooltip = document.createElement('div');
    tooltip.className = 'pipeline-tooltip';
    tooltip.innerHTML =
      '<button class="pipeline-tooltip-close" onclick="dismissPipelineTooltip()">&times;</button>' +
      '<div class="pipeline-tooltip-title">' + title + '</div>' +
      '<div class="pipeline-tooltip-body">' + body + '</div>';

    // Position relative to the dot's parent step
    var step = dotEl.closest('.pipeline-step');
    if (step) {
      step.style.position = 'relative';
      step.appendChild(tooltip);
    }

    // Auto-dismiss after 5 seconds
    tooltipTimer = setTimeout(dismissPipelineTooltip, 5000);
  };

  window.dismissPipelineTooltip = function() {
    if (tooltipTimer) { clearTimeout(tooltipTimer); tooltipTimer = null; }
    var existing = document.querySelector('.pipeline-tooltip');
    if (existing) existing.remove();
  };

  // Dismiss on click outside
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.pipeline-step') && !e.target.closest('.pipeline-tooltip')) {
      dismissPipelineTooltip();
    }
  });

  // ==================== ATTACHMENT LOG LOADER ====================
  // Lazy-load text attachment content when its <details> opens
  document.querySelectorAll('.attachment-item').forEach(function(detail) {
    detail.addEventListener('toggle', function() {
      if (!detail.open) return;
      var logDiv = detail.querySelector('.attachment-log[data-src]');
      if (!logDiv || logDiv.dataset.loaded) return;
      logDiv.dataset.loaded = '1';
      fetch(logDiv.dataset.src)
        .then(function(r) { return r.text(); })
        .then(function(text) {
          logDiv.textContent = text;
        })
        .catch(function() {
          logDiv.textContent = 'Failed to load attachment.';
        });
    });
    // If already open (first item), trigger load immediately
    if (detail.open) detail.dispatchEvent(new Event('toggle'));
  });

  // ==================== SIDEBAR ====================
  // Mobile toggle
  window.toggleSidebar = function() {
    document.querySelector('.sidebar').classList.toggle('open');
    document.getElementById('sidebar-overlay').classList.toggle('open');
  };

  window.closeSidebar = function() {
    document.querySelector('.sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('open');
  };

  // Desktop collapse/expand
  window.toggleSidebarCollapse = function() {
    var sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('sre-sidebar-collapsed', sidebar.classList.contains('collapsed') ? '1' : '');
  };

  // Restore collapse state on load
  (function() {
    if (localStorage.getItem('sre-sidebar-collapsed') === '1') {
      document.querySelector('.sidebar').classList.add('collapsed');
    }
  })();

  // ==================== EXPLANATION TABS ====================
  window.switchExplainTab = function(tab, btn) {
    document.querySelectorAll('.explain-content').forEach(function(c) { c.classList.remove('active'); });
    document.querySelectorAll('.explain-tab').forEach(function(t) { t.classList.remove('active'); });
    var el = document.getElementById('explain-' + tab);
    if (el) el.classList.add('active');
    if (btn) btn.classList.add('active');
  };

})();
