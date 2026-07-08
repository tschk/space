import { describe, it, expect, mock, beforeEach, beforeAll, afterAll } from "bun:test";
import * as path from "path";

const mockGhosttyInit = mock(() => Promise.resolve());
let mockTerminalInstances = [];
let mockFitAddonInstances = [];

class MockTerminal {
  constructor(options) {
    this.options = options || {};
    this.addons = [];
    this.opened = false;
    this.written = [];
    this.focused = false;
    this.dataListeners = [];
    mockTerminalInstances.push(this);
  }
  loadAddon(addon) {
    this.addons.push(addon);
  }
  open(element) {
    this.opened = true;
    this.element = element;
  }
  writeln(text) {
    this.written.push(text);
  }
  write(text) {
    this.written.push(text);
  }
  focus() {
    this.focused = true;
  }
  onData(cb) {
    this.dataListeners.push(cb);
  }
  resize(cols, rows) {
    this.cols = cols;
    this.rows = rows;
  }
}

class MockFitAddon {
  constructor() {
    this.fitted = false;
    this.observeResized = false;
    mockFitAddonInstances.push(this);
  }
  fit() {
    this.fitted = true;
  }
  observeResize() {
    this.observeResized = true;
  }
}

mock.module("ghostty-web", () => {
  return {
    init: mockGhosttyInit,
    Terminal: MockTerminal,
    FitAddon: MockFitAddon
  };
});

let mockV86Instances = [];
class MockV86 {
  constructor(options) {
    this.options = options;
    this.listeners = {};
    mockV86Instances.push(this);
  }
  add_listener(event, cb) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(cb);
  }
  serial0_send(data) {
    if (!this.sent) this.sent = [];
    this.sent.push(data);
  }
}

mock.module("/v86/libv86.mjs?v=dev", () => {
  return { V86: MockV86 };
});
mock.module("/v86/libv86.mjs?v=test-build", () => {
  return { V86: MockV86 };
});


describe("shell.js", () => {
  let domElements = {};
  let windowListeners = {};
  let originalWindow;
  let originalDocument;
  let originalFetch;
  let mockedFetchText = "dev";
  let mockedFetchOk = true;
  let importCounter = 0;

  beforeAll(() => {
    originalWindow = global.window;
    originalDocument = global.document;
    originalFetch = global.fetch;

    global.window = {
      innerWidth: 800,
      innerHeight: 600,
      addEventListener: (event, cb) => {
        if (!windowListeners[event]) windowListeners[event] = [];
        windowListeners[event].push(cb);
      }
    };
    global.document = {
      getElementById: (id) => {
        if (!domElements[id]) {
            domElements[id] = {
              id,
              hidden: false,
              value: 0,
              textContent: "",
              appendChild: mock(),
              addEventListener: mock(),
              style: {},
              focus: mock()
            };
        }
        return domElements[id];
      },
      createElement: (tag) => {
        return {
          tagName: tag,
          setAttribute: mock(),
          addEventListener: mock(),
          className: ""
        };
      },
      fonts: {
        load: mock(() => Promise.resolve()),
        ready: Promise.resolve()
      }
    };
    global.fetch = mock((url) => {
      if (url === "/v86/kernel-build-id.txt") {
        return Promise.resolve({
          ok: mockedFetchOk,
          text: () => Promise.resolve(mockedFetchText)
        });
      }
      return Promise.reject(new Error("Not found"));
    });
  });

  afterAll(() => {
    global.window = originalWindow;
    global.document = originalDocument;
    global.fetch = originalFetch;
  });

  beforeEach(() => {
    mockTerminalInstances = [];
    mockFitAddonInstances = [];
    mockV86Instances = [];
    domElements = {};
    windowListeners = {};
    mockGhosttyInit.mockClear();
    mockedFetchText = "dev";
    mockedFetchOk = true;
  });

  it("should initialize terminal and v86 on successful build id fetch", async () => {
    mockedFetchText = "test-build";

    // Dynamically importing with a counter bypasses cache
    await import("./shell.js?t=" + (++importCounter));

    // Terminal
    expect(mockTerminalInstances.length).toBe(1);
    const term = mockTerminalInstances[0];
    expect(term.opened).toBe(true);
    expect(term.addons[0]).toBeInstanceOf(MockFitAddon);

    // V86 Emulator
    expect(mockV86Instances.length).toBe(1);
    const emu = mockV86Instances[0];
    expect(emu.options.autostart).toBe(true);

    // DOM Updates
    expect(domElements["boot_status"].hidden).toBe(false); // setStatus called
    expect(domElements["boot_message"].textContent).toContain("loading Space");
  });

  it("should handle download progress", async () => {
    await import("./shell.js?t=" + (++importCounter));
    const emu = mockV86Instances[0];

    const progressListener = emu.listeners["download-progress"][0];
    expect(progressListener).toBeDefined();

    progressListener({
      lengthComputable: true,
      total: 100,
      loaded: 50,
      file_index: 0,
      file_count: 2
    });

    // (0 + 50/100) / 2 = 25%
    expect(domElements["boot_progress"].value).toBe(25);
    expect(domElements["boot_progress"].textContent).toBe("25%");
    expect(domElements["boot_message"].textContent).toBe("loading Space 25%");
  });

  it("should handle emulator ready and finish status", async () => {
    await import("./shell.js?t=" + (++importCounter));
    const emu = mockV86Instances[0];

    const readyListener = emu.listeners["emulator-ready"][0];
    expect(readyListener).toBeDefined();

    const originalSetTimeout = global.setTimeout;
    let timeoutCb;
    global.setTimeout = (cb, delay) => { timeoutCb = cb; };

    try {
      readyListener();

      expect(domElements["boot_progress"].value).toBe(100);
      expect(domElements["boot_message"].textContent).toBe("booting Space");
      expect(mockTerminalInstances[0].focused).toBe(true);

      // Trigger setTimeout inside finishStatus
      timeoutCb();
      expect(domElements["boot_status"].hidden).toBe(true);
    } finally {
      global.setTimeout = originalSetTimeout;
    }
  });

  it("should send serial data to terminal or legacy keyboard", async () => {
    await import("./shell.js?t=" + (++importCounter));
    const emu = mockV86Instances[0];

    const serialListener = emu.listeners["serial0-output-byte"][0];
    expect(serialListener).toBeDefined();

    // Sends 0xff - ignores
    serialListener(0xff);
    expect(mockTerminalInstances[0].written.length).toBe(1); // Only "Space loading…" is written

    // Sends valid byte
    serialListener(65); // 'A'
    expect(mockTerminalInstances[0].written.length).toBe(2);
    expect(mockTerminalInstances[0].written[1]).toBe("A");
  });

  it("should handle v86 download error", async () => {
    await import("./shell.js?t=" + (++importCounter));
    const emu = mockV86Instances[0];

    const errorListener = emu.listeners["download-error"][0];
    expect(errorListener).toBeDefined();

    const originalConsoleError = console.error;
    let loggedError;
    console.error = (msg, err) => { loggedError = err; };

    try {
      errorListener(new Error("Network Error"));

      expect(domElements["boot_message"].textContent).toBe("failed to load Space");
      expect(loggedError.message).toBe("Network Error");
    } finally {
      console.error = originalConsoleError;
    }
  });

  it("should throw error if screen mount point is missing", async () => {
    const origGetElementById = global.document.getElementById;
    global.document.getElementById = (id) => {
      if (id === "screen_container") return null;
      return origGetElementById(id);
    };

    let error;
    try {
      await import("./shell.js?t=" + (++importCounter));
    } catch(e) {
      error = e;
    } finally {
      global.document.getElementById = origGetElementById;
    }
    expect(error).toBeDefined();
    expect(error.message).toBe("Space shell mount point is missing");
  });
});
