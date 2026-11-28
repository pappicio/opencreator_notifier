'use strict';

const API = '/api/provider/pushover/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id');
const t = key => window.OCNotifierI18n.t('provider_pushover_' + key);

const serviceName = document.getElementById('serviceName');
const userKey = document.getElementById('userKey');
const apiToken = document.getElementById('apiToken');
const enabled = document.getElementById('enabled');
const saveButton = document.getElementById('saveButton');
const testButton = document.getElementById('testButton');
const notice = document.getElementById('notice');
const toggleUserKey = document.getElementById('toggleUserKey');
const toggleApiToken = document.getElementById('toggleApiToken');

function applyLanguage() {
    document.documentElement.lang = window.OCNotifierI18n.language;
    document.querySelectorAll('[data-i18n]').forEach(element => {
        element.textContent = t(element.dataset.i18n);
    });
    updateToggle(userKey, toggleUserKey);
    updateToggle(apiToken, toggleApiToken);
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
        userKey.value = settings.user_key || '';
        apiToken.value = settings.api_token || '';
        enabled.checked = service.enabled !== false;
        testButton.disabled = !serviceId || !enabled.checked;
    } catch (error) {
        showNotice(error.message || t('error'), true);
    }
}

async function saveConfiguration() {
    const name = serviceName.value.trim();
    const key = userKey.value.trim();
    const token = apiToken.value.trim();

    if (!name || !key || !token) {
        showNotice(t('required'), true);
        return;
    }

    saveButton.disabled = true;
    saveButton.textContent = t('saving');

    try {
        const payload = {
            name,
            settings: {
                user_key: key,
                api_token: token
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

function updateToggle(input, button) {
    const visible = input.type === 'text';
    button.textContent = t(visible ? 'hide' : 'show');
    button.setAttribute('aria-label', button.textContent);
}

function setupToggle(input, button) {
    button.addEventListener('click', () => {
        input.type = input.type === 'password' ? 'text' : 'password';
        updateToggle(input, button);
    });
}

setupToggle(userKey, toggleUserKey);
setupToggle(apiToken, toggleApiToken);

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

async function initialize() {
    await window.OCNotifierI18nReady;
    applyLanguage();
    await loadConfiguration();
}

initialize().catch(error => {
    showNotice(error.message || t('error'), true);
});
