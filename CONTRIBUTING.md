# Contributing

Use fictional profiles, PDFs, employer pages and job lists. Never commit real applicant data, credentials, browser sessions, runtime state or generated member configurations.

Create an isolated environment, install `.[t3,test]`, install Playwright Chromium, and run the checks documented in README. Browser fixtures must use their own profiles and synthetic application pages. Do not submit a real application to prove a change.

Keep source facts, extracted resume text, model drafts, member confirmations and submission reports distinct. Model output cannot confirm its own answer or grant submission authority. The MCP connector must not acquire a confirm/submit/account-creation tool.

Changes to storage, native-message validation, exact packet identity, interruption recovery, consent/attestation handling or external actions need focused maintainer review and a concrete failing-input regression. Do not resolve an uncertain action by deleting its journal or replaying it.

The application is for Apple Silicon Macs. The Python/browser core is tested on Linux for isolated development. Build the actual Mac artifact with a portable arm64 runtime and validate native minimum OS targets; a successful Python test is not proof of an installable Mac app.

The selected engine and member-only adapters are part of the standalone source. Do not restore personal standing rules, account helpers or the original private hub dependencies. Preserve font and runtime license notices.

For a bug report, include the app version, macOS version, visible error, expected behavior and a fictional reproduction if possible. Redact employer answers, private application URLs, PDFs, login tokens and verification codes.
