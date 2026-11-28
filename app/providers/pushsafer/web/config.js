(async () => {
    const params = new URLSearchParams(location.search);
    const serviceId = params.get("service_id");
    let savedServiceId = serviceId || null;

    await window.OCNotifierI18nReady;
    const t = key => window.OCNotifierI18n.t("provider_pushsafer_" + key);

    const $ = id => document.getElementById(id);
    const notice = (message, type = "") => {
        $("notice").textContent = message;
        $("notice").className = type;
    };

    document.documentElement.lang = window.OCNotifierI18n.language;
    document.title = t("title");
    $("page-description").textContent = t("description");
    $("label-service-name").textContent = t("serviceName");
    $("label-privatekey").textContent = t("privatekey");
    $("label-targets").textContent = t("targets");
    $("targets").placeholder = t("targetsPlaceholder");
    $("targets-help").textContent = t("targetsHelp");
    $("label-priority").textContent = t("priority");
    $("label-sound").textContent = t("sound");
    $("label-vibration").textContent = t("vibration");
    $("label-enabled").textContent = t("enabled");
    $("save-button").textContent = t("save");
    $("test-button").textContent = t("test");
    $("cancel-button").textContent = t("cancel");
    $("back-button").textContent = t("back");
    $("toggle-key").textContent = t("show");
    $("service-name").placeholder = t("namePlaceholder");

    const optionLabels = {
        priority: ["default", "low", "medium", "normal", "high", "emergency"],
        sound: ["default", "silent", "bell", "chime", "doorbell", "alarmarmed",
            "alarmdisarmed", "beep", "sirens", "warning", "welcome", "yes", "no"],
        vibration: ["default", "low", "normal", "high"]
    };
    for (const [field, labels] of Object.entries(optionLabels)) {
        [...$(field).options].forEach((option, index) => {
            const key = labels[index];
            if (key && t(key)) option.textContent = t(key);
        });
    }

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
            const data = await request(`/api/provider/pushsafer/config?${query}`);
            const service = data.service || {};
            const settings = service.settings || {};

            $("service-name").value = service.name || "";
            $("privatekey").value = settings.privatekey || "";
            $("targets").value = settings.targets || "";
            $("priority").value = settings.priority || "";
            $("sound").value = settings.sound || "";
            $("vibration").value = settings.vibration || "";
            $("enabled").checked = service.enabled !== false;
        } catch (error) {
            notice(`${t("loadError")} ${error.message}`, "error");
        }
    }

    $("toggle-key").addEventListener("click", () => {
        const field = $("privatekey");
        const visible = field.type === "password";
        field.type = visible ? "text" : "password";
        $("toggle-key").textContent = visible ? t("hide") : t("show");
    });

    $("provider-form").addEventListener("submit", async event => {
        event.preventDefault();
        const privatekey = $("privatekey").value.trim();
        if (!privatekey) {
            notice(t("required"), "error");
            $("privatekey").focus();
            return;
        }

        const payload = {
            name: $("service-name").value.trim(),
            settings: {
                privatekey,
                targets: $("targets").value.trim(),
                priority: $("priority").value,
                sound: $("sound").value,
                vibration: $("vibration").value
            },
            enabled: $("enabled").checked
        };
        if (savedServiceId) payload.service_id = savedServiceId;

        $("save-button").disabled = true;
        $("save-button").textContent = t("saving");
        notice("");
        try {
            const data = await request("/api/provider/pushsafer/config", {
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
            notice(t("saveBeforeTest"), "error");
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
