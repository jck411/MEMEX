---
name: mobile-device-settings
description: Manage or inspect Jack's Pixel phone and Pixel Watch settings through ADB. Use when he asks to change, diagnose, verify, or automate a setting or UI behavior on either device; do not use for ordinary wiki edits about the devices.
---

# Mobile Device Settings

Use the named-device helper at
`/home/jack/REPOS/NETWORK/android/device`. It owns target resolution and
connection recovery; do not hard-code an ADB serial or changing wireless port.

## Workflow

1. Run `/home/jack/REPOS/NETWORK/android/device status <target>`, where target
   is `phone` or `watch`.
2. Inspect the current value before changing it. Prefer stable Android
   interfaces such as `settings`, `cmd`, `am`, and `pm`:
   `.../device shell <target> -- <command>`.
3. When a setting has no reliable shell interface, use `.../device ui
   <target>` and target-specific `input` commands. Take a screenshot when the
   UI hierarchy is insufficient.
4. Make the narrowest change that achieves Jack's request, then read the
   setting or UI state back. Return the device to its home screen after remote
   UI navigation.

`.../device adb <target> -- <adb arguments>` supports target-specific ADB
operations that do not fit the shell wrapper.

## Standing Authorization

Jack prioritizes convenience and authorizes routine, reversible phone and
watch settings inspection and changes without an extra confirmation. This
includes remote UI navigation, screenshots used to inspect settings, and
ordinary permission or notification-policy changes.

Require explicit authorization immediately before a factory reset, bootloader
or recovery change, reboot or power-off, credential or ADB-key rotation,
changing whether ADB authorizations expire, enabling a new network ADB
transport, eSIM/cellular-plan change, app uninstall or app-data clearing, data
deletion, or a change that could break the only available device connection.
Verify the exact target model before every mutation; the helper does this
automatically.

## Connectivity

- `phone` is the Pixel 11 Pro XL, prefers USB, and falls back to secure wireless ADB.
- `watch` is the Pixel Watch 5 and uses secure wireless ADB.
- Android 17 trusted-network auto-reconnection requires ADB 37 or newer. On
  the workstation, `adb` resolves through `~/.local/bin/adb`.
- Stable IPs come from
  `/home/jack/REPOS/NETWORK/dhcp/reservations.json`. Runtime wireless
  endpoints stay outside Git under
  `~/.local/state/homelab/android-devices.json`.
- If the helper reports that pairing is required, ask Jack only for the
  temporary pairing endpoint/code and then the connection endpoint. Use
  `.../device pair` and `.../device connect --endpoint`; do not ask him to
  run terminal commands.
