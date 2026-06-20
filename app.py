"""
Oratorij Print Uploader
-----------------------
Mobile-first Streamlit app, kjer ljudje naložijo fajle za printanje.
Fajli gredo na Google Drive, metadata na Google Sheet.

Public stran:  /
Admin stran:   /?page=admin   (zaščitena z geslom iz secrets)

Avtor: za Tobija — junij 2026
"""

from __future__ import annotations

import io
import html
import re
import time
import uuid
import zipfile
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Any

import pandas as pd
import streamlit as st

# Google API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import gspread


# ────────────────────────────────────────────────────────────────────────────
# Konfiguracija
# ────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Oratorij — Naloži za print",
    page_icon="🖨️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Mobile-first CSS — večji tap targets, manj robov, lepši kontejnerji
st.markdown(
    """
    <style>
      .block-container {
        padding-top: 1.2rem;
        padding-bottom: 4rem;
        max-width: 640px;
      }
      /* Veliki gumbi, prijazni do palca */
      .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        width: 100%;
        padding: 0.85rem 1rem;
        font-size: 1.05rem;
        border-radius: 12px;
      }
      .stTextInput input, .stTextArea textarea, .stNumberInput input {
        font-size: 1rem;
      }
      /* Radio horizontal okolj — naredi labelo bolj klikabilno */
      div[role="radiogroup"] > label {
        padding: 0.35rem 0.6rem;
        border-radius: 10px;
      }
      /* Kartica za vsak fajl */
      .file-card {
        background: rgba(120, 120, 120, 0.06);
        border: 1px solid rgba(120, 120, 120, 0.18);
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.6rem;
      }
      .file-card .name {
        font-weight: 600;
        word-break: break-all;
      }
      .file-card .size {
        opacity: 0.7;
        font-size: 0.85rem;
      }
      .pill {
        display: inline-block;
        background: rgba(0,120,255,0.12);
        color: inherit;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        margin-right: 4px;
      }
      @media (max-width: 640px) {
        .block-container {
          padding-left: 0.85rem;
          padding-right: 0.85rem;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

SHEET_HEADERS = [
    "timestamp",
    "submission_id",
    "ime",
    "namen",
    "namen_podrobno",
    "filename",
    "kopije",
    "strani",
    "opombe",
    "drive_file_id",
    "drive_link",
    "natisnjeno",
]

APP_TIMEZONE = ZoneInfo("Europe/Ljubljana")


# ────────────────────────────────────────────────────────────────────────────
# Google klienti (cache)
# ────────────────────────────────────────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def get_clients() -> tuple[Any, Any]:
    """Vrne (drive_service, gspread_worksheet). Cache-an za session."""
    sa_info = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=SCOPES
    )
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["sheet_id"])
    ws = sh.sheet1

    # Inicializiraj headerje če je sheet prazen
    try:
        first_row = ws.row_values(1)
    except Exception:
        first_row = []
    if first_row != SHEET_HEADERS:
        # Če je prvi row prazen ALI nima naših headerjev → zapiši
        if not first_row:
            ws.append_row(SHEET_HEADERS)
        else:
            # Headerji se razlikujejo — popravimo le če manjkajo (varno)
            if len(first_row) < len(SHEET_HEADERS):
                ws.update([SHEET_HEADERS], "A1")

    return drive, ws


def _sanitize_filename(name: str) -> str:
    name = name.strip().replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^\w\-. ()ČčŠšŽžĆćĐđ]+", "_", name, flags=re.UNICODE)
    return name[:180] or "fajl"


def upload_file_to_drive(
    drive,
    folder_id: str,
    raw_bytes: bytes,
    filename: str,
    mimetype: str | None,
) -> tuple[str, str]:
    """Naloži fajl v Drive folder. Vrne (file_id, webViewLink)."""
    safe_name = _sanitize_filename(filename)
    body = {"name": safe_name, "parents": [folder_id]}
    media = MediaIoBaseUpload(
        io.BytesIO(raw_bytes),
        mimetype=mimetype or "application/octet-stream",
        resumable=False,
    )
    f = (
        drive.files()
        .create(body=body, media_body=media, fields="id, webViewLink", supportsAllDrives=True)
        .execute()
    )
    return f["id"], f.get("webViewLink", "")


def download_file_from_drive(drive, file_id: str) -> bytes:
    """Prenese fajl iz Drive po ID-ju kot bytes."""
    request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    return buf.getvalue()


# ────────────────────────────────────────────────────────────────────────────
# UPLOAD stran
# ────────────────────────────────────────────────────────────────────────────


def render_upload_page() -> None:
    # Če smo pravkar uspešno oddali → pokaži potrditev, ne forme
    if "last_submission" in st.session_state:
        info = st.session_state["last_submission"]
        st.title("✅ Hvala!")
        st.success(
            f"**{info['ime'].split()[0]}**, naloženih je **{info['count']}** fajlov. "
            "Tobija jih dobi v pisarni."
        )
        st.caption(f"Oddano ob {info['ts']}")
        if st.button("➕ Naloži novo oddajo", type="primary", use_container_width=True):
            # Resetiraj session za nov upload
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        return

    st.title("🖨️ Naloži fajle za print")
    st.caption(
        "Naloži, kar bi rad imel sprintano. Vsak fajl posebej označi koliko kopij in enostransko/dvostransko."
    )

    # Fajli — izven forme, da takoj reagira
    uploaded = st.file_uploader(
        "Tvoji fajli (PDF, slike, Word…)",
        accept_multiple_files=True,
        type=None,  # sprejmi vse
        label_visibility="visible",
        key="uploader",
    )

    if uploaded:
        st.markdown("### 📄 Nastavitve za vsak fajl")
        for i, f in enumerate(uploaded):
            escaped_name = html.escape(f.name)
            size_kb = f.size / 1024 if hasattr(f, "size") and f.size else 0
            size_str = (
                f"{size_kb/1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
            )
            with st.container():
                st.markdown(
                    f"""
                    <div class="file-card">
                      <div class="name">{escaped_name}</div>
                      <div class="size">{size_str}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.number_input(
                        "Kopije",
                        min_value=1,
                        max_value=500,
                        value=1,
                        step=1,
                        key=f"copies_{i}",
                    )
                with c2:
                    st.radio(
                        "Strani",
                        ["Enostransko", "Dvostransko"],
                        index=0,
                        horizontal=True,
                        key=f"sides_{i}",
                    )

    st.markdown("---")
    st.markdown("### 👤 Tvoji podatki")

    ime = st.text_input("Tvoje ime in priimek *", key="ime")

    namen = st.radio(
        "Za kaj rabiš? *",
        ["Kateheza", "Velika igra", "Drugo"],
        horizontal=True,
        key="namen",
    )

    namen_detail = ""
    if namen == "Kateheza":
        namen_detail = st.text_input(
            "Katera kateheza? *",
            placeholder="npr. 1. razred, srednješolska, ipd.",
            key="namen_kateheza",
        )
    elif namen == "Velika igra":
        namen_detail = st.selectbox(
            "Kateri dan velike igre? *",
            ["Ponedeljek", "Torek", "Sreda", "Četrtek", "Petek"],
            key="namen_dan",
        )
    elif namen == "Drugo":
        namen_detail = st.text_input(
            "Opiši namen *",
            placeholder="npr. vabilo, plakat za delavnico…",
            key="namen_drugo",
        )

    opombe = st.text_area(
        "Opombe (neobvezno)",
        placeholder="kakršna koli dodatna navodila printarju ali Tobiju",
        key="opombe",
        height=80,
    )

    st.markdown("")
    submit = st.button("📤 Pošlji v pisarno", type="primary", use_container_width=True)

    if submit:
        # Validacija
        if not uploaded:
            st.error("Naloži vsaj en fajl.")
            return
        if not ime.strip():
            st.error("Vpiši svoje ime.")
            return
        if not namen_detail.strip():
            st.error("Izpolni polje za namen.")
            return

        # Pripravi metadata za vsak fajl
        files_payload = []
        for i, f in enumerate(uploaded):
            files_payload.append(
                {
                    "file": f,
                    "copies": st.session_state.get(f"copies_{i}", 1),
                    "sides": st.session_state.get(f"sides_{i}", "Enostransko"),
                }
            )

        # Pošlji
        with st.spinner("Pošiljam… (lahko traja par sekund)"):
            try:
                drive, ws = get_clients()
            except Exception as e:
                st.error(f"Napaka pri povezavi na Google: {e}")
                return

            submission_id = uuid.uuid4().hex[:8]
            ts = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
            folder_id = st.secrets["drive_folder_id"]

            rows_to_append = []
            errors = []

            for item in files_payload:
                f = item["file"]
                try:
                    raw = f.getvalue()
                    # Predponi filename z submission_id + ime → laže iskat v Drive folderju
                    safe_ime = _sanitize_filename(ime.strip()).replace(" ", "_")
                    drive_filename = f"{ts.replace(':','-')}__{safe_ime}__{f.name}"
                    file_id, link = upload_file_to_drive(
                        drive, folder_id, raw, drive_filename, f.type
                    )
                    rows_to_append.append(
                        [
                            ts,
                            submission_id,
                            ime.strip(),
                            namen,
                            namen_detail.strip(),
                            f.name,
                            int(item["copies"]),
                            item["sides"],
                            opombe.strip(),
                            file_id,
                            link,
                            "",  # natisnjeno checkbox — prazno na startu
                        ]
                    )
                except Exception as e:
                    errors.append(f"{f.name}: {e}")

            # Append vse vrstice naenkrat
            if rows_to_append:
                try:
                    ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
                except Exception as e:
                    errors.append(f"Sheet zapis: {e}")

        if errors:
            st.error("Nekaj fajlov ni šlo skozi:\n\n" + "\n".join(f"• {e}" for e in errors))
            if rows_to_append:
                st.info(
                    f"Vseeno se je shranilo {len(rows_to_append)} fajlov. "
                    "Lahko naložiš še manjkajoče."
                )
        else:
            st.session_state["last_submission"] = {
                "ime": ime.strip(),
                "count": len(rows_to_append),
                "ts": ts,
            }
            st.balloons()
            st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# ADMIN stran
# ────────────────────────────────────────────────────────────────────────────


def _check_admin_password() -> bool:
    if st.session_state.get("admin_ok"):
        return True
    st.title("🔒 Admin")
    pw = st.text_input("Geslo", type="password")
    if st.button("Prijava"):
        if pw == st.secrets.get("admin_password", ""):
            st.session_state["admin_ok"] = True
            st.rerun()
        else:
            st.error("Napačno geslo.")
    return False


def _fetch_dataframe(ws) -> pd.DataFrame:
    try:
        records = ws.get_all_records()
    except Exception:
        records = []
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=SHEET_HEADERS)
    # Zagotovi, da imamo vse pričakovane kolone
    for col in SHEET_HEADERS:
        if col not in df.columns:
            df[col] = ""
    # Pretvori timestamp v datetime za filtre
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if "kopije" in df.columns:
        df["kopije"] = pd.to_numeric(df["kopije"], errors="coerce").fillna(1).astype(int)
    return df


def render_admin_page() -> None:
    if not _check_admin_password():
        return

    st.title("📋 Admin — oddaje za print")

    try:
        drive, ws = get_clients()
    except Exception as e:
        st.error(f"Napaka pri povezavi: {e}")
        return

    if st.button("🔄 Osveži"):
        st.cache_resource.clear()
        st.rerun()

    df = _fetch_dataframe(ws)

    if df.empty:
        st.info("Še ni nobene oddaje.")
        return

    # ── Filtri
    st.markdown("### Filtri")
    c1, c2, c3 = st.columns(3)
    with c1:
        all_dates = sorted({d.date() for d in df["timestamp"] if pd.notna(d)})
        default_date = [max(all_dates)] if all_dates else []
        date_filter = st.multiselect(
            "Datum", options=all_dates, default=default_date, format_func=lambda d: d.strftime("%d.%m.%Y")
        )
    with c2:
        namen_filter = st.multiselect(
            "Namen", options=sorted(df["namen"].dropna().unique().tolist())
        )
    with c3:
        ime_search = st.text_input("Iskanje (ime / podrobno)")

    filt = df.copy()
    if date_filter:
        filt = filt[filt["timestamp"].dt.date.isin(date_filter)]
    if namen_filter:
        filt = filt[filt["namen"].isin(namen_filter)]
    if ime_search.strip():
        q = ime_search.strip().lower()
        filt = filt[
            filt["ime"].str.lower().str.contains(q, na=False)
            | filt["namen_podrobno"].str.lower().str.contains(q, na=False)
            | filt["filename"].str.lower().str.contains(q, na=False)
        ]

    st.markdown(f"### {len(filt)} vrstic")

    # Glavna tabela
    display_cols = [
        "timestamp",
        "ime",
        "namen",
        "namen_podrobno",
        "filename",
        "kopije",
        "strani",
        "opombe",
        "drive_link",
    ]
    st.dataframe(
        filt[display_cols].sort_values("timestamp", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Čas", format="DD.MM HH:mm"),
            "drive_link": st.column_config.LinkColumn("Drive", display_text="odpri"),
            "kopije": st.column_config.NumberColumn("Kopij", width="small"),
        },
    )

    # Skupna statistika za printerja
    st.markdown("### 🖨️ Povzetek za printerja")
    if len(filt):
        total_files = len(filt)
        total_pages = filt["kopije"].sum()
        c1, c2 = st.columns(2)
        c1.metric("Različnih fajlov", total_files)
        c2.metric("Skupaj kopij", int(total_pages))

    # ── Export
    st.markdown("### ⬇️ Export")
    e1, e2 = st.columns(2)

    with e1:
        # CSV samo z metadata (za printerja)
        printer_csv = (
            filt[["filename", "ime", "namen", "namen_podrobno", "kopije", "strani", "opombe"]]
            .rename(
                columns={
                    "filename": "Fajl",
                    "ime": "Oddal",
                    "namen": "Namen",
                    "namen_podrobno": "Podrobno",
                    "kopije": "Kopij",
                    "strani": "Strani",
                    "opombe": "Opombe",
                }
            )
            .to_csv(index=False)
            .encode("utf-8-sig")
        )
        st.download_button(
            "📄 Prenesi CSV za printerja",
            printer_csv,
            file_name=f"print-list-{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with e2:
        if st.button("📦 Pripravi ZIP fajlov + CSV", use_container_width=True):
            with st.spinner(f"Prenašam {len(filt)} fajlov iz Drive…"):
                zip_buf = io.BytesIO()
                problems = []
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    # CSV vključen v ZIP
                    zf.writestr(
                        "00_print-list.csv",
                        printer_csv.decode("utf-8-sig"),
                    )
                    for _, row in filt.iterrows():
                        fid = row.get("drive_file_id")
                        if not fid:
                            continue
                        try:
                            data = download_file_from_drive(drive, fid)
                            # filename v ZIP-u: kopije__ime__originalfilename
                            zname = (
                                f"{int(row['kopije'])}x__"
                                f"{_sanitize_filename(str(row['namen']))}__"
                                f"{_sanitize_filename(str(row['ime']))}__"
                                f"{_sanitize_filename(str(row['filename']))}"
                            )
                            zf.writestr(zname, data)
                        except Exception as e:
                            problems.append(f"{row.get('filename')}: {e}")
                zip_buf.seek(0)
                st.session_state["zip_data"] = zip_buf.getvalue()
                st.session_state["zip_problems"] = problems

        if "zip_data" in st.session_state:
            st.download_button(
                "⬇️ Prenesi ZIP",
                st.session_state["zip_data"],
                file_name=f"print-{date.today().isoformat()}.zip",
                mime="application/zip",
                use_container_width=True,
            )
            if st.session_state.get("zip_problems"):
                st.warning("Pri nekaterih fajlih je bilo problema:")
                for p in st.session_state["zip_problems"]:
                    st.text(f"• {p}")


# ────────────────────────────────────────────────────────────────────────────
# Router
# ────────────────────────────────────────────────────────────────────────────


def main() -> None:
    page = st.query_params.get("page", "upload")
    if isinstance(page, list):
        page = page[0] if page else "upload"

    if page == "admin":
        render_admin_page()
    else:
        render_upload_page()


if __name__ == "__main__":
    main()
