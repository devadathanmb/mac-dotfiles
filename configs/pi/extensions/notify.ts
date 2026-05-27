/**
 * Pi Notify Extension
 *
 * Sends a native terminal notification when Pi agent is done and waiting for input.
 * Supports multiple terminal protocols:
 * - OSC 777: Ghostty, iTerm2, WezTerm, rxvt-unicode
 * - OSC 99: Kitty
 * - Windows toast: Windows Terminal (WSL)
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { execFile } from "node:child_process";

function windowsToastScript(title: string, body: string): string {
  const type = "Windows.UI.Notifications";
  const mgr = `[${type}.ToastNotificationManager, ${type}, ContentType = WindowsRuntime]`;
  const template = `[${type}.ToastTemplateType]::ToastText01`;
  const toast = `[${type}.ToastNotification]::new($xml)`;
  return [
    `${mgr} > $null`,
    `$xml = [${type}.ToastNotificationManager]::GetTemplateContent(${template})`,
    `$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('${body}')) > $null`,
    `[${type}.ToastNotificationManager]::CreateToastNotifier('${title}').Show(${toast})`,
  ].join("; ");
}

function notifyOSC777(title: string, body: string): void {
  process.stdout.write(`\x1b]777;notify;${sanitizeForOSC(title)};${sanitizeForOSC(body)}\x07`);
}

function notifyOSC99(title: string, body: string): void {
  // Kitty OSC 99: i=notification id, d=1 means done, p=body for second part
  process.stdout.write(`\x1b]99;i=1:d=1;${sanitizeForOSC(title)}\x1b\\`);
  process.stdout.write(`\x1b]99;i=1:p=body;${sanitizeForOSC(body)}\x1b\\`);
}

function notifyWindows(title: string, body: string): void {
  execFile("powershell.exe", [
    "-NoProfile",
    "-Command",
    windowsToastScript(title, sanitizeForPowerShell(body)),
  ]);
}

function notify(title: string, body: string): void {
  if (process.env.WT_SESSION) {
    notifyWindows(title, body);
  } else if (process.env.KITTY_WINDOW_ID) {
    notifyOSC99(title, body);
  } else {
    notifyOSC777(title, body);
  }
}

/** Strip OSC protocol delimiters and control characters from notification text. */
function sanitizeForOSC(text: string): string {
  return text.replace(/[;\x07\x1b]/g, "");
}

/** Escape single quotes for PowerShell string interpolation ('' = literal '). */
function sanitizeForPowerShell(text: string): string {
  return text.replace(/'/g, "''");
}

export default function (pi: ExtensionAPI) {
  pi.on("agent_end", async () => {
    notify("Pi", "Ready for input");
  });
}
