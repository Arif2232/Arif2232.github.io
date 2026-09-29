# Arif Khan — portfolio

Static, dependency-free portfolio for Arif Khan. Professional descriptions are grounded in the supplied resume and verified fact bank. The workflow exercise is a separate demonstration, not a claim about a deployed client system.

## Preview

```sh
python3 -m http.server 8765 --directory .
```

Open `http://127.0.0.1:8765/`.

## Run the work sample

```sh
cd samples
python3 -m unittest -v test_workflow_store.py
python3 workflow_store.py
```

## Publishing

Publish only the files in this portfolio directory. Do not include the job-agent configuration, application ledger, browser profile, private receipts, environment files or credentials. GitHub Pages can serve the static site from the repository's main branch root. No build step or third-party tracking is used.

Professional metrics (40% database latency reduction and 30% fewer manual QA cycles) come from Arif's resume. The HyperProbe YC reference describes the product/company, not an individual founder credential. Product reference: https://www.hyperprobe.co/.
