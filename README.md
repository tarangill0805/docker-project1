# New Address — HTML, CSS, JavaScript and Python / Flask

The New Address design converted to Flask, Jinja templates, plain CSS and JavaScript. Includes the original hero asset, splash animation, scroll gallery, day/evening lighting effect, responsive navigation, city/type/buy/rent search, property details and photo slides. Python manages SQLite storage, enquiries and the admin dashboard.

## Quick Windows setup

Extract the whole ZIP, then run `SETUP_WINDOWS.bat` once to install dependencies and create your private admin account. Run `RUN_WINDOWS.bat` to start the site. Open http://127.0.0.1:5000 in your browser. See `START_HERE.txt` for exact steps. The Windows batch launchers were not tested on Windows.

## Run in VS Code (Windows Git Bash)

Install Python 3.11 or newer. Extract this ZIP. Open **New-Address-FullStack** in VS Code, then open Terminal → New Terminal. Confirm `app.py` is in your current folder.

```bash
py -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m flask --app app:create_app set-admin
```

Enter your email and choose a password with at least 12 characters. Password typing is hidden. There is no default password. Then start:

```bash
python -m flask --app app:create_app run
```

Website: http://127.0.0.1:5000
Admin: http://127.0.0.1:5000/admin

Keep the terminal running. Stop with Ctrl+C. To start another day:

```bash
source .venv/Scripts/activate
python -m flask --app app:create_app run
```

If `py` is unavailable, use `python` to create the virtual environment. In PowerShell use `.venv\Scripts\Activate.ps1` instead of the `source` command. On macOS/Linux use `python3 -m venv .venv` and `source .venv/bin/activate`.

## Manage properties and enquiries

Sign in at `/admin`. Add, edit or delete properties. Upload JPG, PNG or WebP photos from your computer, or paste HTTPS image URLs, one per line. Maximum 20 images per property; total upload request up to 20 MB. Uploaded images are converted to JPEG. Untick “Sample listing” after replacing all illustrative details with a real listing.

Enquiries appear only in the protected admin dashboard. They are saved in SQLite; automatic email/SMS delivery is not configured. Public contact links use newaddressofficial@gmail.com. Edit contact details in BUSINESS near the top of `app.py`.

## Reset admin password

Stop the server, then run the same `set-admin` command and choose a new password. Existing admin sessions are invalidated. No password is stored in source code.

## Check on your phone

Connect phone and computer to the same trusted Wi-Fi, then:

```bash
python -m flask --app app:create_app run --host=0.0.0.0
```

Run `ipconfig` in Windows to find your Wi-Fi IPv4 address. Open `http://YOUR-IP:5000` on your phone. If Windows asks, allow Python on private networks. This is a local preview, not public hosting.

## Data, backups and migration

The `instance/` directory is created on first run. It contains your SQLite database, uploaded photos and secret session key. Back up this entire directory while the server is stopped. Keep it private; do not upload it to GitHub. The ZIP includes source and five clearly marked sample listings. Live hosted properties, enquiries, uploaded images and hosted passwords have not been migrated. External Unsplash sample photos and Google Fonts need internet access; the main hero image is included locally.

## Hosting

This package is for a Python host with a persistent writable disk. Its database is SQLite, not the previous Cloudflare D1 database. For production, configure HTTPS, set `HTTPS_ONLY=1`, and use a WSGI server instead of the Flask development server, for example:

```bash
waitress-serve --listen=127.0.0.1:8000 --call app:create_app
```

Place it behind your host's HTTPS reverse proxy. A domain can be connected after hosting is configured. The current online website is unchanged.

## Verification

```bash
python -m unittest discover -s tests -v
```

Checks cover public search, property details, admin access control, password reset invalidation, CSRF, enquiry validation/storage, property create/edit/delete and image uploads.

All five integration tests passed during packaging, and JavaScript syntax checking passed. Browser visual verification was not performed.
