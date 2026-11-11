# Apply Desk

A private application desk for your club. Import opportunities, fill confirmed facts in Chrome, and connect T3 to draft answers from your profile and resume. Review each application and submit it in the employer's own tab.

**Mac release:** Apple Silicon (M1 or newer), targeting macOS 13+. Chrome is required for form preparation. T3 Code and your own model-provider account are optional for drafting. Python, Git and Terminal are not required to run the Mac app.

## Get started on a Mac

1. Open the disk image and drag **Apply Desk.app** into Applications. Open the app.
2. Confirm your profile and upload your resume PDF. This creates your private local workspace.
3. Press **Install Chrome support**. Follow the displayed steps to load the Apply Desk extension once in Chrome.
4. Add a job URL or import your club's CSV. Open the employer's application and click the Apply Desk extension.
5. Choose **Prepare this tab**. Confirmed facts and your reviewed resume fill automatically. Missing questions appear in your desk.
6. Answer missing questions yourself, or connect T3 to prepare drafts. Review each draft and press **Confirm this answer**.
7. Scan/prepare the employer form again. Review its actual fields, finish manual checks and submit yourself. You can then record the submission in Apply Desk.

The community app is ad-hoc signed and **not Apple notarized**. On first open, macOS may require **System Settings → Privacy & Security → Open Anyway** after you verify the release checksum. No command to disable Gatekeeper is needed or recommended.

Chrome's **Developer mode → Load unpacked** approval is a one-time browser step. The app displays the exact extension folder and provides a copy button. It installs its own `com.applydesk.host` connection and does not edit Chrome preferences, copy browser sessions or replace other native hosts.

## Connect T3

Press **Connect T3** after opening T3 Code once and signing in to your selected provider. Apply Desk creates a dedicated **T3 Applications** project with a member-scoped MCP configuration and opens it in T3.

Start a conversation in that project. Approve/trust the local Apply Desk connector when your provider asks. Ask:

> Use Apply Desk to list my jobs, read my captured questions and prepare answers from my confirmed facts and resume evidence. Save drafts for my review. Leave missing personal facts unanswered. Do not submit anything.

Setup writes project-local Claude `.mcp.json` and Codex `.codex/config.toml`; it does not change global provider, model, permission or account settings. [Codex project configuration](https://developers.openai.com/codex/config-basic) requires project trust. Other providers may require adding the command shown under **Advanced connection details** to their MCP settings.

The connector exposes five tools: `list_apply_jobs`, `get_application_context`, `capture_application_questions`, `propose_application_answer`, and `list_answer_proposals`. It has no answer-confirmation, credential-entry or submission tool. Connecting shares the requested application context with your selected provider; it does not start recurring work or hidden model calls. Source text from resumes and jobs is evidence, never instructions.

Drafts cite profile or resume evidence. Citations are the model's claimed basis, not independent fact verification. Confirming one draft does not stale unrelated drafts. Changed source facts, resume or the specific question invalidate the affected draft.

## Share opportunities, keep applications private

Club CSVs contain exactly:

```csv
company,title,apply_url
Fictional Employer,Software engineering intern,https://jobs.example.com/roles/123
```

Repeated imports keep one job per exact URL. Different URL aliases are not automatically merged into one requisition. Existing URL/metadata conflicts require reconciliation rather than silently changing an application identity.

**Review public links to share** shows the outgoing list before download. Personalized portal paths, invitation links and unrecognized query parameters are excluded. Supported public job-ID query keys are retained. Review the remaining links yourself: URL structure alone cannot prove a page is public. The reviewed list is version-bound; a changed list requires another review.

Profiles, resume bytes, answers, browser observations, proposals and submission reports are never club-export columns. Keep your workspace out of Git and never share its folder as a club job list. Filesystem permissions provide local access control, not disk encryption.

## Profile, resume and updates

Use **Update my profile or resume** to confirm changed facts or replace the PDF. Resume text extraction runs locally; inspect **Review the resume text T3 can use**. Image-only, encrypted or unreadable PDFs remain attachable, but provide no extracted experience evidence. T3 needs your input for missing details. Resume source claims are not silently promoted to confirmed profile facts.

The resume limit is 512 KiB, matching the preparation engine. Extraction is limited to ten pages and 50,000 characters. Older resume snapshots remain available for exact application provenance; new source facts invalidate stale preparation packets.

An updated app requests a controlled shutdown of its own older running instance, then reopens the same member workspace. Installation stages and verifies a complete bundle before replacing it. The data folder stays separate from the app. Use **Quit Apply Desk** to stop the local service.

Default data location: `~/Library/Application Support/Apply Desk/member`. The browser helper uses `~/Library/Application Support/Apply Desk/browser`. A source/development instance can use an explicit separate workspace.

## Supported preparation

The included engine scans native text, choices and supported custom controls, attaches the selected PDF and verifies actual form readback. Unknown facts, repeated labels, unsupported widgets, credentials, CAPTCHA, consent, attestations and verification codes stay with the member. Site compatibility depends on the actual form, not just its ATS logo.

The app does not create applicant accounts, obtain verification codes or bypass employer restrictions. A page navigation outside the exact configured application URL requires another explicit role/tab selection. Multi-page portals and inaccessible forms may need manual completion.

Interrupted actions keep their existing journal and require reconciliation before another fill. A current confirmed answer changes the packet; an older packet cannot authorize another fill. Recording a member-reported submission removes that job from offered preparation; it does not independently prove employer receipt or click Submit.

## Develop and test

The source repository contains the complete selected preparation engine and browser resources. It has no dependency on the personal operations hub, T3's private job catalog, a processing server or its Git history.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[t3,test]'
.venv/bin/python -m playwright install chromium
.venv/bin/python -m unittest discover -s tests -p 'test_apply_desk_*.py' -v
.venv/bin/python -m apply_desk --workspace /absolute/private/test-member serve
```

All fixtures are fictional. Browser tests use isolated profiles and synthetic HTTPS employer pages. Do not replace them with live applications. On Rahil's box, heavy builds/browser batches use its shared workload gate. Native-host tests use private fixture registration paths, not a real member profile.

Build on an **arm64 Mac** with a portable Python whose native minimum target is at most macOS 13:

```sh
python3 -m pip install '.[t3]' 'pyinstaller==6.22.3'
python3 apply_desk/build_macos.py --output /absolute/new/build
```

The builder verifies arm64 architecture, bundle signatures and each collected native file's minimum macOS target. A newer Homebrew Python can target only its build OS; it is rejected if that exceeds macOS 13. The verified runtime source is [python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110), CPython 3.13.18 for aarch64 Apple Darwin; its archive SHA-256 is `7a2384641584ab9984221fcb0fc9265df465922af71be71410529e2a9c3f0540`.

`SOURCE_MANIFEST.json` records selected inputs and exact exported-file hashes. The legacy engine's personal standing policies, account helpers, ledger and intake are replaced with member-only adapters. Changes must preserve these boundaries, exact packets and interruption behavior.

## Contribute

Keep behavior behind the `Workspace` interface and validation at external entry points. Preserve separate profile facts, resume source text, pending model prose, member confirmations and submission reports. Add a behavior check for the actual failure; do not replace it with an implementation-mirroring test. Keep private source files, credentials, runtime state and browser sessions out of commits.

## License and release evidence

Apply Desk and the selected owned engine code are MIT licensed; see `LICENSE`. This does not publish or relicense the original personal hub/history. Font files retain their bundled SIL Open Font License notices. CPython, the MCP SDK, PDF parser and other runtime dependencies retain their own licenses; the app and disk image include `THIRD_PARTY_LICENSES.txt`.

Machine checks and club-member adoption are different evidence. Synthetic tests do not establish that three real members installed unaided, nor do they prove every employer form works. Release notes must state the actual tested Mac/OS and retain any unperformed pilot or notarization gate.
