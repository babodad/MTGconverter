# Web app for converting TopDecked or TCG ImportErrors CSV to TCG PowerTools format

import pandas as pd
import streamlit as st
import io
import json
import requests
from functools import lru_cache

def remove_basic_lands(df):
    basic_land_names = ["Plains", "Island", "Swamp", "Mountain", "Forest"]
    return df[~df["NAME"].isin(basic_land_names)].copy()

def consolidate_duplicates(df):
    group_cols = ["NAME", "SETNAME", "SETCODE", "FINISH", "CONDITION", "LANG", "NOTES"]
    df["QUANTITY"] = pd.to_numeric(df["QUANTITY"], errors="coerce").fillna(0).astype(int)
    return df.groupby(group_cols, dropna=False, as_index=False).agg({"QUANTITY": "sum"})

def consolidate_sets(df):
    df["GROUP_KEY"] = df["NAME"].str.lower().str.strip()
    group = df.groupby("GROUP_KEY")
    result_rows = []

    for key, group_df in group:
        if group_df["SETNAME"].nunique() > 1:
            max_setname = group_df.groupby("SETNAME")["QUANTITY"].sum().idxmax()
            total_quantity = group_df["QUANTITY"].sum()
            consolidated_row = group_df.iloc[0].copy()
            consolidated_row["QUANTITY"] = total_quantity
            consolidated_row["SETNAME"] = max_setname
            consolidated_row["NOTES"] = (consolidated_row["NOTES"] + " | Sets consolidated").strip(" | ")
            result_rows.append(consolidated_row)
        else:
            result_rows.extend(group_df.to_dict("records"))

    return pd.DataFrame(result_rows).drop(columns=["GROUP_KEY"], errors="ignore")

@lru_cache(maxsize=1)
def load_cardmarket_mapping():
    path = "products_singles_1.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("products", [])
    except Exception:
        return []

def build_id_lookup_table():
    raw_data = load_cardmarket_mapping()
    lookup = {}
    for entry in raw_data:
        if isinstance(entry, dict):
            name = entry.get("name", "").strip().lower()
            set_id = entry.get("idExpansion", "")
            if name:
                if name not in lookup:
                    lookup[name] = []
                lookup[name].append({"idProduct": entry.get("idProduct", ""), "idExpansion": set_id})
    return lookup

def get_cardmarket_id(name, setname, lookup):
    name_key = name.strip().lower()
    matches = lookup.get(name_key, [])
    if not matches:
        return ""
    if setname:
        setname = setname.strip().lower()
        for match in matches:
            if setname in str(match.get("idExpansion", "")).lower():
                return match.get("idProduct", "")
    return matches[0].get("idProduct", "")

@lru_cache(maxsize=1)
def fetch_scryfall_sets():
    url = "https://api.scryfall.com/sets"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return {s['name'].lower(): s['code'] for s in data['data']}
    return {}

def get_scryfall_id(name, setname):
    sets = fetch_scryfall_sets()
    setcode = sets.get(setname.strip().lower())
    if not setcode:
        return ""
    url = f"https://api.scryfall.com/cards/named?exact={name.strip()}&set={setcode}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("id", "")
    return ""

def convert_error_format(df):
    df.columns = df.columns.str.strip().str.lower()
    required = ["quantity", "name"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in TCG ImportErrors format.")

    def get_column(col):
        return df[col] if col in df.columns else ""

    df_out = pd.DataFrame()
    df_out["QUANTITY"] = df["quantity"]
    df_out["NAME"] = df["name"]
    df_out["SETNAME"] = get_column("expansion")
    df_out["SETCODE"] = ""
    df_out["FINISH"] = get_column("foil").apply(lambda x: "Foil" if str(x).strip().lower() in ["true", "yes", "foil"] else "")
    df_out["CONDITION"] = get_column("condition")
    df_out["LANG"] = get_column("language")
    df_out["NOTES"] = get_column("comment")

    return df_out[["QUANTITY", "NAME", "SETNAME", "SETCODE", "FINISH", "CONDITION", "LANG", "NOTES"]]

def convert_topdecked_format(df):
    df.columns = df.columns.str.strip().str.upper()
    required = ["QUANTITY", "NAME"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in TopDecked format.")
    for col in ["SETNAME", "SETCODE", "FINISH", "CONDITION", "LANG", "NOTES"]:
        if col not in df.columns:
            df[col] = ""
    return df

def convert_to_tcgpowertools_format(df, default_condition, default_language, fetch_ids=False, use_scryfall=False):
    output = pd.DataFrame()
    if fetch_ids:
        if use_scryfall:
            output["idProduct"] = df.apply(lambda row: get_scryfall_id(row["NAME"], row["SETNAME"]), axis=1)
        else:
            lookup = build_id_lookup_table()
            output["idProduct"] = df.apply(lambda row: get_cardmarket_id(row["NAME"], row["SETNAME"], lookup), axis=1)
    else:
        output["idProduct"] = ""
    output["quantity"] = df["QUANTITY"]
    output["name"] = df["NAME"]
    output["set"] = df["SETNAME"]
    output["condition"] = df["CONDITION"].fillna(default_condition)
    output["language"] = df["LANG"].fillna(default_language)
    output["isFoil"] = df["FINISH"].str.lower().eq("foil")
    output["isPlayset"] = ""
    output["isSigned"] = ""
    output["isFirstEd"] = ""
    output["price"] = ""
    output["comment"] = df["NOTES"].fillna("")
    return output

st.title("TopDecked → TCG PowerTools Converter")

uploaded_file = st.file_uploader("Upload a CSV file", type="csv")

input_format = st.selectbox("Input format", ["TopDecked", "TCG ImportErrors"])

remove_basics = st.checkbox("Remove basic lands", value=True)
default_condition = st.selectbox("Default condition", ["NM", "EX", "GD", "LP", "PL", "PO"], index=0)
default_language = st.selectbox("Default language", ["English", "German", "French", "Spanish", "Italian", "Simplified Chinese", "Japanese", "Portuguese", "Russian", "Korean"], index=0)

fetch_ids = (input_format == "TCG ImportErrors")
if fetch_ids:
    use_scryfall = st.checkbox("Use Scryfall API (slower, but more accurate)", value=False)
else:
    use_scryfall = False

set_consolidation = st.checkbox("Consolidate sets after grouping (assign all to most common set per name)", value=False)

if uploaded_file is not None:
    if st.button("Convert"):
        try:
            df = pd.read_csv(uploaded_file)
            if input_format == "TCG ImportErrors":
                df = df.drop(columns=["error"], errors="ignore")
                df = df.rename(columns={df.columns[0]: "idProduct"})
                df = convert_error_format(df)
            else:
                df = convert_topdecked_format(df)

            if remove_basics:
                df = remove_basic_lands(df)

            df_grouped = consolidate_duplicates(df)

            if set_consolidation:
                df_grouped = consolidate_sets(df_grouped)

            df_converted = convert_to_tcgpowertools_format(df_grouped, default_condition, default_language, fetch_ids, use_scryfall)

            csv_buffer = io.StringIO()
            df_converted.to_csv(csv_buffer, index=False)
            st.download_button("Download converted CSV", data=csv_buffer.getvalue(), file_name="converted_tcgpt.csv", mime="text/csv")

            st.success("Conversion successful.")
        except Exception as e:
            st.error(f"Error processing the file: {e}")
