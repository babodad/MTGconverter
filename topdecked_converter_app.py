# Web-App zur Umwandlung von TopDecked CSV in TCG PowerTools Format

import pandas as pd
import streamlit as st
import io

def remove_basic_lands(df):
    basic_land_names = ["Plains", "Island", "Swamp", "Mountain", "Forest"]
    return df[~df["NAME"].isin(basic_land_names)].copy()

def consolidate_duplicates(df):
    group_cols = ["NAME", "SETNAME", "SETCODE", "FINISH", "CONDITION", "LANG", "NOTES"]
    df["QUANTITY"] = pd.to_numeric(df["QUANTITY"], errors="coerce").fillna(0).astype(int)
    return df.groupby(group_cols, dropna=False, as_index=False).agg({"QUANTITY": "sum"})

def convert_to_tcgpowertools_format(df):
    output = pd.DataFrame()
    output["idProduct"] = ""
    output["quantity"] = df["QUANTITY"]
    output["name"] = df["NAME"]
    output["set"] = df["SETNAME"].fillna(df["SETCODE"])
    output["condition"] = df["CONDITION"].fillna("NM")
    output["language"] = df["LANG"].fillna("English")
    output["isFoil"] = df["FINISH"].str.lower().eq("foil")
    output["isPlayset"] = ""
    output["isSigned"] = ""
    output["isFirstEd"] = ""
    output["price"] = ""
    output["comment"] = df["NOTES"].fillna("")
    return output

st.title("TopDecked → TCG PowerTools Converter")

uploaded_file = st.file_uploader("CSV-Datei von TopDecked hochladen", type="csv")
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        df_clean = remove_basic_lands(df)
        df_grouped = consolidate_duplicates(df_clean)
        df_converted = convert_to_tcgpowertools_format(df_grouped)

        csv_buffer = io.StringIO()
        df_converted.to_csv(csv_buffer, index=False)
        st.download_button("Download konvertierte CSV", data=csv_buffer.getvalue(), file_name="converted_tcgpt.csv", mime="text/csv")

        st.success("Konvertierung erfolgreich.")
    except Exception as e:
        st.error(f"Fehler beim Verarbeiten der Datei: {e}")
