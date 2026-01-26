# Deploy Frontend for Testing

Run the frontend locally so you can test the upload → status → summary flow immediately.

---

## One-time setup

1. **Node.js 18+** installed.
2. **Terminal** at the project root: `/Users/chenjackie/Desktop/LifeStream`.

---

## Deploy and run (paste in your terminal)

```bash
cd /Users/chenjackie/Desktop/LifeStream && ./scripts/start-frontend.sh
```

This script will:

- Create `frontend/.env.local` with the staging API URL (if missing).
- Clear `.next`, run `npm run build`, then `npm run start`.
- Serve the app at **http://localhost:3000**.

When you see `✓ Ready in ...`, open **http://localhost:3000** in your browser and start testing (Upload → job status → View summary).

---

## Optional: dev server (hot reload)

Not recommended for testing—dev can show a **blank page** due to chunk errors. Prefer `./scripts/start-frontend.sh`.

If you use dev anyway:

```bash
cd /Users/chenjackie/Desktop/LifeStream/frontend
rm -rf .next && npm run build && npm run dev
```

Then open **http://localhost:3000** (or the port Next.js prints).

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| **Internal Server Error at localhost:3000** | Usually caused by the **dev** server (e.g. `npm run dev`) with a bad cache. Stop the server, then run `./scripts/start-frontend.sh` and open http://localhost:3000 again. Use **production** only for testing. |
| **Blank page / nothing shows** | You may be running `npm run dev`. Stop it, then run `./scripts/start-frontend.sh` only. Use **production** (this script), not dev, for testing. |
| **Port 3000 in use** | Stop other Next.js/Node processes (e.g. `npm run dev`), then re-run the script. Or run `next start -p 3001` and use `http://localhost:3001`. |
| **"Cannot find module './xx.js'"** | Caused by stale dev build. Run `./scripts/start-frontend.sh` (it clears `.next` and does a fresh production build). |
| **API errors in UI** | Confirm `frontend/.env.local` has `NEXT_PUBLIC_API_URL=https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging`. |
