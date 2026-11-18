# RuangUang – Multi-user Personal & Family Finance

RuangUang is a public-facing finance tracker built with Streamlit and Supabase. Each registered user has isolated personal workspaces and can create family workspaces to share selected finance records with invited members.

## Features in this starter
- Public email/password registration and login through Supabase Auth.
- Multiple isolated workspaces: personal and family.
- Family invitations by email for registered RuangUang users.
- Workspace-scoped accounts, transactions, bills, and atomic paired internal transfers.
- Receipt OCR with manual confirmation.
- Charts, transaction history, and CSV export.
- PostgreSQL Row Level Security (RLS).

## 1. Create Supabase project
1. Create a project at https://supabase.com/.
2. Open **SQL Editor**.
3. Run the complete `supabase/schema.sql` script.
4. In **Project Settings → API**, copy the Project URL and the publishable/anon key.
5. In **Authentication → Providers → Email**, enable email/password sign-in. For a first test, email confirmation may be disabled; before public launch, configure email confirmation and SMTP.

## 2. Upload to GitHub
Upload the CONTENTS of this folder to the ROOT of your GitHub repository. The repository root must contain `app.py`, `requirements.txt`, `packages.txt`, and `supabase/schema.sql`.

## 3. Deploy on Streamlit Community Cloud
1. Connect the GitHub repository at https://share.streamlit.io/.
2. Main file path: `app.py`.
3. In Streamlit app **Settings → Secrets**, add:
   ```toml
   SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
   SUPABASE_ANON_KEY = "YOUR_SUPABASE_PUBLISHABLE_OR_ANON_KEY"
   ```
4. Deploy / reboot the app.

Do not put the Supabase service-role key in Streamlit secrets. The app uses the publishable/anon key plus each user's authenticated session; RLS enforces workspace access.

## 4. Family workspaces
A user creates a family workspace, then invites another registered user by email from the **Anggota** page. The invited person logs in and accepts the invitation. Family members can read and manage records in that family workspace. The workspace owner/admin controls invitations.

## Important limitations before public launch
- This is a starter implementation, not a security audit or production-certified financial service.
- Family members currently share full read/write access to records in their family workspace; granular permissions and audit logs are future improvements.
- Invitation flow is in-app and requires the invitee to already have a RuangUang account. Email delivery is not configured here.
- OCR can misread receipts; user confirmation is required.
- No direct bank/e-wallet API integration. Use manual entry and compatible CSV import as later enhancements.
- Streamlit Community Cloud is suitable for a prototype; review deployment, privacy, backups, rate limits, and operational needs before broad public launch.
- Do not collect mobile banking passwords, PINs, or OTPs.
