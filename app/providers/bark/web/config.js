'use strict';

const API = '/api/provider/bark/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id') || '';
const el = id => document.getElementById(id);

const t = key => window.OCNotifierI18n.t('provider_bark_' + key);

function applyLanguage() {
  document.querySelectorAll('[data-i18n]').forEach(node => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(node => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
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

function readSettings() {
  return {
    server_url: el('serverUrl').value.trim(),
    targets: el('targets').value.trim(),
    port: el('port').value.trim(),
    user: el('user').value.trim(),
    password: el('password').value,
    sound: el('sound').value,
    level: el('level').value,
    volume: el('volume').value.trim(),
    badge: el('badge').value.trim(),
    subtitle: el('subtitle').value.trim(),
    group: el('group').value.trim(),
    category: el('category').value.trim(),
    click: el('click').value.trim(),
    icon: el('icon').value.trim(),
    action: el('action').value,
    ttl: el('ttl').value.trim(),
    include_image: el('includeImage').checked,
    call: el('call').checked,
    archive: el('archive').checked
  };
}

function validate(settings, name) {
  if (!name || !settings.server_url || !settings.targets) {
    return t('required');
  }
  try {
    const url = new URL(
      settings.server_url.includes('://')
        ? settings.server_url : 'https://' + settings.server_url
    );
    if (!['http:', 'https:'].includes(url.protocol) ||
        url.username || url.password || url.pathname !== '/' ||
        url.search || url.hash) return t('invalid_url');
  } catch (_) {
    return t('invalid_url');
  }
  if (settings.port &&
      (!/^\d+$/.test(settings.port) ||
       Number(settings.port) < 1 || Number(settings.port) > 65535)) {
    return t('invalid_port');
  }
  if (settings.volume !== '' &&
      (!/^\d+$/.test(settings.volume) ||
       Number(settings.volume) > 10)) return t('invalid_volume');
  if (settings.badge !== '' &&
      (!/^\d+$/.test(settings.badge))) return t('invalid_badge');
  if (settings.ttl !== '' &&
      (!/^\d+$/.test(settings.ttl) || Number(settings.ttl) < 1)) {
    return t('invalid_ttl');
  }
  for (const value of [settings.click, settings.icon]) {
    if (value) {
      try {
        if (!['http:', 'https:'].includes(new URL(value).protocol)) {
          return t('invalid_optional_url');
        }
      } catch (_) {
        return t('invalid_optional_url');
      }
    }
  }
  return '';
}

async function loadConfiguration() {
  try {
    const query = serviceId ? '?service_id=' + encodeURIComponent(serviceId) : '';
    const data = await request(API + query);
    if (data.service) {
      const s = data.service.settings || {};
      el('serviceName').value = data.service.name || '';
      el('serverUrl').value = s.server_url || '';
      el('targets').value = Array.isArray(s.targets) ? s.targets.join(', ') : (s.targets || '');
      for (const id of ['port','user','password','sound','level','volume','badge',
                        'subtitle','group','category','click','icon','action','ttl']) {
        el(id).value = s[id] ?? '';
      }
      el('includeImage').checked = s.include_image !== false;
      el('call').checked = s.call === true;
      el('archive').checked = s.archive === true;
      el('enabled').checked = data.service.enabled !== false;
      el('testButton').disabled = data.service.enabled === false;
    }
    document.title = t(serviceId ? 'title_edit' : 'title_add');
  } catch (error) {
    showNotice(t('error') + error.message, true);
    el('saveButton').disabled = true;
  }
}

async function saveConfiguration() {
  const name = el('serviceName').value.trim();
  const settings = readSettings();
  const validation = validate(settings, name);
  if (validation) {
    showNotice(validation, true);
    return;
  }

  el('saveButton').disabled = true;
  showNotice(t('saving'));

  try {
    const payload = {
      name,
      settings,
      enabled: el('enabled').checked
    };
    if (serviceId) payload.service_id = serviceId;

    const result = await request(API, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });

    showNotice(t('saved'));
    alert(t('saved'));
    el('testButton').disabled = !payload.enabled;

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

(async function initialize() {
  try {
    await window.OCNotifierI18nReady;
    applyLanguage();
    await loadConfiguration();
  } catch (error) {
    showNotice('Language initialization failed: ' + error.message, true);
    el('saveButton').disabled = true;
    el('testButton').disabled = true;
  }
})();
