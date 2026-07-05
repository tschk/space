import "@fontsource/geist-mono/400.css";
import { init, Terminal, FitAddon } from "ghostty-web";

const bootStatus = document.getElementById("boot_status");
const bootMessage = document.getElementById("boot_message");
const bootProgress = document.getElementById("boot_progress");
const screen = document.getElementById("screen_container");
const legacyPre = document.getElementById("terminal");
const commandForm = document.getElementById("command_form");
const commandInput = document.getElementById("command_input");

let buildId = "dev";
try {
  const idRes = await fetch("/v86/kernel-build-id.txt", { cache: "no-store" });
  if (idRes.ok) {
    buildId = (await idRes.text()).trim() || buildId;
  }
} catch {
  /* ignore */
}

const asset = (path) => `${path}?v=${encodeURIComponent(buildId)}`;

let emulator;
let term;
let fitAddon;

function setStatus(message, percent) {
  if (bootMessage) {
    bootMessage.textContent = message;
  }
  if (bootProgress && Number.isFinite(percent)) {
    bootProgress.value = Math.max(0, Math.min(100, percent));
    bootProgress.textContent = `${Math.round(bootProgress.value)}%`;
  }
}

function finishStatus(message) {
  setStatus(message, 100);
  setTimeout(() => {
    if (bootStatus) {
      bootStatus.hidden = true;
    }
    applyTerminalScale();
  }, 700);
}

function sendSerial(data) {
  emulator?.serial0_send(data);
}

function computeTerminalMetrics() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  const pad = Math.min(72, Math.max(24, Math.min(w, h) * 0.06));
  const innerW = Math.max(200, w - pad * 2);
  const innerH = Math.max(120, h - pad * 2);
  const cols = Math.max(48, Math.floor(innerW / 8.2));
  const rows = Math.max(14, Math.floor(innerH / 18));
  const fromWidth = innerW / cols;
  const fromHeight = innerH / rows;
  const fontSize = Math.min(26, Math.max(11, Math.round(Math.min(fromWidth, fromHeight) * 0.92)));
  return { cols, rows, fontSize, pad };
}

function terminalSize() {
  const { cols, rows } = computeTerminalMetrics();
  return { cols, rows };
}

function terminalFontSize() {
  return computeTerminalMetrics().fontSize;
}

function applyTerminalScale() {
  if (!term || !fitAddon) {
    return;
  }
  const { fontSize } = computeTerminalMetrics();
  if (term.options && term.options.fontSize !== fontSize) {
    term.options.fontSize = fontSize;
  }
  fitAddon.fit();
  if (typeof term.resize === "function" && term.cols && term.rows) {
    term.resize(term.cols, term.rows);
  }
}

async function mountTerminal() {
  if (!screen) {
    return false;
  }
  if (legacyPre) {
    legacyPre.hidden = true;
  }
  if (commandForm) {
    commandForm.hidden = true;
  }

  await init();

  let host = document.getElementById("xterm_host");
  if (!host) {
    host = document.createElement("div");
    host.id = "xterm_host";
    host.className = "term-host";
    host.setAttribute("aria-label", "Space serial console");
    screen.appendChild(host);
  }

  term = new Terminal({
    fontSize: terminalFontSize(),
    fontFamily: '"Geist Mono", ui-monospace, monospace',
    cursorBlink: true,
    scrollback: 10000,
    allowTransparency: false,
    theme: {
      background: "#000000",
      foreground: "#e4e4e7",
      cursor: "#fafafa",
      cursorAccent: "#000000",
      selectionBackground: "#3f3f46",
      selectionForeground: "#fafafa",
    },
  });

  fitAddon = new FitAddon();
  term.loadAddon(fitAddon);
  term.open(host);
  applyTerminalScale();
  if (fitAddon.observeResize) {
    fitAddon.observeResize();
  }
  window.addEventListener("resize", () => {
    applyTerminalScale();
  });

  term.writeln("Space loading…");
  term.focus();
  term.onData(sendSerial);
  host.addEventListener("pointerdown", () => term.focus());
  return true;
}

function wireLegacyKeyboard() {
  if (!legacyPre) {
    return;
  }
  legacyPre.hidden = false;
  legacyPre.style.display = "block";
  legacyPre.textContent = "Space loading…\n";
  legacyPre.focus();

  commandForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const line = commandInput?.value ?? "";
    if (commandInput) {
      commandInput.value = "";
    }
    sendSerial(`${line}\r`);
    legacyPre.focus();
  });
}

if (!screen) {
  throw new Error("Space shell mount point is missing");
}

setStatus("loading Space", 0);
const useXterm = await mountTerminal();

try {
  const { V86 } = await import(asset("/v86/libv86.mjs"));

  emulator = new V86({
    wasm_path: asset("/v86/v86.wasm"),
    screen_container: screen,
    multiboot: { url: asset("/v86/space-multiboot.bin") },
    memory_size: 512 * 1024 * 1024,
    autostart: true,
  });

  emulator.add_listener("serial0-output-byte", (byte) => {
    const ch = String.fromCharCode(byte);
    if (term) {
      term.write(ch);
    }
    if (legacyPre) {
      legacyPre.textContent += ch;
      legacyPre.scrollTop = legacyPre.scrollHeight;
    }
  });

  if (!useXterm) {
    wireLegacyKeyboard();
  }

  emulator.add_listener("download-progress", (event) => {
    if (event.lengthComputable && event.total) {
      const percent = ((event.file_index + event.loaded / event.total) / event.file_count) * 100;
      setStatus(`loading Space ${Math.round(percent)}%`, percent);
      return;
    }
    setStatus("loading Space", bootProgress?.value || 0);
  });

  emulator.add_listener("download-error", (event) => {
    setStatus("failed to load Space", bootProgress?.value || 0);
    console.error("v86 download error", event);
  });

  emulator.add_listener("emulator-ready", () => {
    finishStatus("booting Space (serial + VGA if kernel enables it)");
    applyTerminalScale();
    term?.focus();
  });
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  setStatus(`failed: ${message}`, bootProgress?.value || 0);
  term?.writeln(`\r\nSpace failed to start: ${message}`);
  throw error;
}