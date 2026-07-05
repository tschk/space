import { init, Terminal, FitAddon } from "ghostty-web";

const bootStatus = document.getElementById("boot_status");
const bootMessage = document.getElementById("boot_message");
const bootProgress = document.getElementById("boot_progress");
const screen = document.getElementById("screen_container");
const legacyPre = document.getElementById("terminal");

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

const scancodeSet1 = {
  a: 0x1e, b: 0x30, c: 0x2e, d: 0x20, e: 0x12, f: 0x21, g: 0x22, h: 0x23,
  i: 0x17, j: 0x24, k: 0x25, l: 0x26, m: 0x32, n: 0x31, o: 0x18, p: 0x19,
  q: 0x10, r: 0x13, s: 0x1f, t: 0x14, u: 0x16, v: 0x2f, w: 0x11, x: 0x2d,
  y: 0x15, z: 0x2c,
  "0": 0x0b, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
  "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0a,
  "-": 0x0c, "=": 0x0d, ",": 0x33, ".": 0x34, "/": 0x35,
  " ": 0x39,
};

async function sendInput(data) {
  if (!emulator) return;
  const ps2 = emulator.v86?.cpu?.devices?.ps2;
  if (!ps2) return;
  ps2.enable_keyboard_stream = true;
  window.sendInputCount = (window.sendInputCount || 0) + 1;
  for (const ch of data) {
    if (ch === "\r" || ch === "\n") {
      ps2.kbd_send_code(0x1c);
      continue;
    }
    const make = scancodeSet1[ch];
    if (make) ps2.kbd_send_code(make);
  }
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

function applyTerminalScale() {
  if (!term || !fitAddon) return;
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
  if (!screen) return false;
  if (legacyPre) legacyPre.hidden = true;

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
    fontSize: computeTerminalMetrics().fontSize,
    fontFamily: 'GeistMono, ui-monospace, monospace',
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
      black: "#18181b",
      red: "#f87171",
      green: "#4ade80",
      yellow: "#facc15",
      blue: "#60a5fa",
      magenta: "#c084fc",
      cyan: "#22d3ee",
      white: "#e4e4e7",
      brightBlack: "#52525b",
      brightRed: "#fca5a5",
      brightGreen: "#86efac",
      brightYellow: "#fde047",
      brightBlue: "#93c5fd",
      brightMagenta: "#d8b4fe",
      brightCyan: "#67e8f9",
      brightWhite: "#fafafa",
    },
  });

  try {
    await document.fonts.load('1rem GeistMono');
  } catch {
    /* ignore */
  }

  fitAddon = new FitAddon();
  term.loadAddon(fitAddon);
  term.open(host);
  applyTerminalScale();
  if (fitAddon.observeResize) fitAddon.observeResize();
  window.addEventListener("resize", () => applyTerminalScale());

  term.focus();
  term.onData(sendInput);
  host.addEventListener("pointerdown", () => term.focus());
  return true;
}

function wireLegacyKeyboard() {
  if (!legacyPre) return;
  legacyPre.hidden = false;
  legacyPre.style.display = "block";
  legacyPre.textContent = "Space loading…\n";
  legacyPre.focus();

  legacyPre.addEventListener("keydown", (event) => {
    if (event.metaKey || event.altKey) return;
    if (event.ctrlKey) {
      const key = event.key.toLowerCase();
      if (key >= "a" && key <= "z") {
        sendInput(String.fromCharCode(key.charCodeAt(0) - 96));
        event.preventDefault();
      }
      return;
    }
    const keys = { Enter: "\r", Backspace: "\x7F", Tab: "\t" };
    if (keys[event.key]) {
      sendInput(keys[event.key]);
      event.preventDefault();
      return;
    }
    if (event.key.length === 1) {
      sendInput(event.key);
      event.preventDefault();
    }
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
  window.spaceEmulator = emulator;

  emulator.add_listener("serial0-output-byte", (byte) => {
    if (byte === 0xff) return;
    const ch = String.fromCharCode(byte);
    if (term) {
      term.write(ch);
      return;
    }
    if (legacyPre) {
      legacyPre.textContent += ch;
      legacyPre.scrollTop = legacyPre.scrollHeight;
    }
  });

  if (!useXterm) wireLegacyKeyboard();

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
  if (legacyPre) {
    legacyPre.textContent += `\nSpace failed to start: ${message}\n`;
  }
  throw error;
}
