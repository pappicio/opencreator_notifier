(async () => {
    const params = new URLSearchParams(location.search);
    const serviceId = params.get("service_id");
    let savedServiceId = serviceId || null;

    const t = key => window.OCNotifierI18n.t("provider_prowl_" + key);
    const $ = id => document.getElementById(id);

    await window.OCNotifierI18nReady;

    document.documentElement.lang = window.OCNotifierI18n.language;
    document.title = t("title");
    $("page-description").textContent = t("description");
    $("label-service-name").textContent = t("serviceName");
    $("label-apikey").textContent = t("apikey");
    $("label-providerkey").textContent = t("providerkey");
    $("apikey-help").textContent = t("apikeyHelp");
    $("providerkey-help").textContent = t("providerkeyHelp");
    $("label-priority").textContent = t("priority");
    $("label-enabled").textContent = t("enabled");
    $("save-button").textContent = t("save");
    $("test-button").textContent = t("test");
    $("cancel-button").textContent = t("cancel");
    $("back-button").textContent = t("back");
    $("toggle-apikey").textContent = t("show");
    $("service-name").placeholder = t("namePlaceholder");

    for (const option of $("priority").options) {
        if (["normal", "low", "moderate", "high", "emergency"].includes(option.value)) {
            option.textContent = t(option.value);
        }
    }

    const notice = (message, type = "") => {
        $("notice").textContent = message;
        $("notice").className = type;
    };

    async function request(url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: { "Content-Type": "application/json", ...(options.headers || {}) }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.ok === false) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }
        return data;
    }

    async function loadConfig() {
        if (!serviceId) return;
        try {
            const query = new URLSearchParams({ service_id: serviceId });
            const data = await request(`/api/provider/prowl/config?${query}`);
            const service = data.service || {};
            const settings = service.settings || {};
            $("service-name").value = service.name || "";
            $("apikey").value = settings.apikey || "";
            $("providerkey").value = settings.providerkey || "";
            $("priority").value = settings.priority || "normal";
            $("enabled").checked = service.enabled !== false;
        } catch (error) {
            notice(`${t("loadError")} ${error.message}`, "error");
        }
    }

    $("toggle-apikey").addEventListener("click", () => {
        const field = $("apikey");
        const visible = field.type === "password";
        field.type = visible ? "text" : "password";
        $("toggle-apikey").textContent = visible ? t("hide") : t("show");
    });

    $("provider-form").addEventListener("submit", async event => {
        event.preventDefault();
        const apikey = $("apikey").value.trim();
        const providerkey = $("providerkey").value.trim();

        if (!/^[A-Za-z0-9]{40}$/.test(apikey)) {
            notice(t("required"), "error");
            $("apikey").focus();
            return;
        }
        if (providerkey && !/^[A-Za-z0-9]{40}$/.test(providerkey)) {
            notice(t("invalidProvider"), "error");
            $("providerkey").focus();
            return;
        }

        const payload = {
            name: $("service-name").value.trim(),
            settings: { apikey, providerkey, priority: $("priority").value },
            enabled: $("enabled").checked
        };
        if (savedServiceId) payload.service_id = savedServiceId;

        $("save-button").disabled = true;
        $("save-button").textContent = t("saving");
        notice("");
        try {
            const data = await request("/api/provider/prowl/config", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            savedServiceId = data.service_id || savedServiceId;
            notice(t("saved"), "success");
        } catch (error) {
            notice(`${t("saveError")} ${error.message}`, "error");
        } finally {
            $("save-button").disabled = false;
            $("save-button").textContent = t("save");
        }
    });

    $("test-button").addEventListener("click", async () => {
        if (!savedServiceId) {
            notice(t("saveFirst"), "error");
            return;
        }
        notice(t("testing"));
        $("test-button").disabled = true;
        try {
            await request("/api/test", {
                method: "POST",
                body: JSON.stringify({ service_id: savedServiceId })
            });
            notice(t("testSent"), "success");
        } catch (error) {
            notice(`${t("testError")} ${error.message}`, "error");
        } finally {
            $("test-button").disabled = false;
        }
    });

    $("back-button").addEventListener("click", () => { window.location.href = "/"; });
    $("cancel-button").addEventListener("click", () => history.back());
    await loadConfig();
})();
