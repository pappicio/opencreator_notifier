'use strict';

const API = '/api/provider/home_assistant/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id') || '';
const el = id => document.getElementById(id);

const t = key => window.OCNotifierI18n.t('provider_home_assistant_' + key);

function applyLanguage() {
  document.documentElement.lang = window.OCNotifierI18n.language;
  document.querySelectorAll('[data-i18n]').forEach(node => {
    node.textContent = t(node.dataset.i18n);
  });
  el('serviceName').placeholder = t('service_name_placeholder');
  el('toggleToken').title = t('show_token');
  el('toggleToken').setAttribute('aria-label', t('show_token'));
}

function showNotice(message, error = false) {
  el('notice').textContent = message;
  el('notice').style.color = error ? '#ff8585' : '#83d69a';
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || response.statusText);
  }
  return data;
}

function updateModeFields() {
  const persistent = el('mode').value === 'persistent';
  el('targetField').hidden = persistent;
  el('notificationIdField').hidden = !persistent;
}

function validateForm() {
  const name = el('serviceName').value.trim();
  const url = el('haUrl').value.trim();
  const token = el('token').value.trim();
  const mode = el('mode').value;
  const target = el('target').value.trim();
  const nid = el('notificationId').value.trim();

  if (!name || !url || !token) {
    showNotice(t('required'), true);
    return false;
  }

  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname ||
        parsed.username || parsed.password) {
      showNotice(t('invalid_url'), true);
      return false;
    }
  } catch {
    showNotice(t('invalid_url'), true);
    return false;
  }

  const tokenPattern = /^(?:[0-9a-f]{8}\.[0-9a-f]{64}|[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+)$/i;
  if (!tokenPattern.test(token)) {
    showNotice(t('invalid_token'), true);
    return false;
  }

  if (mode === 'service' && !/^[a-z0-9_]+\.[a-z0-9_]+$/i.test(target)) {
    showNotice(t('invalid_target'), true);
    return false;
  }

  if (mode === 'persistent' && nid && !/^[a-z0-9_-]+$/i.test(nid)) {
    showNotice(t('invalid_id'), true);
    return false;
  }

  return true;
}

async function loadConfiguration() {
  try {
    const query = serviceId ? '?service_id=' + encodeURIComponent(serviceId) : '';
    const data = await request(API + query);
    if (data.service) {
      const settings = data.service.settings || {};
      el('serviceName').value = data.service.name || '';
      el('haUrl').value = settings.ha_url || '';
      el('token').value = settings.token || '';
      el('mode').value = settings.mode || 'persistent';
      el('target').value = settings.target || '';
      el('notificationId').value = settings.notification_id || '';
      el('enabled').checked = data.service.enabled !== false;
      el('testButton').disabled = data.service.enabled === false;
    }
    updateModeFields();
    document.title = t(serviceId ? 'title_edit' : 'title_add');
  } catch (error) {
    showNotice(t('error') + error.message, true);
    el('saveButton').disabled = true;
  }
}

async function saveConfiguration() {
  if (!validateForm()) return;

  const name = el('serviceName').value.trim();
  const settings = {
    ha_url: el('haUrl').value.trim(),
    token: el('token').value.trim(),
    mode: el('mode').value,
    target: el('target').value.trim(),
    notification_id: el('notificationId').value.trim()
  };
  const enabled = el('enabled').checked;

  el('saveButton').disabled = true;
  showNotice(t('saving'));

  try {
    const payload = {name, settings, enabled};
    if (serviceId) payload.service_id = serviceId;

    const result = await request(API, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });

    showNotice(t('saved'));
    alert(t('saved'));
    el('testButton').disabled = !enabled;

    if (!serviceId && result.service_id) {
      const next = new URLSearchParams();
      next.set('service_id', result.service_id);
      next.set('lang', window.OCNotifierI18n.language);
      window.history.replaceState({}, '', window.location.pathname + '?' + next);
      window.location.reload();
    }
  } catch (error) {
    showNotice(t('error') + error.message, true);
  } finally {
    el('saveButton').disabled = false;
  }
}

async function testNotification() {
  if (!serviceId) {
    showNotice(t('save_first'), true);
    return;
  }
  el('testButton').disabled = true;
  showNotice(t('queueing'));
  try {
    await request('/api/test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({service_id: serviceId})
    });
    showNotice(t('queued'));
  } catch (error) {
    showNotice(t('error') + error.message, true);
  } finally {
    el('testButton').disabled = false;
  }
}

function goBack() {
  window.location.href = '/';
}

el('saveButton').addEventListener('click', saveConfiguration);
el('testButton').addEventListener('click', testNotification);
el('backButton').addEventListener('click', goBack);
el('cancelButton').addEventListener('click', goBack);
el('mode').addEventListener('change', updateModeFields);
el('toggleToken').addEventListener('click', () => {
  const input = el('token');
  const visible = input.type === 'password';
  input.type = visible ? 'text' : 'password';
  el('toggleToken').textContent = visible ? '🙈' : '👁';
  el('toggleToken').title = t(visible ? 'hide_token' : 'show_token');
  el('toggleToken').setAttribute('aria-label', el('toggleToken').title);
});

(async function initialize() {
  try {
    await window.OCNotifierI18nReady;
    applyLanguage();
    updateModeFields();
    await loadConfiguration();
  } catch (error) {
    console.error('Language initialization failed:', error);
    el('saveButton').disabled = true;
    el('testButton').disabled = true;
  }
})();
