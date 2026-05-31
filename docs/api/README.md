# API Contract

`openapi.json` is the exported FastAPI contract for the frontend-facing API.

Update it after changing request or response schemas:

```bash
scripts/export-openapi.sh
```

Check that it matches the current backend code:

```bash
scripts/check-api-contract.sh
```

The full local verification path already runs this check:

```bash
scripts/check-fullstack.sh
```
