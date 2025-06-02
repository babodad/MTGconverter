# Web app for converting TopDecked CSV to TCG PowerTools format

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

def convert_to_tcgpowertools_format(df, default_condition, default_language):
    output = pd.DataFrame()
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

uploaded_file = st.file_uploader("Upload CSV file exported from TopDecked", type="csv")

remove_basics = st.checkbox("Remove basic lands", value=True)
default_condition = st.selectbox("Default condition", ["NM", "EX", "GD", "LP", "PL", "PO"], index=0)
default_language = st.selectbox("Default language", ["English", "German", "French", "Spanish", "Italian", "Simplified Chinese", "Japanese", "Portuguese", "Russian", "Korean"], index=0)

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        if remove_basics:
            df = remove_basic_lands(df)
        df_grouped = consolidate_duplicates(df)
        df_converted = convert_to_tcgpowertools_format(df_grouped, default_condition, default_language)

        csv_buffer = io.StringIO()
        df_converted.to_csv(csv_buffer, index=False)
        st.download_button("Download converted CSV", data=csv_buffer.getvalue(), file_name="converted_tcgpt.csv", mime="text/csv")

        st.success("Conversion successful.")
    except Exception as e:
        st.error(f"Error processing the file: {e}")
