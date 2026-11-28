'use strict';

const API = '/api/provider/matrix/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id');
const t = key => window.OCNotifierI18n.t('provider_matrix_' + key);

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
    document.title = t('page_title');
    document.documentElement.lang = window.OCNotifierI18n.language;
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
            params.set('lang', window.OCNotifierI18n.language);
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

(async function initialize() {
    try {
        await window.OCNotifierI18nReady;
        applyLanguage();
        await loadConfiguration();
    } catch (error) {
        console.error('Language initialization failed:', error);
        saveButton.disabled = true;
        testButton.disabled = true;
    }
})();
