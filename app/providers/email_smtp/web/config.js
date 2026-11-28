'use strict';

const API = '/api/provider/email_smtp/config';
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id');
const t = key => window.OCNotifierI18n.t('provider_email_smtp_' + key);

const fields = {
    serviceName: document.getElementById('serviceName'),
    smtpHost: document.getElementById('smtpHost'),
    security: document.getElementById('security'),
    port: document.getElementById('port'),
    username: document.getElementById('username'),
    password: document.getElementById('password'),
    senderEmail: document.getElementById('senderEmail'),
    senderName: document.getElementById('senderName'),
    recipients: document.getElementById('recipients'),
    enabled: document.getElementById('enabled')
};

const saveButton = document.getElementById('saveButton');
const testButton = document.getElementById('testButton');
const notice = document.getElementById('notice');
const togglePassword = document.getElementById('togglePassword');

function applyLanguage() {
    document.title = t('page_title');
    document.documentElement.lang = window.OCNotifierI18n.language;
    document.querySelectorAll('[data-i18n]').forEach(element => {
        element.textContent = t(element.dataset.i18n);
    });
    updatePasswordToggle();
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

function updatePort() {
    const defaults = {
        starttls: 587,
        ssl: 465,
        insecure: 25
    };

    fields.port.value = defaults[fields.security.value];
}

async function loadConfiguration() {
    try {
        const url = serviceId
            ? `${API}?service_id=${encodeURIComponent(serviceId)}`
            : API;

        const data = await request(url, { method: 'GET' });
        const service = data.service || data;
        const settings = service.settings || {};

        fields.serviceName.value = service.name || '';
        fields.smtpHost.value = settings.smtp_host || '';
        fields.security.value = settings.security || 'starttls';
        fields.port.value = settings.port || '';
        fields.username.value = settings.username || '';
        fields.password.value = settings.password || '';
        fields.senderEmail.value = settings.sender_email || '';
        fields.senderName.value = settings.sender_name || '';
        fields.recipients.value = Array.isArray(settings.recipients)
            ? settings.recipients.join(', ')
            : (settings.recipients || '');

        fields.enabled.checked = service.enabled !== false;
        testButton.disabled = !serviceId || !fields.enabled.checked;

        updatePasswordToggle();
    } catch (error) {
        showNotice(error.message || t('error'), true);
    }
}

async function saveConfiguration() {
    const name = fields.serviceName.value.trim();
    const username = fields.username.value.trim();
    const password = fields.password.value;

    if (
        !name ||
        !fields.smtpHost.value.trim() ||
        !fields.senderEmail.value.trim() ||
        !fields.recipients.value.trim()
    ) {
        showNotice(t('required'), true);
        return;
    }

    if (Boolean(username) !== Boolean(password)) {
        showNotice(t('auth_pair'), true);
        return;
    }

    saveButton.disabled = true;
    saveButton.textContent = t('saving');

    try {
        const payload = {
            name,
            settings: {
                smtp_host: fields.smtpHost.value.trim(),
                security: fields.security.value,
                port: fields.port.value,
                username,
                password,
                sender_email: fields.senderEmail.value.trim(),
                sender_name: fields.senderName.value.trim(),
                recipients: fields.recipients.value.trim()
            },
            enabled: fields.enabled.checked
        };

        if (serviceId) payload.service_id = serviceId;

        const data = await request(API, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        showNotice(t('saved'));
        alert(t('saved'));

        testButton.disabled = !fields.enabled.checked;

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
        testButton.disabled = !fields.enabled.checked;
    }
}

function updatePasswordToggle() {
    const visible = fields.password.type === 'text';
    togglePassword.textContent = t(visible ? 'hide' : 'show');
    togglePassword.setAttribute('aria-label', togglePassword.textContent);
}

togglePassword.addEventListener('click', () => {
    fields.password.type = fields.password.type === 'password' ? 'text' : 'password';
    updatePasswordToggle();
});

fields.security.addEventListener('change', updatePort);

fields.enabled.addEventListener('change', () => {
    testButton.disabled = !serviceId || !fields.enabled.checked;
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
        showNotice('Language initialization failed: ' + error.message, true);
        saveButton.disabled = true;
        testButton.disabled = true;
    }
})();
