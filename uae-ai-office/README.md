# UAE AI Office

## Starting UAE AI Office

From this directory, run:

```bash
./start.sh
```

The script starts the backend on port 8000 and the frontend on port 3000,
checks their HTTP readiness, and reuses already-running project processes.
Use `./status.sh` to inspect service state and `./stop.sh` to stop only the
processes started by this project.

The backend reads `backend/.env` directly through its settings configuration;
starting the application does not require `source .env`. In Codespaces, ports
3000 and 8000 are forwarded automatically by `.devcontainer/devcontainer.json`.