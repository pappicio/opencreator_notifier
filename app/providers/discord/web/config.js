'use strict';

const API = '/api/provider/discord/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id') || '';
const language = params.get('lang') === 'it' ? 'it' : 'en';
const el = id => document.getElementById(id);

const TEXT = {
  en: {
    description: 'Configure a Discord Webhook destination',
    back: 'Back',
    service_configuration: 'Service Configuration',
    service_name: 'Service Name',
    service_name_placeholder: 'e.g. Workshop Discord',
    webhook_id: 'Webhook ID',
    webhook_token: 'Webhook Token',
    enabled: 'Enabled',
    save: 'Save Configuration',
    test: 'Test Notification',
    cancel: 'Cancel',
    show_token: 'Show Webhook token',
    hide_token: 'Hide Webhook token',
    required: 'Please complete all required fields.',
    saving: 'Saving configuration...',
    saved: 'Configuration saved successfully.',
    save_first: 'Save the service before testing.',
    queueing: 'Queueing test notification...',
    queued: 'Test notification queued.',
    error: 'Error: '
  },
  it: {
    description: 'Configura una destinazione tramite Webhook Discord',
    back: 'Indietro',
    service_configuration: 'Configurazione servizio',
    service_name: 'Nome servizio',
    service_name_placeholder: 'es. Discord Laboratorio',
    webhook_id: 'ID Webhook',
    webhook_token: 'Token Webhook',
    enabled: 'Attivo',
    save: 'Salva configurazione',
    test: 'Invia notifica di prova',
    cancel: 'Annulla',
    show_token: 'Mostra token Webhook',
    hide_token: 'Nascondi token Webhook',
    required: 'Completa tutti i campi obbligatori.',
    saving: 'Salvataggio configurazione...',
    saved: 'Configurazione salvata correttamente.',
    save_first: 'Salva il servizio prima di eseguire il test.',
    queueing: 'Accodamento notifica di prova...',
    queued: 'Notifica di prova accodata.',
    error: 'Errore: '
  }
};
const t = key => TEXT[language][key] || TEXT.en[key] || key;

function applyLanguage() {
  document.documentElement.lang = language;
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

async function loadConfiguration() {
  try {
    const query = serviceId ? '?service_id=' + encodeURIComponent(serviceId) : '';
    const data = await request(API + query);
    if (data.service) {
      el('serviceName').value = data.service.name || '';
      el('webhookId').value = data.service.settings.webhook_id || '';
      el('webhookToken').value = data.service.settings.webhook_token || '';
      el('enabled').checked = data.service.enabled !== false;
      el('testButton').disabled = data.service.enabled === false;
    }
    document.title = (serviceId ? 'Edit Discord' : 'Add Discord') + ' - OpenCreator Notifier';
  } catch (error) {
    showNotice(t('error') + error.message, true);
    el('saveButton').disabled = true;
  }
}

async function saveConfiguration() {
  const name = el('serviceName').value.trim();
  const webhookId = el('webhookId').value.trim();
  const webhookToken = el('webhookToken').value.trim();

  if (!name || !webhookId || !webhookToken) {
    showNotice(t('required'), true);
    return;
  }

  el('saveButton').disabled = true;
  showNotice(t('saving'));

  try {
    const payload = {
      name,
      settings: {webhook_id: webhookId, webhook_token: webhookToken},
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
      next.set('lang', language);
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
el('toggleToken').addEventListener('click', () => {
  const input = el('webhookToken');
  const visible = input.type === 'password';
  input.type = visible ? 'text' : 'password';
  el('toggleToken').textContent = visible ? '🙈' : '👁';
  el('toggleToken').title = t(visible ? 'hide_token' : 'show_token');
  el('toggleToken').setAttribute('aria-label', el('toggleToken').title);
});

applyLanguage();
loadConfiguration();
