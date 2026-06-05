import base64
import duckdb
import folium
import pandas as pd
import streamlit as st
import altair as alt
from streamlit_folium import st_folium
from pathlib import Path


# Set Streamlit page configuration and custom CSS for better font sizes
st.set_page_config(layout="wide")

APP_DIR = Path(__file__).parent

def font_to_base64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()

regular_font = font_to_base64(APP_DIR / "fonts" / "IRANSans Regular.ttf")
medium_font = font_to_base64(APP_DIR / "fonts" / "IRANSans Medium.ttf")

st.markdown(
    f"""
<style>

/* ------------------ Fonts ------------------ */

@font-face {{
    font-family: 'IRANSans';
    src: url(data:font/truetype;charset=utf-8;base64,{regular_font}) format('truetype');
    font-weight: 400;
}}

@font-face {{
    font-family: 'IRANSans';
    src: url(data:font/truetype;charset=utf-8;base64,{medium_font}) format('truetype');
    font-weight: 500;
}}

/* Apply to everything */

* {{
    font-family: 'IRANSans', sans-serif !important;
}}

/* Main app */

html,
body,
.stApp,
[data-testid="stAppViewContainer"] {{
    font-family: 'IRANSans', sans-serif !important;
    font-weight: 400 !important;
}}

/* Titles and headings */

h1,
h2,
h3,
h4,
h5,
h6,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {{
    font-family: 'IRANSans', sans-serif !important;
    font-weight: 500 !important;
}}

/* Sidebar */

[data-testid="stSidebar"] *,
[data-testid="stSidebarNav"] * {{
    font-family: 'IRANSans', sans-serif !important;
}}

/* Widget labels */

label,
.stSelectbox,
.stRadio,
.stMultiSelect,
.stSlider,
.stCheckbox,
.stButton {{
    font-family: 'IRANSans', sans-serif !important;
    font-weight: 500 !important;
}}

/* DataFrames and tables */

[data-testid="stDataFrame"] *,
table,
th,
td {{
    font-family: 'IRANSans', sans-serif !important;
    font-weight: 400 !important;
}}

/* Altair / Vega charts */

.vega-embed text,
.vega-text {{
    font-family: 'IRANSans', sans-serif !important;
}}

/* Markdown text */

p,
span,
div {{
    font-family: 'IRANSans', sans-serif !important;
    font-weight: 400 !important;
}}

</style>
""",
    unsafe_allow_html=True,
)



# ----------- DuckDB connection & loaders ----------- #

DB_PATH = "data/duckdb/iod_dash.duckdb"
con = duckdb.connect(DB_PATH, read_only=True)

df_facts = con.execute("SELECT * FROM econ_facts").fetchdf()
df_master_en = con.execute("SELECT * FROM master_en").fetchdf()
df_master_fa = con.execute("SELECT * FROM master_fa").fetchdf()
df_geo = con.execute("SELECT * FROM geo").fetchdf()
df_sub = con.execute("SELECT * FROM sub").fetchdf()


# -------------- Language configuration ------------ #


lang = st.sidebar.selectbox(
    "Language / زبان",
    options=["fa", "en"],
    format_func=lambda k: {"en": "English", "fa": "فارسی"}.get(k, k),
    index=1 # index =1 Set the default page English, insex = 0 would set the default page to Farsi,
)

facts = df_facts.drop_duplicates().dropna(subset=["time_id", "value"], how="all").reset_index(drop=True)
master = df_master_fa if lang == "fa" else df_master_en
geo_label_col = "geo_label_fa" if lang == "fa" else "geo_label_en"
sub_label_col = "sub_label_fa" if lang == "fa" else "sub_label_en"
detail_col = "detail_fa" if lang == "fa" else "detail"


# ------- Dashboard title, subtitle and header -------- #

if lang == "en":
    st.image("https://pbs.twimg.com/profile_images/2048301384337088512/SJV40xp__400x400.jpg", width=200)
    st.markdown(
        """
        <h1 dir="rtl" style="text-align:left;">
        <a href="https://iranopendata.org" target="_blank"
        style="text-decoration:none; color:inherit;">
        Iran Open Data
        </a>
        </h1>

        <h3 dir="rtl";">
        <a href="https://iranopendata.org" target="_blank"
        style="text-decoration:none; color:inherit;">
        To see more data, visit the Iran Open Data website.
        </a>
        </h3>
        """,
    unsafe_allow_html=True)
    
else:
    st.markdown(
        """
        <h1 dir="rtl" style="text-align:right;">
        <a href="https://iranopendata.org" target="_blank"
        style="text-decoration:none; color:inherit;">
        مرکز داده‌های باز ایران
        </a>
        </h1>

        <h3 dir="rtl" style="text-align:right;">
        <a href="https://iranopendata.org" target="_blank"
        style="text-decoration:none; color:inherit;">
        برای مشاهده و دانلود داده‌های بیشتر به وب‌سایت مرکز داده‌های باز ایران مراجعه کنید
        </a>
        </h3>
        """,
    unsafe_allow_html=True)



# ------------------ dataset and subs selection ------------------ #

# to remove '01-', '02-'... from options for better display in selectbox. The numbers are only for ordering and not meaningful for users,
# so we can safely remove them in the UI. But we keep the original values in the backend for filtering.
def clean_option(x):
    return x[3:] if isinstance(x, str) and len(x) > 3 else x


## dataset selection

datasets = master["main_category"].dropna().unique().tolist()
dataset_map = {clean_option(x): x for x in datasets}

selected_main_cat_clean = st.sidebar.selectbox(
    "Main Category" if lang == "en" else "بخش‌های اصلی",
    options=list(dataset_map.keys()),
    index=0,
)

selected_main_cat = dataset_map[selected_main_cat_clean]

## subs selection

subs_list = [f"sub_{i}" for i in range(1, 11)]
filtered_master = master[master["main_category"] == selected_main_cat].copy()

if filtered_master.empty:
    st.error("No metadata found for this category." if lang == "en" else "برای این بخش، داده‌ای در متادیتا پیدا نشد.")
    st.stop()

topic_id = filtered_master["topic_id"].iloc[0]

for item in subs_list:
    if item in filtered_master.columns and filtered_master[item].notna().any():
        options = filtered_master[item].dropna().unique().tolist()
        option_map = {clean_option(x): x for x in options}

        label = "Select options" if lang == "en" else "انتخاب گزینه"

        selected_sub_clean = st.sidebar.selectbox(
            label,
            options=list(option_map.keys())
        )

        selected_sub = option_map[selected_sub_clean]
        filtered_master = filtered_master[filtered_master[item] == selected_sub].copy()


        if filtered_master.empty:
            st.error("No matching topic found." if lang == "en" else "موضوعی مطابق با این انتخاب پیدا نشد.")
            st.stop()

        topic_id = filtered_master["topic_id"].iloc[0]
    else:
        break


# ------------------- filtering data ------------------- #

filtered_facts = facts[facts["topic_id"] == topic_id].copy()

if filtered_facts.empty:
    if lang == "en":
        st.warning(
            "To see this dataset, visit "
            "[Iran Open Data](https://iranopendata.org)"
        )
    else:
        st.markdown("""
        <div dir="rtl"
             style="padding:1rem; border-radius:0.5rem;
                    background-color:#fff3cd; color:#664d03;
                    border:1px solid #ffecb5; text-align:right;">
            برای مشاهده این داده به
            <a href="https://iranopendata.org" target="_blank">
                سایت مرکز داده‌های باز ایران
            </a>
            مراجعه کنید.
        </div>
        """, unsafe_allow_html=True)

    st.stop()

fact_cols = ["topic_id", "time_id", "value", "geo_code", "sub_code"]
if detail_col in filtered_facts.columns:
    fact_cols.append(detail_col)

df = (
    filtered_facts[fact_cols]
    .merge(
        master.drop_duplicates(subset="topic_id"),
        on="topic_id",
        how="left",
        validate="many_to_one"
    )
    .merge(
        df_geo.drop_duplicates(subset="geo_code"),
        on="geo_code",
        how="left",
        validate="many_to_one"
    )
    .merge(
        df_sub.drop_duplicates(subset="sub_code"),
        on="sub_code",
        how="left",
        validate="many_to_one"
    )
    .rename(columns={geo_label_col: "geo_name", sub_label_col: "sub_label"})
)


# ------------------- type handling ------------------- #

if "id_type" in df.columns and not df["id_type"].isna().all():
    if df["id_type"].iloc[0] == "time":
        freq = df["frequency"].iloc[0] if "frequency" in df.columns else None

        df["time_id"] = df["time_id"].astype(str).str.strip()

        if freq == "yearly":
            df["time_id"] = df["time_id"].str[:4]
        elif freq in ["seasonal", "monthly"]:
            df["time_id"] = df["time_id"].str[:7]
        elif freq == "daily":
            df["time_id"] = df["time_id"].str[:10]
    else:
        df["time_id"] = df["time_id"].astype(str)
else:
    df["time_id"] = df["time_id"].astype(str)


if "val_type" in df.columns and not df["val_type"].isna().all():
    if df["val_type"].iloc[0] == "num":
        # replace ',' with ''
        df['value'] = df['value'].str.replace(',', '')
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    else:
        df["value"] = df["value"].astype(str)


#------------------- check the access ------------------- #
#check access column in master table.
#1- If it is 'free' go ahead and show the data
#2- If it's 'subscription' or 'enterprise' check if user is logged in, if not show a message to log in.
# If logged in, get the username from session state or cookie,
# and check if the username is in the 'subscription list' or 'enterprise list' show the data
# If not, show a message that the user does not have access to this dataset and stop the execution
# for now 'subscription list' and 'enterprise list' are just an empty list, but in a real application they should be populated with actual usernames.
access_type = filtered_master["access"].iloc[0]
if access_type == "free" or access_type == "subscriber" or access_type == "enterprise":
    pass
elif access_type in ["subscription", "enterprise"]:
    if "user_logged_in" not in st.session_state or not st.session_state["user_logged_in"]:
        st.warning("Please log in to access this dataset." if lang == "en" else "لطفا برای دسترسی به این مجموعه‌داده وارد شوید.")
        st.stop()
    else:
        username = st.session_state.get("username", "")
        subscription_list = []  # This should be populated with actual usernames
        enterprise_list = []  # This should be populated with actual usernames

        if (access_type == "subscription" and username in subscription_list) or (access_type == "enterprise" and username in enterprise_list):
            pass
        else:
            st.error("You do not have access to this dataset." if lang == "en" else "شما به این مجموعه‌داده دسترسی ندارید.")
            st.stop()


# ------------------- dataframe for display ------------------- #

display_cols = [
    "indicator_label", "geo_name", "sub_label", "time_id", "value",
    "default_unit", "calendar", "default_source"
]

if detail_col in df.columns:
    display_cols.insert(8, detail_col)

display_cols = [col for col in display_cols if col in df.columns]

df_to_display = df[display_cols].reset_index(drop=True)

if "geo_name" in df_to_display.columns and df_to_display["geo_name"].dropna().nunique() <= 1:
    df_to_display = df_to_display.drop(columns=["geo_name"])

if "sub_label" in df_to_display.columns and df_to_display["sub_label"].dropna().nunique() <= 1:
    df_to_display = df_to_display.drop(columns=["sub_label"])

if "geo_name" in df_to_display.columns and df_to_display["geo_name"].dropna().nunique() <= 1:
    df_to_display = df_to_display.drop(columns=["geo_name"])

if "sub_label" in df_to_display.columns and df_to_display["sub_label"].dropna().nunique() <= 1:
    df_to_display = df_to_display.drop(columns=["sub_label"])

column_labels = {
    "en": {
        "indicator_label": "Indicator",
        "geo_name": "Geo",
        "sub_label": "Sub",
        "time_id": "Time",
        "value": "Value",
        "default_unit":"Unit",
        "calendar": "Calendar",
        "default_source": "Source",
        "detail": "Detail",
        "detail_fa": "Detail",
    },
    "fa": {
        "indicator_label": "شاخص",
        "geo_name": "جغرافیا",
        "sub_label": "بخش",
        "time_id": "زمان",
        "value": "مقدار",
        "default_unit":"واحد",
        "calendar": "تقویم",
        "default_source": "منبع",
        "detail": "توضیحات",
        "detail_fa": "توضیحات",
    }
}

df_to_display = df_to_display.rename(columns=column_labels[lang])


st.dataframe(df_to_display)


# ------------------- display chart ------------------- #

chart_type = filtered_master["chart_type"].iloc[0] if "chart_type" in filtered_master.columns else "none"

df_chart = df.copy()

if df["requires_time_selection"].iloc[0] == True:
    time_options = sorted(df["time_id"].dropna().unique().tolist(), reverse=True)
    selected_time = st.selectbox(
        "Select Time" if lang == "en" else "انتخاب زمان",
        options=time_options
    )
    df_chart = df[df["time_id"] == selected_time].copy()

if df_chart.empty:
    st.warning("No chart data available." if lang == "en" else "داده‌ای برای نمودار موجود نیست.")
    st.stop()

if chart_type is None or chart_type == "none":
    st.write("No chart available for this dataset." if lang == "en" else "چارتی برای این مجموعه‌داده در دسترس نیست.")


## line chart 

if chart_type == "line":
    df_chart = df_chart.sort_values("time_id")

    line_color = (
        "geo_name"
        if "geo_name" in df_chart.columns and df_chart["geo_name"].dropna().nunique() > 1
        else alt.value("steelblue")
    )

    tooltips = ["indicator_label", "time_id", "value"]
    if detail_col in df_chart.columns:
        tooltips.append(detail_col)
    if "geo_name" in df_chart.columns and df_chart["geo_name"].notna().any():
        tooltips.append("geo_name")
    if "sub_label" in df_chart.columns and df_chart["sub_label"].notna().any():
        tooltips.append("sub_label")

    chart = alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X("time_id", title=None),
        y=alt.Y("value", title=None),
        color=line_color,
        tooltip=tooltips
    ).properties(title=filtered_master["indicator_label"].iloc[0])

    st.altair_chart(chart, use_container_width=True)


## bar chart

if chart_type == "bar":

    # sort descending and keep top 35
    df_chart = (
        df_chart.sort_values("value", ascending=False)
        .head(35)
        .copy()
    )

    ## numeric_values = df_chart["value"].dropna()
    ## if len(numeric_values) >= 2:
    ##     top2 = numeric_values.nlargest(2).tolist()
    ##     if top2[0] > 2.5 * top2[1]:
    ##         df_chart.loc[df_chart["value"] == top2[0], "value"] = None

    geo_unique = "geo_name" in df_chart.columns and df_chart["geo_name"].dropna().nunique() > 1
    sub_unique = "sub_label" in df_chart.columns and df_chart["sub_label"].dropna().nunique() > 1
    time_unique = "time_id" in df_chart.columns and df_chart["time_id"].dropna().nunique() > 1

    if geo_unique and sub_unique:
        x_axis = st.selectbox(
            "Select X axis:" if lang == "en" else "انتخاب محور ایکس:",
            options=["geo_name", "sub_label"],
            index=0,
        )
    elif geo_unique:
        x_axis = "geo_name"
    elif sub_unique:
        x_axis = "sub_label"
    elif time_unique:
        x_axis = "time_id"
    else:
        x_axis = "indicator_label"

    tooltips = ["indicator_label", "time_id", "value"]
    if detail_col in df_chart.columns:
        tooltips.append(detail_col)
    if "geo_name" in df_chart.columns and df_chart["geo_name"].notna().any():
        tooltips.append("geo_name")
    if "sub_label" in df_chart.columns and df_chart["sub_label"].notna().any():
        tooltips.append("sub_label")

    chart = alt.Chart(df_chart).mark_bar().encode(
        x=alt.X(x_axis, sort="-y", title=None),
        y=alt.Y("value", title=None),
        tooltip=tooltips,
        color=alt.value("steelblue")
    )

    st.altair_chart(chart, use_container_width=True)


#map chart 

if chart_type == "map":
    df_map = df.dropna(subset=["latitude", "longitude"]).copy()

    if df_map.empty:
        st.warning("No coordinates available for map display." if lang == "en" else "مختصاتی برای نمایش نقشه موجود نیست.")
    else:
        m = folium.Map(
            location=[df_map["latitude"].mean(), df_map["longitude"].mean()],
            zoom_start=2
        )

        for _, row in df_map.iterrows():
            popup_text = f"{row.get('geo_name', '')}: {row.get('indicator_label', '')} {row.get('value', '')} {row.get('default_unit', '')}"

            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=5,
                popup=popup_text,
                color="red",
                fill=True,
                fill_color="red",
                fill_opacity=0.7
            ).add_to(m)

        st_folium(m, width=700, height=500)