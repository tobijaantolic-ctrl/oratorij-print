# Oratorij Print Uploader

Mobile-first Streamlit app, kjer ljudje naložijo fajle za printanje. Fajli gredo na Google Drive, metadata pa v Google Sheet. Brezplačen stack: GitHub + Streamlit Community Cloud + Google Drive/Sheets.

## Kaj počne

**Public (`/`)** — naloži fajle (PDF, slike, Word, karkoli), za vsak fajl vpiše št. kopij in enostransko/dvostransko, izpolni ime + namen (Kateheza/Velika igra/Drugo) + opcijske opombe, klikne **Pošlji**.

**Admin (`/?page=admin`, geslo iz secrets)** — vidiš tabelo vseh oddaj, filtri (datum, namen, iskanje), povzetek koliko fajlov × kopij. Dva exporta:
- CSV za printerja (tabela: fajl, oddal, namen, kopij, strani, opombe)
- ZIP, ki vsebuje vse fajle + CSV (filename v ZIP-u je `Nx__namen__ime__originalfilename`)

## Kaj je treba nastaviti

Koda je pripravljena za GitHub in Streamlit. Edini del, ki mora biti izven GitHuba, so Google credentials in ID-ji Drive/Sheet, ker so to secret-i.

### 1. Google Cloud — service account
1. https://console.cloud.google.com → nov projekt (npr. `oratorij-print`)
2. **APIs & Services → Enable APIs** → omogoči **Google Drive API** in **Google Sheets API**
3. **IAM & Admin → Service Accounts** → Create. Ko nastane, klik nanj → **Keys → Add Key → JSON**. Prenese se `service-account.json`.

### 2. Google Drive folder
1. V svojem Drive naredi mapo (npr. `Oratorij — Print 2026`)
2. **Share** to mapo na email service accounta (`...@...iam.gserviceaccount.com`) kot **Editor**
3. Iz URL-ja kopiraj **folder ID** (`https://drive.google.com/drive/folders/<TO>`)

### 3. Google Sheet
1. V Drive naredi nov Sheet (npr. `Oratorij — Print Log`)
2. **Share** na isti service-account email kot **Editor**
3. Iz URL-ja kopiraj **sheet ID** (`https://docs.google.com/spreadsheets/d/<TO>/edit`)

### 4. Secrets

Najlažje:

```bash
python scripts/make_streamlit_secrets.py ~/Downloads/service-account.json \
  --drive-folder-id "PASTE_DRIVE_FOLDER_ID_HERE" \
  --sheet-id "PASTE_SHEET_ID_HERE" \
  --admin-password "izberi-dobro-admin-geslo"
```

To ustvari lokalni `.streamlit/secrets.toml`, ki ga **ne commitaj**. Isti content potem prilepiš v Streamlit Cloud pod **App settings → Secrets**.

Ročno:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# odpri secrets.toml in zamenjaj:
#   admin_password   — geslo za /admin
#   drive_folder_id  — iz koraka 2
#   sheet_id         — iz koraka 3
#   [gcp_service_account] — vsebina service-account.json
```

### 5. Lokalni run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### 6. Deploy na Streamlit Community Cloud
1. Pushni repo na GitHub (`.streamlit/secrets.toml` in `service-account.json` sta v `.gitignore`, NE pushaj ju)
2. https://share.streamlit.io → **Create app** → izberi repo → entrypoint `app.py`
3. V **Advanced settings** izberi Python `3.12`, če je izbira na voljo
4. **Secrets** → prilepi vsebino lokalnega `.streamlit/secrets.toml`
5. Deploy. Navaden URL deli z ljudmi za upload, sebi shrani isti URL z `?page=admin`.

## Polja v Sheet-u

Headerji se ustvarijo avtomatsko ob prvi oddaji:

`timestamp | submission_id | ime | namen | namen_podrobno | filename | kopije | strani | opombe | drive_file_id | drive_link | natisnjeno`

`natisnjeno` lahko ročno popolniš v Sheet-u (npr. `x` ko sprintaš) — koda jo bo ohranila.

## Tips

- Vsak fajl je shranjen z imenom `YYYY-MM-DD_HH-MM-SS__Ime_Priimek__originalfilename` v Drive folderju → lahko ga najdeš tudi brez admin strani.
- 200 MB max per fajl (default). Če rabiš več, spremeni v `.streamlit/config.toml`.
- HEIC iz iPhone-a se naloži kot-je. Če printer ne pozna HEIC, ga v admin ZIP-u shrani in pretvori s katerim koli orodjem (Preview na Macu zna).
- Če rabiš urgent stop sprejemanja oddaj, daj app na "pause" na Streamlit Cloud, ali zamenjaj `admin_password` in dodaj banner.

## Testiranje

```bash
python -m unittest discover -s tests
python -m py_compile app.py scripts/make_streamlit_secrets.py
streamlit run app.py
```
