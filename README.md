# SHYS Remote

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Home Assistant integration to learn, store and replay remote control signals through the
built-in [`infrared`](https://www.home-assistant.io/integrations/infrared/)
integration.

- **Output signals** become `button` entities and send learned codes.
- **Input signals** become pulsing `binary_sensor` entities when a matching code
  is received.
- **Flipper-IRDB import** lets you search a bundled remote database and import
  all supported buttons during device setup.

## Requirements

- Home Assistant **2025.2** or newer
- The **Infrared** integration configured with at least one receiver and one
  emitter entity

## Installation

### HACS (recommended after repository publish)

1. Add this repository as a [custom HACS repository](https://hacs.xyz/docs/faq/custom_repositories/).
2. Install **SHYS Remote**.
3. Restart Home Assistant.

### Manual

Copy `custom_components/shys_remote` into your Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Quick start

1. Open **Settings → Devices & services → Add integration**.
2. Search for **SHYS Remote** and complete the setup wizard.
3. Open the integration card and choose **Add device**.
4. Enter a device name and select your `infrared` receiver and transmitter.
5. Either:
   - learn signals manually via **Manage device → Learn signal**, or
   - choose **Import from IR database** to search Flipper-IRDB.

Each logical device appears as its own device in Home Assistant. Every learned
output signal is exposed as a button; every input signal as a binary sensor.

## Integration options

Under **Configure** on the integration card:

| Option | Description |
| --- | --- |
| Input pulse duration | How long input binary sensors stay `on` after a match |
| Signal match tolerance | Allowed timing deviation when matching received patterns |
| Input debounce | Minimum time between two triggers of the same input signal |

## Services

| Service | Description |
| --- | --- |
| `shys_remote.learn` | Learn a new signal on a device |
| `shys_remote.send` | Send a learned output signal |
| `shys_remote.delete` | Delete a learned signal and its entity |

The `device` parameter is the device **slug** shown in the subentry settings
(for example `soundbar_buro`).

Example:

```yaml
service: shys_remote.learn
data:
  device: soundbar_buro
  name: power
  direction: output
  timeout: 15
```

## Flipper-IRDB

The search index is shipped locally in `data/irdb_index.json`. Individual `.ir`
files are downloaded from GitHub only when you import a remote.

- Source: [Flipper-IRDB](https://github.com/Lucaslhm/Flipper-IRDB)
- License: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Details: see [`data/IRDB_NOTICE.md`](custom_components/shys_remote/data/IRDB_NOTICE.md)

## Removal

1. Delete the **SHYS Remote** integration under **Settings → Devices & services**.
2. Remove `custom_components/shys_remote` from your configuration directory.
3. Restart Home Assistant.

Optional: delete `.storage/shys_remote` if you no longer need learned signals.

## License

Integration code: [MIT](LICENSE)

Flipper-IRDB data: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)

---

# SHYS Remote (Deutsch)

Home-Assistant-Integration zum Anlernen, Speichern und Senden von
Fernbedienungssignalen über die eingebaute `infrared`-Integration.

- **Output:** Buttons zum Senden
- **Input:** Binärsensoren bei erkanntem Signal
- **Flipper-IRDB:** Lokale Suche und Import beim Gerät anlegen

### Kurzstart

1. Integration **SHYS Remote** hinzufügen
2. Unter der Integration **Gerät hinzufügen**
3. Receiver und Transmitter wählen
4. Signale manuell anlernen oder aus der Flipper-IRDB importieren

Dokumentation in Home Assistant: Integrationskarte → **Dokumentation** (Link
aus `manifest.json`).
