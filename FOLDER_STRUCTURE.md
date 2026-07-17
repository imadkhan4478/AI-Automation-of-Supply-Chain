# FOLDER STRUCTURE — where every file goes

This is the ONE correct layout. If a file is loose in the project root when it
should be in a subfolder (or duplicated in both places), Python loads the wrong
copy and you get errors like "module has no attribute X". Keep exactly this.

```
Qadri_Group/                    <-- project root (where you run streamlit)
│
├── app.py                      <-- ROOT (entry point)
├── requirements.txt            <-- ROOT
├── .env                        <-- ROOT (DB credentials; NOT committed)
├── .gitignore                  <-- ROOT
├── README.md                   <-- ROOT
├── PROJECT_HANDOFF.md          <-- ROOT
├── FOLDER_STRUCTURE.md         <-- ROOT (this file)
│
├── .streamlit/
│   └── config.toml
│
├── assets/
│   ├── qadri_logo.png
│   └── qadri_logo_transparent.png
│
├── components/                 <-- UI building blocks
│   ├── __init__.py
│   ├── theme.py                <-- (NOT in root)
│   ├── ui.py
│   └── charts.py               <-- (NOT in root)
│
├── pages_logic/                <-- one file per page
│   ├── __init__.py
│   ├── dashboard.py            <-- (NOT in root)
│   ├── purchases.py
│   ├── inventory.py
│   ├── imports.py
│   ├── logistics.py
│   ├── reports.py
│   └── assistant.py
│
├── backend/                    <-- data layer (the ONLY place touching the DB)
│   ├── __init__.py
│   ├── data_access.py          <-- (NOT in root) the ONE the pages call
│   └── db_connection.py        <-- SQLAlchemy engine, reads .env
│
└── stubs/
    ├── __init__.py
    └── fake_data.py            <-- (NOT in root)
```

## Files that must NOT sit loose in the project root

These belong ONLY inside their subfolders. If you see a copy in the root, delete
the root copy (the correct one is inside the folder):

- data_access.py   -> backend/
- db_connection.py -> backend/
- theme.py         -> components/
- ui.py            -> components/
- charts.py        -> components/
- dashboard.py     -> pages_logic/
- fake_data.py     -> stubs/

## Throwaway test scripts (fine to keep or delete)

- check.py, test_stock.py  -> these are your own temporary test scripts.
  They can live in the root; they are not part of the app. Delete when done.

## How to run

From the project root (the folder containing app.py):

```
streamlit run app.py
```
