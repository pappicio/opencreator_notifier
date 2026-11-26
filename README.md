# OpenCreator Notifier

OpenCreator Notifier is a plugin for OpenCreator / Flashforge Creator 5 that provides Telegram notifications, printer event monitoring, and configurable macro notifications through [Apprise](https://github.com/caronc/apprise).

The plugin integrates with Moonraker and Klipper while keeping its application, configuration, data, logs, and Python environment inside its own plugin directory.

---

## Features

- Telegram notifications through Apprise.
- Printer event notifications.
- Configurable notification preferences.
- Monitoring of existing Klipper macros.
- Plugin-managed custom macros.
- Per-macro notification preferences.
- Optional screenshot attachments for macro notifications.
- Support for duplicate macro definitions without duplicating notification settings.
- Background notification processing to avoid blocking macro execution.
- Dedicated Python virtual environment.
- Plugin-managed Moonraker secrets integration.
- English and Italian interface translations.

---

## Notifications

OpenCreator Notifier uses Apprise as its notification backend.

Apprise provides a unified notification interface and supports many notification services. This plugin currently uses Telegram as its notification destination.

The notification system is configured through the plugin's web interface.

Notification preferences allow the user to select which printer events should generate notifications and configure the available notification options.

---

## Macro Notifications

The plugin provides separate management pages for existing macros and custom macros.

### Existing Macros

Existing macros are discovered from the Klipper configuration files reachable through the printer configuration.

The plugin:

- Scans available macro definitions.
- Allows the user to select which macros are monitored.
- Allows notification preferences to be configured individually.
- Supports optional screenshot attachments.
- Groups definitions with the same macro name into a single entry.
- Displays the configuration files and locations where duplicate definitions were found.

Duplicate definitions of the same macro name share a single notification preference.

The plugin does not modify existing macro definitions in order to add notifications.

### Custom Macros

Custom macros are managed by OpenCreator Notifier and stored in the plugin-managed macro configuration.

Users can:

- Create custom macros.
- Edit existing custom macros.
- Delete custom macros.
- Enable or disable monitoring.
- Enable or disable notifications.
- Configure optional screenshot attachments.
- View the macro configuration.

Custom macro definitions are managed separately from the printer's existing macros.

The plugin checks macro names to avoid conflicts with existing macros and duplicate custom macro names.

---

## Screenshot Notifications

Macro notifications can optionally include a printer screenshot.

Screenshot attachment behavior depends on:

- The screenshot preference configured for the individual macro.
- The global screenshot/photo notification setting.
- Screenshot availability at the time the notification is generated.

If screenshots are disabled globally, macro notifications will not attach images even when an individual macro has screenshot notifications enabled.

---

## Non-blocking Notifications

Macro notifications are processed asynchronously.

When a monitored macro executes successfully, the Klipper component queues the notification event for background processing.

This prevents notification network requests from blocking the normal macro execution path.

Notifications are not generated when the monitored macro execution fails before returning successfully.

---

## Installation

OpenCreator plugins are managed through the OpenCreator Plugin Manager.

### Install from a local directory

If the plugin files are available locally:

    oc-plugin install [/path/to/opencreator_notifier](https://github.com/pappicio/opencreator_notifier)



The Plugin Manager handles plugin installation and synchronization of the declared Klipper component and configuration files.

### Installation preparation

The plugin installation script prepares the required directories and Python environment.

The installation process:

1. Creates plugin-owned data, log, and backup directories.
2. Verifies the Moonraker secrets integration path.
3. Creates the plugin's Python virtual environment if it does not already exist.
4. Installs the required Apprise version and dependencies when needed.
5. Verifies that Apprise and Requests are available.

---

## Python Environment

OpenCreator Notifier uses an isolated Python virtual environment located inside the plugin directory.

    opencreator_notifier/
    +-- apprise-venv/

The environment is created using the Creator 5 Python interpreter:

    /usr/data/python-hf/bin/python3

The plugin does not require the virtual environment to be manually activated.

Instead, the service uses the virtual environment's interpreter directly:

    apprise-venv/bin/python

This keeps the plugin's Python dependencies isolated from the system Python installation and other OpenCreator plugins.

### Apprise

The plugin currently installs:

    Apprise 2.3.0

Apprise is installed inside the plugin virtual environment together with its required dependencies.

The installation is version-pinned to avoid unexpected changes caused by upstream releases.

### Core dependencies

Apprise's core dependencies include:

- certifi
- requests
- urllib3
- requests-oauthlib
- click
- Markdown
- PyYAML

Additional packages required by these dependencies are installed automatically by pip.

The plugin does not install Apprise's optional development, testing, or all-plugin dependency groups.

---

## Configuration and Data

Plugin-owned configuration and runtime data are stored inside the plugin directory.

The plugin uses its own data directory for configuration and secrets-related data.

The plugin also integrates with Moonraker's standard secrets location through a plugin-managed symbolic link.

The installation and uninstallation scripts check the target paths before creating or removing links. Existing unrelated files or links are not intentionally overwritten.

Sensitive information such as Telegram credentials should never be committed to the repository.

---

## Plugin Structure

The plugin directory contains the application, frontend, configuration, Klipper component, scripts, and runtime data.

    opencreator_notifier/
    +-- app/
    ¦   +-- telegram_notify.py
    +-- config/
    ¦   +-- oc_notifier.cfg
    +-- klippy/
    ¦   +-- oc_notifier.py
    +-- scripts/
    ¦   +-- install.sh
    ¦   +-- update.sh
    ¦   +-- start.sh
    ¦   +-- uninstall.sh
    +-- web/
    ¦   +-- index.html
    ¦   +-- languages/
    ¦       +-- en.json
    ¦       +-- it.json
    +-- data/
    +-- logs/
    +-- backup/
    +-- apprise-venv/
    +-- manifest.json

The exact contents may change between plugin releases.

---

## Updating

Updates are handled through the OpenCreator Plugin Manager.

The plugin's update preparation script reuses the installation logic to verify and prepare the Python environment.

If the correct Apprise version is already installed and working, the installation script does not reinstall it unnecessarily.

This helps avoid unnecessary downloads and reduces update time.

---

## Uninstallation

Uninstallation is handled by the OpenCreator Plugin Manager.

The plugin's uninstall script:

- Removes the plugin-owned Moonraker secrets symbolic link when it matches the expected target.
- Leaves unrelated files and links untouched.
- Removes the plugin's dedicated Python virtual environment.
- Preserves plugin configuration and data during the uninstall preparation step.

The Plugin Manager is responsible for removing plugin-managed Klipper synchronization links and completing plugin removal.

---

## Troubleshooting

### Plugin service does not start

Check the plugin status:

    oc-plugin status opencreator_notifier

Check the plugin logs:

    oc-plugin logs opencreator_notifier

Verify that the plugin's Python environment exists:

    ls -l apprise-venv/bin/python

### Apprise is missing

Run the plugin installation preparation script:

    sh scripts/install.sh

The script verifies the virtual environment and installs the pinned Apprise version when necessary.

### Notifications are not received

Verify:

- Telegram configuration and credentials.
- The selected notification events.
- The plugin service status.
- Network connectivity.
- The configured macro notification preferences. 
- Whether screenshot notifications are enabled globally and for the selected macro.

### Macro notifications are not triggered

Verify that:

- The macro is listed in the macro management page.
- Monitoring is enabled for the macro.
- Notifications are enabled.
- Klipper has loaded the OpenCreator Notifier component.
- The macro completes successfully.

---

## Development and Safety

OpenCreator Notifier is designed to manage its own files and configuration.

Existing printer macro definitions are not rewritten to insert notification code.

Plugin installation, update, and removal are designed to operate on plugin-owned resources and to avoid replacing unrelated files.

Changes to the plugin should be tested on a compatible OpenCreator / Creator 5 installation before release.

---

## License

See the repository's license file for licensing information.
