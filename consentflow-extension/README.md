# ConsentFlow Privacy Shield

ConsentFlow Privacy Shield is a Chrome extension that automatically detects and masks Personally Identifiable Information (PII) before you send it to AI chatbots like ChatGPT and Claude. It replaces sensitive data with temporary placeholder tokens, ensuring your private information never leaves your browser unless explicitly permitted.

## Privacy Guarantees

* **Zero PII Logging:** Real PII is never sent to the backend server; only placeholder tokens (like `[PERSON_1]`) are transmitted.
* **In-Memory Vault:** The mapping between real PII and generated dummy values lives entirely in your browser's RAM and is wiped automatically when you close the tab.
* **No Disk Storage for Sensitive Data:** IndexedDB is used exclusively for non-sensitive metadata (e.g., counters for how many items were masked).
* **Local Processing:** PII detection happens entirely locally using regular expressions within the browser extension.

## Development Setup

1. Install dependencies:
   ```bash
   npm install
   ```
2. Build the extension:
   ```bash
   npm run build
   ```
3. Open Chrome and navigate to `chrome://extensions`.
4. Enable "Developer mode" in the top right.
5. Click "Load unpacked" and select the `dist/` directory inside this project.

## Configuration

To configure the backend URL for the extension:
1. Click the ConsentFlow Shield icon in your browser toolbar to open the popup.
2. At the bottom of the popup, under the "Backend URL" section, click **Edit**.
3. Enter your local or remote backend URL (e.g., `http://localhost:8000`) and click **Save**.

## Running Tests

Run the unit tests (which cover the dummy generator, vault, and reverse mapper) using:
```bash
npm test
```

## Backend Integration

This extension communicates with the FastAPI backend. The relevant backend files are:
* **`consentflow/app/routers/extension.py`**: A dedicated router providing the `/anonymize` and `/consent-profile` endpoints.
* **`consentflow/app/models.py`**: Added the `ExtensionAnonymizePlaceholderRequest` schema for validating incoming requests.
* **`consentflow/app/main.py`**: The extension router is included here via `app.include_router(extension.router)`.

## Offline Mode

If the backend server is unreachable or offline, the extension automatically falls back to **Offline Mode**. In this mode:
* The network request times out (after 3 seconds) and fails gracefully.
* The extension instantly generates realistic dummy values locally.
* Real PII is swapped for the locally generated dummy values and stored in the in-memory vault.
* Chatbots still receive masked data, maintaining your privacy without interruption.
