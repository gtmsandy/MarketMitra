# MarketMitra local demo

This project uses separate local PostgreSQL targets for different purposes. The
existing `backend/.env` continues to point at the original `marketmitra`
database. Authentication testing uses the ignored `backend/.env.auth-ci.local`
file and the disposable `marketmitra_auth_ci` database. Do not use the CI
database as a permanent interview-demo database.

## Start the authentication test environment

Run these commands from the repository root in separate PowerShell windows.

Backend:

```powershell
Get-Content .\backend\.env.auth-ci.local | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') {
    [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
  }
}
Push-Location .\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
Push-Location .\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Open <http://127.0.0.1:5173>. The matching `127.0.0.1` origin is recommended
for authenticated flows. `localhost` remains available for public pages, but
mixing `localhost` frontend requests with a `127.0.0.1` API intentionally does
not share the `SameSite=Lax` session cookie.

## Planned interview-demo accounts

These addresses are reserved for a future, separately approved
`marketmitra_demo` database. They have not been provisioned in the disposable
CI database.

- Investor: `investor@marketmitra.test`
- Admin: `admin@marketmitra.test`
- Password-manager entries: `MarketMitra / Demo / Investor` and
  `MarketMitra / Demo / Admin`

Never put either password in this repository, an `.env` committed to Git, a
fixture, or documentation. Provision the admin only through the controlled
offline provisioning command after the separate demo database is approved.

## Interview walkthrough

1. Open the dashboard and show anonymous market overview, movers, sectors and
   heatmap pages.
2. Sign in with the future demo investor account and open the profile page.
3. Update the display name, refresh, and show that the session persists.
4. Visit `/admin` as the investor to demonstrate server-side denial.
5. Sign out and confirm protected pages require authentication.
6. Sign in with the future demo admin account and show the server-verified admin
   page.
7. Sign out before closing the demo.

## Troubleshooting

- If the backend reports a database authentication error, verify that
  `backend/.env.auth-ci.local` exists, is ignored by Git, and targets
  `marketmitra_auth_ci` with user `marketmitra_ci_user`.
- If port 8000 is occupied, choose another local port and set the same port in
  `VITE_API_BASE_URL` before starting the frontend.
- If authentication appears to fail only on `localhost`, use matching
  `127.0.0.1` URLs for both frontend and API.
- Check PostgreSQL with `pg_isready -h localhost -p 5432`; do not run migrations
  against the existing `marketmitra` database.
- The CI database is disposable. Do not reset or recreate it automatically at
  application startup.
