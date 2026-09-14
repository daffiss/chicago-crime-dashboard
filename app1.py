from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
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

DATA_PATH = Path(__file__).parent / "chicago_crimes.csv"


# ============================================================
# DUCKDB CONNECTION
# ============================================================

@st.cache_resource
def get_connection():
    con = duckdb.connect()

    csv_path = str(DATA_PATH).replace("\\", "/").replace("'", "''")

    con.execute(
        f"""
        CREATE OR REPLACE VIEW crimes AS
        SELECT *
        FROM read_csv_auto('{csv_path}', header=true)
        """
    )

    return con


con = get_connection()

# ============================================================
# BASIC INFORMATION FOR FILTERS
# ============================================================

@st.cache_data
def get_years():
    return con.execute(
        """
        SELECT DISTINCT CAST(Year AS INTEGER) AS Year
        FROM crimes
        WHERE Year IS NOT NULL
        ORDER BY Year
        """
    ).df()["Year"].tolist()


@st.cache_data
def get_crime_types():
    return con.execute(
        """
        SELECT DISTINCT "Primary Type"
        FROM crimes
        WHERE "Primary Type" IS NOT NULL
        ORDER BY "Primary Type"
        """
    ).df()["Primary Type"].tolist()


@st.cache_data
def get_districts():
    return con.execute(
        """
        SELECT DISTINCT District
        FROM crimes
        WHERE District IS NOT NULL
        ORDER BY District
        """
    ).df()["District"].tolist()


@st.cache_data
def get_locations():
    return con.execute(
        """
        SELECT DISTINCT "Location Description"
        FROM crimes
        WHERE "Location Description" IS NOT NULL
        ORDER BY "Location Description"
        """
    ).df()["Location Description"].tolist()


years = get_years()
crime_types = get_crime_types()
districts = get_districts()
locations = get_locations()


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

selected_years = st.sidebar.slider(
    "Year range",
    min_value=int(min(years)),
    max_value=int(max(years)),
    value=(int(min(years)), int(max(years)))
)

selected_crimes = st.sidebar.multiselect(
    "Crime type",
    options=crime_types,
    default=[]
)

selected_districts = st.sidebar.multiselect(
    "District",
    options=districts,
    default=[]
)

selected_locations = st.sidebar.multiselect(
    "Location type",
    options=locations,
    default=[]
)

arrest_filter = st.sidebar.selectbox(
    "Arrest",
    ["All", "Yes", "No"]
)


# ============================================================
# BUILD WHERE CLAUSE
# ============================================================

def build_where_clause():
    conditions = [
        'CAST("Year" AS INTEGER) BETWEEN ? AND ?'
    ]

    params = [
        selected_years[0],
        selected_years[1]
    ]

    if selected_crimes:
        placeholders = ",".join(["?"] * len(selected_crimes))

        conditions.append(
            f'"Primary Type" IN ({placeholders})'
        )

        params.extend(selected_crimes)

    if selected_districts:
        placeholders = ",".join(["?"] * len(selected_districts))

        conditions.append(
            f'District IN ({placeholders})'
        )

        params.extend(selected_districts)

    if selected_locations:
        placeholders = ",".join(["?"] * len(selected_locations))

        conditions.append(
            f'"Location Description" IN ({placeholders})'
        )

        params.extend(selected_locations)

    if arrest_filter != "All":
        conditions.append(
            'LOWER(CAST(Arrest AS VARCHAR)) = ?'
        )

        params.append(
            "true" if arrest_filter == "Yes" else "false"
        )

    where_clause = " AND ".join(conditions)

    return where_clause, params


where_clause, params = build_where_clause()


# ============================================================
# KPI SECTION
# ============================================================

st.subheader("Overview")


kpi_query = f"""
SELECT
    COUNT(*) AS total_crimes,

    SUM(
        CASE
            WHEN LOWER(CAST(Arrest AS VARCHAR)) = 'true'
            THEN 1
            ELSE 0
        END
    ) AS total_arrests,

    COUNT(DISTINCT "Primary Type") AS crime_types

FROM crimes

WHERE {where_clause}
"""


kpi = con.execute(
    kpi_query,
    params
).df().iloc[0]


total_crimes = int(kpi["total_crimes"])
total_arrests = int(kpi["total_arrests"] or 0)

arrest_rate = (
    total_arrests / total_crimes * 100
    if total_crimes > 0
    else 0
)


# Most common crime

most_common_crime_query = f"""
SELECT
    "Primary Type" AS crime,
    COUNT(*) AS count
FROM crimes
WHERE {where_clause}
GROUP BY "Primary Type"
ORDER BY count DESC
LIMIT 1
"""

most_common_result = con.execute(
    most_common_crime_query,
    params
).df()

most_common_crime = (
    most_common_result.iloc[0]["crime"]
    if not most_common_result.empty
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
# CRIME TRENDS
# ============================================================

st.divider()

st.subheader("Crime Trends")


trend_query = f"""
SELECT
    CAST("Year" AS INTEGER) AS Year,
    COUNT(*) AS Crimes
FROM crimes
WHERE {where_clause}
GROUP BY Year
ORDER BY Year
"""

yearly_crimes = con.execute(
    trend_query,
    params
).df()


if not yearly_crimes.empty:

    # Convert years to strings so Plotly treats them as categories
    yearly_crimes["Year"] = yearly_crimes["Year"].astype(int).astype(str)

    fig = px.line(
        yearly_crimes,
        x="Year",
        y="Crimes",
        markers=True,
        category_orders={
            "Year": sorted(yearly_crimes["Year"].unique())
        }
    )

    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Number of reported crimes",
        hovermode="x unified"
    )

    # Force the x-axis to be categorical
    fig.update_xaxes(
        type="category"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:
    st.warning(
        "No data available for the selected filters."
    )



# ============================================================
# CRIME TYPES
# ============================================================

st.divider()

col1, col2 = st.columns(2)


with col1:

    st.subheader("Crime by Type")

    crime_query = f"""
    SELECT
        "Primary Type" AS "Crime Type",
        COUNT(*) AS Count
    FROM crimes
    WHERE {where_clause}
    GROUP BY "Primary Type"
    ORDER BY Count DESC
    LIMIT 10
    """

    crime_counts = con.execute(
        crime_query,
        params
    ).df()

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
        width="stretch"
    )


# ============================================================
# LOCATION TYPES
# ============================================================

with col2:

    st.subheader("Crime by Location")

    location_query = f"""
    SELECT
        "Location Description" AS Location,
        COUNT(*) AS Count
    FROM crimes
    WHERE {where_clause}
    GROUP BY "Location Description"
    ORDER BY Count DESC
    LIMIT 10
    """

    location_counts = con.execute(
        location_query,
        params
    ).df()

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
        width="stretch"
    )

# ============================================================
# CRIME TRENDS TABLE
# ============================================================

st.subheader("Crime Trends Table")


crime_categories = [
    "ROBBERY",
    "ASSAULT",
    "BATTERY",
    "BURGLARY",
    "THEFT",
    "MOTOR VEHICLE THEFT",
    "HOMICIDE"
]


# ------------------------------------------------------------
# Get yearly counts directly from DuckDB
# ------------------------------------------------------------

table_query = f"""
SELECT
    CAST("Year" AS INTEGER) AS Year,
    "Primary Type",
    COUNT(*) AS Count
FROM crimes
WHERE {where_clause}
GROUP BY Year, "Primary Type"
ORDER BY Year
"""


table_raw = con.execute(
    table_query,
    params
).df()


table_years = sorted(
    table_raw["Year"].dropna().unique(),
    reverse=True
)


available_categories = [
    crime
    for crime in crime_categories
    if crime in table_raw["Primary Type"].unique()
]


table = pd.DataFrame()

table["Year"] = table_years


def calculate_change(
    counts,
    year,
    available_years
):

    # 2023 has no previous year in the dataset.
    if year == 2023:
        return np.nan

    # 2026 is incomplete / year-to-date.
    # Do not compare it with complete 2025.
    if year == 2026:
        return np.nan

    previous_year = year - 1

    if previous_year not in available_years:
        return np.nan

    current_count = counts.get(year, 0)
    previous_count = counts.get(previous_year, 0)

    if previous_count == 0:
        return np.nan

    return (
        (current_count - previous_count)
        / previous_count
        * 100
    )


# ------------------------------------------------------------
# Crime categories
# ------------------------------------------------------------

for crime in available_categories:

    crime_counts = (
        table_raw[
            table_raw["Primary Type"] == crime
        ]
        .set_index("Year")["Count"]
        .to_dict()
    )

    table[f"{crime} — Count"] = [
        int(crime_counts.get(year, 0))
        for year in table_years
    ]

    table[f"{crime} — Change From Previous Year"] = [
        calculate_change(
            crime_counts,
            year,
            table_years
        )
        for year in table_years
    ]


# ------------------------------------------------------------
# Total reported crimes
# ------------------------------------------------------------

total_yearly = (
    table_raw
    .groupby("Year")["Count"]
    .sum()
    .to_dict()
)


table["Total Reported Crimes — Count"] = [
    int(total_yearly.get(year, 0))
    for year in table_years
]

table["Total Reported Crimes — Change From Previous Year"] = [
    calculate_change(
        total_yearly,
        year,
        table_years
    )
    for year in table_years
]


# ------------------------------------------------------------
# Format count columns
# ------------------------------------------------------------

for column in table.columns:

    if "Count" in column:

        table[column] = (
            table[column]
            .astype(int)
            .map(lambda x: f"{x:,}")
        )


# ------------------------------------------------------------
# Format change columns
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

        if number > 0:
            return (
                "background-color: #f8d7da;"
                "color: #b02a37;"
                "font-weight: bold;"
            )

    except Exception:
        pass

    return ""


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


st.dataframe(
    styled_table,
    width="stretch",
    hide_index=True
)


st.caption(
    "Percentage changes show the year-over-year change in reported "
    "crime counts. 2023 is shown without a percentage change because "
    "the dataset starts on January 1, 2023. 2026 is shown as "
    "year-to-date data and is therefore not used for year-over-year "
    "percentage comparisons."
)

# ============================================================
# ARREST ANALYSIS
# ============================================================

st.divider()

st.subheader("Arrest Analysis")


arrest_query = f"""
SELECT
    CASE
        WHEN LOWER(CAST(Arrest AS VARCHAR)) = 'true'
        THEN 'Arrest'
        ELSE 'No arrest'
    END AS Arrest,
    COUNT(*) AS Count
FROM crimes
WHERE {where_clause}
GROUP BY Arrest
"""


arrest_data = con.execute(
    arrest_query,
    params
).df()


fig = px.pie(
    arrest_data,
    names="Arrest",
    values="Count",
    title="Crimes resulting in an arrest"
)

st.plotly_chart(
    fig,
    width="stretch"
)


# ============================================================
# DISTRICT ANALYSIS
# ============================================================

st.divider()

st.subheader("Crime by District")


district_query = f"""
SELECT
    District,
    COUNT(*) AS Count
FROM crimes
WHERE {where_clause}
GROUP BY District
ORDER BY District
"""


district_data = con.execute(
    district_query,
    params
).df()


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
    width="stretch"
)


# ============================================================
# MAP
# ============================================================

st.divider()

st.subheader("Geographic Distribution")


map_query = f"""
SELECT
    Latitude,
    Longitude,
    "Primary Type"
FROM crimes
WHERE {where_clause}
  AND Latitude IS NOT NULL
  AND Longitude IS NOT NULL
USING SAMPLE 10000
"""


map_df = con.execute(
    map_query,
    params
).df()


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
        "The map shows a sample of up to 10,000 reported crime locations."
    )

else:

    st.info(
        "No geographic data available for the selected filters."
    )


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


display_columns_sql = ", ".join(
    f'"{column}"'
    for column in display_columns
)


data_table_query = f"""
SELECT
    {display_columns_sql}
FROM crimes
WHERE {where_clause}
ORDER BY
    TRY_CAST(
        "Date" AS TIMESTAMP
    ) DESC
LIMIT 1000
"""


display_df = con.execute(
    data_table_query,
    params
).df()


st.dataframe(
    display_df,
    width="stretch",
    height=500
)


# ============================================================
# DOWNLOAD
# ============================================================

st.caption(
    "The download contains the filtered records."
)


@st.cache_data
def create_download_data(
    where_clause,
    params
):

    download_query = f"""
    SELECT *
    FROM crimes
    WHERE {where_clause}
    """

    download_df = con.execute(
        download_query,
        params
    ).df()

    return download_df.to_csv(index=False)


download_data = create_download_data(
    where_clause,
    params
)


st.download_button(
    label="Download filtered data",
    data=download_data,
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