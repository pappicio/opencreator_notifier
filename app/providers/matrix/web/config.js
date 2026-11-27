'use strict';

const API = '/api/provider/matrix/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id');
const language = params.get('lang') === 'it' ? 'it' : 'en';

const TEXT = {
    en: {
        description: 'Send printer notifications to Matrix.',
        back: 'Back',
        service_configuration: 'Service Configuration',
        service_name: 'Service Name',
        homeserver_url: 'Homeserver URL',
        access_token: 'Access Token',
        target: 'Room ID, Room Alias or User ID',
        target_hint: 'Enter a Room ID (!), Room Alias (#) or User ID (@).',
        enabled: 'Enable notifications',
        save: 'Save Configuration',
        saving: 'Saving...',
        test: 'Test Notification',
        cancel: 'Cancel',
        required: 'Please complete all required fields.',
        saved: 'Configuration saved successfully.',
        save_first: 'Save the configuration before testing.',
        queueing: 'Sending test notification...',
        queued: 'Test notification submitted.',
        show: 'Show',
        hide: 'Hide',
        error: 'An error occurred. Please try again.'
    },
    it: {
        description: 'Invia notifiche della stampante a Matrix.',
        back: 'Indietro',
        service_configuration: 'Configurazione servizio',
        service_name: 'Nome servizio',
        homeserver_url: 'URL Homeserver',
        access_token: 'Access Token',
        target: 'Room ID, alias della stanza o User ID',
        target_hint: 'Inserisci un Room ID (!), un alias (#) oppure un User ID (@).',
        enabled: 'Abilita notifiche',
        save: 'Salva configurazione',
        saving: 'Salvataggio...',
        test: 'Invia notifica di test',
        cancel: 'Annulla',
        required: 'Compila tutti i campi obbligatori.',
        saved: 'Configurazione salvata correttamente.',
        save_first: 'Salva la configurazione prima di eseguire il test.',
        queueing: 'Invio della notifica di test...',
        queued: 'Notifica di test inviata.',
        show: 'Mostra',
        hide: 'Nascondi',
        error: 'Si è verificato un errore. Riprova.'
    }
};

const t = key => TEXT[language][key] || key;

const serviceName = document.getElementById('serviceName');
const homeserverUrl = document.getElementById('homeserverUrl');
const accessToken = document.getElementById('accessToken');
const target = document.getElementById('target');
const enabled = document.getElementById('enabled');
const saveButton = document.getElementById('saveButton');
const testButton = document.getElementById('testButton');
const notice = document.getElementById('notice');
const toggleToken = document.getElementById('toggleToken');

function applyLanguage() {
    document.documentElement.lang = language;
    document.querySelectorAll('[data-i18n]').forEach(element => {
        element.textContent = t(element.dataset.i18n);
    });
    updateTokenToggle();
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
        const settings = service.settings || {};

        serviceName.value = service.name || '';
        homeserverUrl.value = settings.homeserver_url || '';
        accessToken.value = settings.access_token || '';
        target.value = settings.target || '';
        enabled.checked = service.enabled !== false;
        testButton.disabled = !serviceId || !enabled.checked;
    } catch (error) {
        showNotice(error.message || t('error'), true);
    }
}

async function saveConfiguration() {
    const name = serviceName.value.trim();
    const server = homeserverUrl.value.trim();
    const token = accessToken.value.trim();
    const destination = target.value.trim();

    if (!name || !server || !token || !destination) {
        showNotice(t('required'), true);
        return;
    }

    saveButton.disabled = true;
    saveButton.textContent = t('saving');

    try {
        const payload = {
            name,
            settings: {
                homeserver_url: server,
                access_token: token,
                target: destination
            },
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

function updateTokenToggle() {
    const visible = accessToken.type === 'text';
    toggleToken.textContent = t(visible ? 'hide' : 'show');
    toggleToken.setAttribute('aria-label', toggleToken.textContent);
}

toggleToken.addEventListener('click', () => {
    accessToken.type = accessToken.type === 'password' ? 'text' : 'password';
    updateTokenToggle();
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
