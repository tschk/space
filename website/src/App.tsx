export const description = "Space nanokernel in the browser via v86.";

export const title = "Space";

export default function App() {
  return (
    <div data-moonshine-root="true">
      <header className="boot-top-bar" aria-label="Space links">
        <a
          href="https://github.com/tschk/space"
          target="_blank"
          rel="noopener noreferrer"
        >
          tschk/space
        </a>
        <span className="boot-top-sep" aria-hidden="true">
          ·
        </span>
        <a href="https://tsc.hk" target="_blank" rel="noopener noreferrer">
          tsc.hk
        </a>
      </header>
      <main id="screen_container" className="page-shell" aria-label="Space OS">
        <div className="hidden" />
        <canvas className="hidden" />
        <pre
          id="terminal"
          className="hidden"
          tabIndex={0}
          aria-label="Space console"
        />
        <section id="boot_status" className="boot-status" aria-live="polite">
          <p id="boot_message">loading Space shell</p>
          <meter id="boot_progress" min={0} max={100} value={0}>
            0%
          </meter>
        </section>
      </main>
      <footer className="site-credit">built with moonshine</footer>
    </div>
  );
}
