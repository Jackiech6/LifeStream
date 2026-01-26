# Fix "Internal Server Error" at localhost:3000

## 1. Use production only (most common fix)

The error often happens when the **dev server** (`npm run dev`) is running or was running with a bad cache.

- **Stop any running app**: In every terminal where you ran `npm run dev` or `npm run start`, press **Ctrl+C**.
- **Free port 3000** (in a terminal):
  ```bash
  lsof -ti :3000 | xargs kill -9
  ```
- **Start with the script** (from project root):
  ```bash
  cd /Users/chenjackie/Desktop/LifeStream && ./scripts/start-frontend.sh
  ```
- When you see **`✓ Ready in ...`**, open **http://localhost:3000** in a **new tab** (or use a private/incognito window to avoid cache).

Use **only** this script for testing. Do **not** run `npm run dev`.

---

## 2. If you still see Internal Server Error

The server prints the real error in the **same terminal** where you ran `./scripts/start-frontend.sh`.

1. Look at that terminal for a stack trace or message (e.g. `Error: Cannot find module ...`, `TypeError: ...`).
2. Copy the full error (or a screenshot) and share it so we can fix the code.
3. Try opening **http://localhost:3000/upload** or **http://localhost:3000** and see if one of them works (narrows down the failing route).

---

## 3. "Cannot find module .next/server/app/.../page.js"

The build completed but server route files are missing. Try a **clean reinstall** (section 4). If the script then says "Build did not produce .next/server/app/upload/page.js", run the build manually from the **frontend** folder and watch for errors:

```bash
cd /Users/chenjackie/Desktop/LifeStream/frontend
rm -rf .next
npm run build
ls -la .next/server/app/upload/
```

If `page.js` is missing, report your Node version (`node -v`) and OS; it may be a Next.js build quirk on your environment.

---

## 4. Nuclear option: clean reinstall

From the **project root**:

```bash
cd /Users/chenjackie/Desktop/LifeStream/frontend
rm -rf .next node_modules
npm install
cd ..
./scripts/start-frontend.sh
```

Then open http://localhost:3000 again.
