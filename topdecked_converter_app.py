# Web app for converting TopDecked CSV to TCG PowerTools format

import pandas as pd
import streamlit as st
import io
import json
from functools import lru_cache

def remove_basic_lands(df):
    basic_land_names = ["Plains", "Island", "Swamp", "Mountain", "Forest"]
    return df[~df["NAME"].isin(basic_land_names)].copy()

def consolidate_duplicates(df):
    group_cols = ["NAME", "SETNAME", "SETCODE", "FINISH", "CONDITION", "LANG", "NOTES"]
    df["QUANTITY"] = pd.to_numeric(df["QUANTITY"], errors="coerce").fillna(0).astype(int)
    return df.groupby(group_cols, dropna=False, as_index=False).agg({"QUANTITY": "sum"})

@lru_cache(maxsize=1)
def load_cardmarket_mapping():
    path = "products_singles_1.json"  # expects this file to be in the working directory
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
            if name:
                if name not in lookup:
                    lookup[name] = []
                lookup[name].append(entry.get("idProduct", ""))
    return lookup

def get_cardmarket_id(name, lookup):
    matches = lookup.get(name.strip().lower(), [])
    return matches[0] if matches else ""

def convert_error_format(df):
    df.columns = df.columns.str.strip().str.lower()
    required = ["count", "name", "expansion"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in TCG ImportErrors format.")

    df["QUANTITY"] = df["count"]
    df["NAME"] = df["name"]
    df["SETNAME"] = df["expansion"]
    df["SETCODE"] = ""
    df["FINISH"] = ""
    df["CONDITION"] = ""
    df["LANG"] = ""
    df["NOTES"] = ""
    return df[["QUANTITY", "NAME", "SETNAME", "SETCODE", "FINISH", "CONDITION", "LANG", "NOTES"]]

def convert_topdecked_format(df):
    df.columns = df.columns.str.strip().str.upper()
    required = ["QUANTITY", "NAME"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in TopDecked format.")
    return df

def convert_to_tcgpowertools_format(df, default_condition, default_language, fetch_ids=False):
    output = pd.DataFrame()
    if fetch_ids:
        lookup = build_id_lookup_table()
        output["idProduct"] = df.apply(lambda row: get_cardmarket_id(row["NAME"], lookup), axis=1)
    else:
        output["idProduct"] = ""
    output["quantity"] = df["QUANTITY"]
    output["name"] = df["NAME"]
    output["set"] = df["SETNAME"].fillna(df["SETCODE"])
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

if uploaded_file is not None:
    if st.button("Convert"):
        try:
            df = pd.read_csv(uploaded_file)
            if input_format == "TCG ImportErrors":
                df = convert_error_format(df)
            else:
                df = convert_topdecked_format(df)

            if remove_basics:
                df = remove_basic_lands(df)

            df_grouped = consolidate_duplicates(df)
            df_converted = convert_to_tcgpowertools_format(df_grouped, default_condition, default_language, fetch_ids)

            csv_buffer = io.StringIO()
            df_converted.to_csv(csv_buffer, index=False)
            st.download_button("Download converted CSV", data=csv_buffer.getvalue(), file_name="converted_tcgpt.csv", mime="text/csv")

            st.success("Conversion successful.")
        except Exception as e:
            st.error(f"Error processing the file: {e}")
