'use strict';

const API = '/api/provider/google_chat/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id');
const language = params.get('lang') === 'it' ? 'it' : 'en';

const TEXT = {
    en: {
        description: 'Send printer notifications to Google Chat.',
        back: 'Back',
        service_configuration: 'Service Configuration',
        service_name: 'Service Name',
        webhook_url: 'Incoming Webhook URL',
        enabled: 'Enable notifications',
        save: 'Save Configuration',
        saving: 'Saving...',
        test: 'Test Notification',
        cancel: 'Cancel',
        required: 'Please enter a service name and Incoming Webhook URL.',
        saved: 'Configuration saved successfully.',
        save_first: 'Save the configuration before testing.',
        queueing: 'Sending test notification...',
        queued: 'Test notification submitted.',
        show: 'Show',
        hide: 'Hide',
        show_webhook: 'Show',
        hide_webhook: 'Hide',
        error: 'An error occurred. Please try again.'
    },
    it: {
        description: 'Invia notifiche della stampante a Google Chat.',
        back: 'Indietro',
        service_configuration: 'Configurazione servizio',
        service_name: 'Nome servizio',
        webhook_url: 'URL Incoming Webhook',
        enabled: 'Abilita notifiche',
        save: 'Salva configurazione',
        saving: 'Salvataggio...',
        test: 'Invia notifica di test',
        cancel: 'Annulla',
        required: 'Inserisci il nome del servizio e l’URL Incoming Webhook.',
        saved: 'Configurazione salvata correttamente.',
        save_first: 'Salva la configurazione prima di eseguire il test.',
        queueing: 'Invio della notifica di test...',
        queued: 'Notifica di test inviata.',
        show: 'Mostra',
        hide: 'Nascondi',
        show_webhook: 'Mostra',
        hide_webhook: 'Nascondi',
        error: 'Si è verificato un errore. Riprova.'
    }
};

const t = key => TEXT[language][key] || key;

const serviceName = document.getElementById('serviceName');
const webhookUrl = document.getElementById('webhookUrl');
const enabled = document.getElementById('enabled');
const saveButton = document.getElementById('saveButton');
const testButton = document.getElementById('testButton');
const notice = document.getElementById('notice');
const toggleWebhook = document.getElementById('toggleWebhook');

function applyLanguage() {
    document.documentElement.lang = language;
    document.querySelectorAll('[data-i18n]').forEach(element => {
        element.textContent = t(element.dataset.i18n);
    });
    updateWebhookToggle();
}

function showNotice(message, isError = false) {
    notice.textContent = message;
    notice.className = isError ? 'error' : 'success';
}

async function request(url, options = {}) {
    const response = await fetch(url, {
        credentials: 'same-origin',
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        }
    });

    let data = {};
    try {
        data = await response.json();
    } catch (_) {}

    if (!response.ok || data.ok === false) {
        throw new Error(data.error || data.message || t('error'));
    }
    return data;
}

async function loadConfiguration() {
    try {
        const url = serviceId
            ? `${API}?service_id=${encodeURIComponent(serviceId)}`
            : API;

        const data = await request(url, { method: 'GET' });
        const service = data.service || data;

        serviceName.value = service.name || '';
        webhookUrl.value = (service.settings || {}).webhook_url || '';
        enabled.checked = service.enabled !== false;
        testButton.disabled = !serviceId || !enabled.checked;
    } catch (error) {
        showNotice(error.message || t('error'), true);
    }
}

async function saveConfiguration() {
    const name = serviceName.value.trim();
    const url = webhookUrl.value.trim();

    if (!name || !url) {
        showNotice(t('required'), true);
        return;
    }

    saveButton.disabled = true;
    saveButton.textContent = t('saving');

    try {
        const payload = {
            name,
            settings: { webhook_url: url },
            enabled: enabled.checked
        };

        if (serviceId) payload.service_id = serviceId;

        const data = await request(API, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        showNotice(t('saved'));
        alert(t('saved'));

        testButton.disabled = !enabled.checked;

        if (!serviceId && data.service_id) {
            params.set('service_id', data.service_id);
            params.set('lang', language);
            window.location.search = params.toString();
        }
    } catch (error) {
        showNotice(error.message || t('error'), true);
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = t('save');
    }
}

async function testNotification() {
    if (!serviceId) {
        showNotice(t('save_first'), true);
        return;
    }

    testButton.disabled = true;
    showNotice(t('queueing'));

    try {
        await request('/api/test', {
            method: 'POST',
            body: JSON.stringify({ service_id: serviceId })
        });
        showNotice(t('queued'));
    } catch (error) {
        showNotice(error.message || t('error'), true);
    } finally {
        testButton.disabled = !enabled.checked;
    }
}

function updateWebhookToggle() {
    const visible = webhookUrl.type === 'text';
    toggleWebhook.textContent = t(visible ? 'hide_webhook' : 'show_webhook');
    toggleWebhook.setAttribute('aria-label', toggleWebhook.textContent);
}

toggleWebhook.addEventListener('click', () => {
    webhookUrl.type = webhookUrl.type === 'password' ? 'text' : 'password';
    updateWebhookToggle();
});

enabled.addEventListener('change', () => {
    testButton.disabled = !serviceId || !enabled.checked;
});

saveButton.addEventListener('click', saveConfiguration);
testButton.addEventListener('click', testNotification);

document.getElementById('backButton').addEventListener('click', () => {
    window.location.href = '/';
});

document.getElementById('cancelButton').addEventListener('click', () => {
    window.location.href = '/';
});

applyLanguage();
loadConfiguration();
