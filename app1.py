from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import duckdb

# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Chicago Crime Index",
    page_icon="🚨",
    layout="wide"
)

# Change this to your dataset path
DATA_PATH = Path("chicago_crimes.csv")


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data
def load_data(path):
    df = pd.read_csv(path)

    # Convert date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Make year numeric
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

    return df


df = load_data(DATA_PATH)

# ============================================================
# TITLE
# ============================================================

st.title("Chicago Crime Index")

st.markdown(
    """
    **Explore reported crime in Chicago over time.**

    This dashboard allows you to examine crime trends, compare crime types,
    explore geographic patterns, and analyze arrests using data from the
    City of Chicago Data Portal.
    """
)

st.divider()

# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header("Filters")

# Years
years = sorted(df["Year"].dropna().unique())

selected_years = st.sidebar.slider(
    "Year range",
    min_value=int(min(years)),
    max_value=int(max(years)),
    value=(int(min(years)), int(max(years)))
)

# Crime types
crime_types = sorted(df["Primary Type"].dropna().unique())

selected_crimes = st.sidebar.multiselect(
    "Crime type",
    options=crime_types,
    default=[]
)

# District
districts = sorted(df["District"].dropna().unique())

selected_districts = st.sidebar.multiselect(
    "District",
    options=districts,
    default=[]
)

# Location
locations = sorted(df["Location Description"].dropna().unique())

selected_locations = st.sidebar.multiselect(
    "Location type",
    options=locations,
    default=[]
)

# Arrest
arrest_filter = st.sidebar.selectbox(
    "Arrest",
    ["All", "Yes", "No"]
)

# ============================================================
# FILTER DATA USING DUCKDB
# ============================================================

query = """
SELECT *
FROM df
WHERE Year BETWEEN ? AND ?
"""

params = [selected_years[0], selected_years[1]]

if selected_crimes:
    query += " AND \"Primary Type\" IN ({})".format(
        ",".join(["?"] * len(selected_crimes))
    )
    params.extend(selected_crimes)

if selected_districts:
    query += " AND District IN ({})".format(
        ",".join(["?"] * len(selected_districts))
    )
    params.extend(selected_districts)

if selected_locations:
    query += " AND \"Location Description\" IN ({})".format(
        ",".join(["?"] * len(selected_locations))
    )
    params.extend(selected_locations)

if arrest_filter != "All":
    query += " AND Arrest = ?"
    params.append(arrest_filter == "Yes")

filtered_df = duckdb.execute(query, params).df()

# ============================================================
# KPI SECTION
# ============================================================

st.subheader("Overview")

total_crimes = len(filtered_df)

total_arrests = (
    filtered_df["Arrest"]
    .astype(str)
    .str.lower()
    .eq("true")
    .sum()
)

arrest_rate = (
    total_arrests / total_crimes * 100
    if total_crimes > 0
    else 0
)

most_common_crime = (
    filtered_df["Primary Type"].value_counts().idxmax()
    if not filtered_df.empty
    else "N/A"
)

most_common_location = (
    filtered_df["Location Description"].value_counts().idxmax()
    if not filtered_df.empty
    else "N/A"
)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Reported crimes",
    f"{total_crimes:,}"
)

col2.metric(
    "Arrests",
    f"{total_arrests:,}"
)

col3.metric(
    "Arrest rate",
    f"{arrest_rate:.1f}%"
)

col4.metric(
    "Most common crime",
    most_common_crime
)

st.caption(
    f"Selected period: {selected_years[0]}–{selected_years[1]}"
)

# ============================================================
# TRENDS
# ============================================================

st.divider()

st.subheader("Crime Trends")

if not filtered_df.empty:

    yearly_crimes = (
        filtered_df
        .groupby("Year")
        .size()
        .reset_index(name="Crimes")
        .sort_values("Year")
    )

    fig = px.line(
        yearly_crimes,
        x="Year",
        y="Crimes",
        markers=True,
        title="Reported crimes over time"
    )

    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Number of reported crimes",
        hovermode="x unified"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

else:
    st.warning("No data available for the selected filters.")

# ============================================================
# CRIME TRENDS TABLE
# ============================================================

st.subheader("Crime Trends Table")

# Make sure Year is numeric
filtered_df["Year"] = pd.to_numeric(
    filtered_df["Year"],
    errors="coerce"
)

filtered_df = filtered_df.dropna(subset=["Year"]).copy()
filtered_df["Year"] = filtered_df["Year"].astype(int)

# ------------------------------------------------------------
# Use only complete years: 2023, 2024, 2025
# ------------------------------------------------------------

years = sorted(
    filtered_df["Year"].unique()
)

# Exclude the current incomplete year
current_year = max(years)

complete_years = [
    year for year in years
    if year < current_year
]

# Newest year first
complete_years = sorted(
    complete_years,
    reverse=True
)

# Data for complete years only
complete_df = filtered_df[
    filtered_df["Year"].isin(complete_years)
].copy()

# ------------------------------------------------------------
# Crime categories
# ------------------------------------------------------------

crime_categories = [
    "ROBBERY",
    "ASSAULT",
    "BATTERY",
    "BURGLARY",
    "THEFT",
    "MOTOR VEHICLE THEFT",
    "HOMICIDE"
]

# Keep only crime types that exist in the dataset
available_categories = [
    crime
    for crime in crime_categories
    if crime in complete_df["Primary Type"].unique()
]

# ------------------------------------------------------------
# Create yearly counts
# ------------------------------------------------------------

yearly_counts = {}

for crime in available_categories:

    counts = (
        complete_df[
            complete_df["Primary Type"] == crime
        ]
        .groupby("Year")
        .size()
        .reindex(complete_years, fill_value=0)
    )

    yearly_counts[crime] = counts

# ------------------------------------------------------------
# Total reported crimes
# ------------------------------------------------------------

total_counts = (
    complete_df
    .groupby("Year")
    .size()
    .reindex(complete_years, fill_value=0)
)

# ------------------------------------------------------------
# Build table
# ------------------------------------------------------------

table = pd.DataFrame()

# Year
table["Year"] = complete_years

# ------------------------------------------------------------
# Function for Year-over-Year change
# ------------------------------------------------------------

def calculate_change(counts, year, all_years):

    # 2023 cannot be compared because the dataset
    # starts on January 1, 2023
    previous_years = [
        y for y in all_years
        if y < year
    ]

    if len(previous_years) == 0:
        return np.nan

    previous_year = max(previous_years)

    current_count = counts.loc[year]
    previous_count = counts.loc[previous_year]

    if previous_count == 0:
        return np.nan

    return (
        (current_count - previous_count)
        / previous_count
        * 100
    )


# ------------------------------------------------------------
# Add crime columns
# ------------------------------------------------------------

for crime in available_categories:

    counts = yearly_counts[crime]

    # Count
    table[f"{crime} — Count"] = [
        int(counts.loc[year])
        for year in complete_years
    ]

    # Change From Previous Year
    table[f"{crime} — Change From Previous Year"] = [
        calculate_change(
            counts,
            year,
            complete_years
        )
        for year in complete_years
    ]

# ------------------------------------------------------------
# Add Total Reported Crimes
# ------------------------------------------------------------

table["Total Reported Crimes — Count"] = [
    int(total_counts.loc[year])
    for year in complete_years
]

table["Total Reported Crimes — Change From Previous Year"] = [
    calculate_change(
        total_counts,
        year,
        complete_years
    )
    for year in complete_years
]

# ------------------------------------------------------------
# Format Count columns
# ------------------------------------------------------------

for column in table.columns:

    if "Count" in column:

        table[column] = (
            table[column]
            .astype(int)
            .map(lambda x: f"{x:,}")
        )

# ------------------------------------------------------------
# Format Change columns
# ------------------------------------------------------------

for column in table.columns:

    if "Change From Previous Year" in column:

        table[column] = table[column].map(
            lambda x:
            "—"
            if pd.isna(x)
            else f"{x:+.1f}%"
        )

# ------------------------------------------------------------
# Highlight changes
# Decrease = green
# Increase = red
# ------------------------------------------------------------

def highlight_change(value):

    if value == "—":
        return ""

    try:

        number = float(
            value
            .replace("%", "")
            .replace("+", "")
        )

        if number < 0:
            return (
                "background-color: #d9f2d9;"
                "color: #187a18;"
                "font-weight: bold;"
            )

        elif number > 0:
            return (
                "background-color: #f8d7da;"
                "color: #b02a37;"
                "font-weight: bold;"
            )

    except:
        pass

    return ""


# ------------------------------------------------------------
# Apply styling
# ------------------------------------------------------------

change_columns = [
    column
    for column in table.columns
    if "Change From Previous Year" in column
]

styled_table = table.style

for column in change_columns:

    styled_table = styled_table.map(
        highlight_change,
        subset=[column]
    )

# ------------------------------------------------------------
# Display
# ------------------------------------------------------------

st.dataframe(
    styled_table,
    use_container_width=True,
    hide_index=True
)

# ------------------------------------------------------------
# Note
# ------------------------------------------------------------

st.caption(
    "Percentage changes show the year-over-year change in reported "
    "crime counts. 2023 is shown without a percentage change because "
    "the dataset starts on January 1, 2023 and therefore does not "
    "contain data for 2022."
)
# ============================================================
# CRIME TYPES
# ============================================================

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Crime by Type")

    crime_counts = (
        filtered_df["Primary Type"]
        .value_counts()
        .head(10)
        .reset_index()
    )

    crime_counts.columns = ["Crime Type", "Count"]

    fig = px.bar(
        crime_counts,
        x="Count",
        y="Crime Type",
        orientation="h",
        title="Top 10 crime types"
    )

    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis_title="Number of crimes",
        yaxis_title=""
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

# ============================================================
# LOCATION TYPES
# ============================================================

with col2:
    st.subheader("Crime by Location")

    location_counts = (
        filtered_df["Location Description"]
        .value_counts()
        .head(10)
        .reset_index()
    )

    location_counts.columns = ["Location", "Count"]

    fig = px.bar(
        location_counts,
        x="Count",
        y="Location",
        orientation="h",
        title="Top 10 locations"
    )

    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis_title="Number of crimes",
        yaxis_title=""
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

# ============================================================
# ARREST ANALYSIS
# ============================================================

st.divider()

st.subheader("Arrest Analysis")

arrest_data = (
    filtered_df["Arrest"]
    .astype(str)
    .str.lower()
    .value_counts()
    .reset_index()
)

arrest_data.columns = ["Arrest", "Count"]

arrest_data["Arrest"] = arrest_data["Arrest"].replace(
    {
        "true": "Arrest",
        "false": "No arrest"
    }
)

fig = px.pie(
    arrest_data,
    names="Arrest",
    values="Count",
    title="Crimes resulting in an arrest"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ============================================================
# DISTRICT ANALYSIS
# ============================================================

st.divider()

st.subheader("Crime by District")

district_data = (
    filtered_df["District"]
    .value_counts()
    .reset_index()
)

district_data.columns = ["District", "Count"]

fig = px.bar(
    district_data,
    x="District",
    y="Count",
    title="Reported crimes by police district"
)

fig.update_layout(
    xaxis_title="District",
    yaxis_title="Number of crimes"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ============================================================
# MAP
# ============================================================

st.divider()

st.subheader("Geographic Distribution")

map_df = filtered_df[
    ["Latitude", "Longitude", "Primary Type"]
].dropna()

# Limit points for performance
if len(map_df) > 10000:
    map_df = map_df.sample(10000, random_state=42)

if not map_df.empty:

    st.map(
        map_df.rename(
            columns={
                "Latitude": "latitude",
                "Longitude": "longitude"
            }
        ),
        latitude="latitude",
        longitude="longitude"
    )

    st.caption(
        "The map shows a sample of reported crime locations."
    )

else:
    st.info("No geographic data available for the selected filters.")

# ============================================================
# DATA TABLE
# ============================================================

st.divider()

st.subheader("Data Table")

display_columns = [
    "ID",
    "Case Number",
    "Date",
    "Primary Type",
    "Description",
    "Location Description",
    "Arrest",
    "Domestic",
    "District",
    "Ward",
    "Community Area",
    "Year"
]

display_columns = [
    col for col in display_columns
    if col in filtered_df.columns
]

st.dataframe(
    filtered_df[display_columns].sort_values(
        "Date",
        ascending=False
    ).head(1000),
    use_container_width=True,
    height=500
)

# ============================================================
# DOWNLOAD
# ============================================================

csv = filtered_df.to_csv(index=False)

st.download_button(
    label="Download filtered data",
    data=csv,
    file_name="chicago_crimes_filtered.csv",
    mime="text/csv"
)

# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Source: City of Chicago Data Portal — Crimes 2001 to Present"
)