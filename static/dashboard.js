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
        // Show error in the progress overlay instead of alert
        triageTimers.forEach(clearTimeout);
        triageTimers = [];
        var statusLabel = document.getElementById('triage-progress-status');
        var fill = document.getElementById('triage-progress-fill');
        var title = document.querySelector('.triage-progress-title');
        if (title) title.textContent = 'Triage Failed';
        if (fill) { fill.style.width = '100%'; fill.style.background = 'var(--red)'; }
        // Mark current step as failed
        triageSteps.forEach(function(id) {
          var el = document.getElementById(id);
          if (el && el.classList.contains('active')) {
            el.classList.remove('active');
            el.style.color = 'var(--red)';
          }
        });
        if (statusLabel) statusLabel.textContent = err.message;
        // Auto-dismiss after 5s and redirect to the incident
        setTimeout(function() {
          hideTriageProgress();
          if (fill) fill.style.background = '';
          if (title) title.textContent = 'AI Triage in Progress';
          if (btn) { btn.disabled = false; btn.textContent = 'Run Triage'; }
          // If we came from submit, still redirect to the incident page
          if (redirectUrl) window.location.href = redirectUrl;
        }, 5000);
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

  // ==================== PIPELINE INFO PANEL ====================
  var pipelineInfoTimer = null;

  window.showPipelineInfo = function(title, body) {
    var panel = document.getElementById('pipeline-info-panel');
    var titleEl = document.getElementById('pipeline-info-title');
    var bodyEl = document.getElementById('pipeline-info-body');
    if (!panel || !title) return;

    if (pipelineInfoTimer) { clearTimeout(pipelineInfoTimer); pipelineInfoTimer = null; }

    titleEl.textContent = title;
    bodyEl.textContent = body;
    panel.classList.add('visible');

    pipelineInfoTimer = setTimeout(function() {
      panel.classList.remove('visible');
      pipelineInfoTimer = null;
    }, 5000);
  };

  // Dismiss on click outside pipeline area
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.pipeline-progress') && !e.target.closest('.pipeline-info-panel')) {
      var panel = document.getElementById('pipeline-info-panel');
      if (panel) panel.classList.remove('visible');
      if (pipelineInfoTimer) { clearTimeout(pipelineInfoTimer); pipelineInfoTimer = null; }
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

  // ==================== ONBOARDING WALKTHROUGH ====================
  var onboardingSteps = [
    {
      title: 'Welcome to Triagista',
      body: 'AI-powered SRE incident triage. This tour highlights key features for judges. Click Next or Skip tour.',
      target: '.sidebar-logo'
    },
    {
      title: 'Incident List',
      body: '18 pre-seeded incidents. Sort by column headers, filter by Status / Severity / Engine above the table.',
      target: '.incidents-table'
    },
    {
      title: '3 Triage Engines',
      body: 'Basic (Gemini), Premium (Claude), Experimental (Managed Agents). See the Engine column for which was used.',
      target: '.filter-row'
    },
    {
      title: 'Attachments',
      body: 'Log and image icons in the Files column show which incidents have attached files. Click an incident to view them inline.',
      target: 'th.attach-col'
    },
    {
      title: 'Report & Triage',
      body: 'Submit a new incident, select an engine, and watch the AI triage in real-time with a progress overlay.',
      target: '[data-testid="nav-report"]'
    },
    {
      title: 'Settings & Theme',
      body: 'Toggle dark/light theme, font size, and font family. Collapse the sidebar with the chevron button.',
      target: '#settings-btn'
    }
  ];
  var onboardingIdx = 0;
  var highlightedEl = null;

  function showOnboardingStep() {
    var overlay = document.getElementById('onboarding-overlay');
    var card = document.getElementById('onboarding-card');
    if (!overlay || onboardingIdx >= onboardingSteps.length) {
      dismissOnboarding();
      return;
    }

    // Remove previous highlight
    if (highlightedEl) highlightedEl.classList.remove('onboarding-highlight');

    var step = onboardingSteps[onboardingIdx];
    document.getElementById('onboarding-indicator').textContent = 'Step ' + (onboardingIdx + 1) + ' of ' + onboardingSteps.length;
    document.getElementById('onboarding-title').textContent = step.title;
    document.getElementById('onboarding-body').textContent = step.body;
    document.getElementById('onboarding-next').textContent = onboardingIdx < onboardingSteps.length - 1 ? 'Next' : 'Get Started';
    overlay.classList.add('open');

    // Highlight target element and position card near it
    var target = step.target ? document.querySelector(step.target) : null;
    if (target) {
      target.classList.add('onboarding-highlight');
      highlightedEl = target;
      var rect = target.getBoundingClientRect();
      // Position card below the target, or above if near bottom
      var top = rect.bottom + 12;
      var left = Math.max(12, Math.min(rect.left, window.innerWidth - 360));
      if (top + 200 > window.innerHeight) top = Math.max(12, rect.top - 220);
      card.style.top = top + 'px';
      card.style.left = left + 'px';
    } else {
      // Fallback: center
      card.style.top = '50%';
      card.style.left = '50%';
      card.style.transform = 'translate(-50%, -50%)';
    }
  }

  window.nextOnboardingStep = function() {
    onboardingIdx++;
    if (onboardingIdx >= onboardingSteps.length) {
      dismissOnboarding();
    } else {
      showOnboardingStep();
    }
  };

  window.dismissOnboarding = function() {
    if (highlightedEl) { highlightedEl.classList.remove('onboarding-highlight'); highlightedEl = null; }
    var overlay = document.getElementById('onboarding-overlay');
    if (overlay) overlay.classList.remove('open');
    localStorage.setItem('sre-onboarding-done', '1');
  };

  window.relaunchOnboarding = function() {
    localStorage.removeItem('sre-onboarding-done');
    onboardingIdx = 0;
    // Navigate to list page if not already there
    if (window.location.pathname !== '/incidents') {
      window.location.href = '/incidents';
      return;
    }
    showOnboardingStep();
  };

  // Show on first visit to list page
  if (!localStorage.getItem('sre-onboarding-done') && window.location.pathname === '/incidents') {
    setTimeout(showOnboardingStep, 800);
  }

})();
