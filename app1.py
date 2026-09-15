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
# COLOR THEME
# ============================================================
# Red-led "alert" palette applied dashboard-wide so every
# chart (bars, lines, pies, the map) shares the same look.

COLOR_SEQUENCE = [
    "#D7263D",  # main red
    "#2E2E38",  # charcoal
    "#F2A65A",  # amber
    "#5C7A99",  # slate blue
    "#8C271E",  # deep brick red
    "#C0C0C0",  # silver grey
    "#E8871E",  # burnt orange
    "#6B4226",  # dark brown
    "#A8A8A8",  # neutral grey
    "#F4D35E",  # warm gold
]

COLOR_CONTINUOUS_SCALE = [
    "#1A1A1D",
    "#4E4E50",
    "#8C271E",
    "#D7263D",
    "#F2A65A",
]

px.defaults.color_discrete_sequence = COLOR_SEQUENCE
px.defaults.color_continuous_scale = COLOR_CONTINUOUS_SCALE


# ============================================================
# DUCKDB CONNECTION
# ============================================================

@st.cache_resource
def get_connection():
    con = duckdb.connect()

    csv_path = str(DATA_PATH).replace("\\", "/").replace("'", "''")

    con.cursor().execute(
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
    return con.cursor().execute(
        """
        SELECT DISTINCT CAST(Year AS INTEGER) AS Year
        FROM crimes
        WHERE Year IS NOT NULL
        ORDER BY Year
        """
    ).df()["Year"].tolist()


@st.cache_data
def get_crime_types():
    return con.cursor().execute(
        """
        SELECT DISTINCT "Primary Type"
        FROM crimes
        WHERE "Primary Type" IS NOT NULL
        ORDER BY "Primary Type"
        """
    ).df()["Primary Type"].tolist()


@st.cache_data
def get_districts():
    return con.cursor().execute(
        """
        SELECT DISTINCT District
        FROM crimes
        WHERE District IS NOT NULL
        ORDER BY District
        """
    ).df()["District"].tolist()


@st.cache_data
def get_locations():
    return con.cursor().execute(
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


kpi_df = con.cursor().execute(
    kpi_query,
    params
).df()

if kpi_df is None or kpi_df.empty:
    kpi = pd.Series({
        "total_crimes": 0,
        "total_arrests": 0,
        "crime_types": 0
    })
else:
    kpi = kpi_df.iloc[0]


total_crimes = int(kpi["total_crimes"])

if pd.isna(kpi["total_arrests"]):
    total_arrests = 0
    no_arrests = True
else:
    total_arrests = int(kpi["total_arrests"])
    no_arrests = False

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

most_common_result = con.cursor().execute(
    most_common_crime_query,
    params
).df()

most_common_crime = (
    most_common_result.iloc[0]["crime"]
    if most_common_result is not None and not most_common_result.empty
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

if no_arrests:
    st.info("No arrests were recorded for the selected filters.")


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

yearly_crimes = con.cursor().execute(
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
        hovermode="x unified",
        yaxis_tickformat=","
    )

    # Force the x-axis to be categorical
    fig.update_xaxes(
        type="category"
    )

    # Show full numbers (no "k" abbreviation) on hover
    fig.update_traces(
        hovertemplate="%{y:,}<extra></extra>"
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

    crime_counts = con.cursor().execute(
        crime_query,
        params
    ).df()

    fig = px.bar(
        crime_counts,
        x="Count",
        y="Crime Type",
        orientation="h",
        title="Top 10 crime types (based on current filters)"
    )

    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis_title="Number of crimes",
        yaxis_title="",
        xaxis_tickformat=","
    )

    fig.update_traces(
        hovertemplate="%{y}<br>%{x:,} crimes<extra></extra>"
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

    location_counts = con.cursor().execute(
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
        yaxis_title="",
        xaxis_tickformat=","
    )

    fig.update_traces(
        hovertemplate="%{y}<br>%{x:,} crimes<extra></extra>"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

# ============================================================
# CRIME TRENDS TABLE
# ============================================================

st.subheader("Crime Trends Table")


crime_categories = (
    selected_crimes
    if selected_crimes
    else [
        "ROBBERY",
        "ASSAULT",
        "BATTERY",
        "BURGLARY",
        "THEFT",
        "MOTOR VEHICLE THEFT",
        "HOMICIDE"
    ]
)


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


table_raw = con.cursor().execute(
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


# ------------------------------------------------------------
# Transpose: rows = metrics (Count / Change per crime type),
# columns = years. Easier to scan year-over-year this way.
# ------------------------------------------------------------

table = table.set_index("Year")
transposed = table.T
transposed.index.name = "Metric"
transposed = transposed.reset_index()

change_row_mask = transposed["Metric"].str.contains(
    "Change From Previous Year"
)


def highlight_row(row):

    if not change_row_mask.loc[row.name]:
        return ["" for _ in row]

    return [
        "" if column == "Metric" else highlight_change(value)
        for column, value in row.items()
    ]


styled_table = transposed.style.apply(
    highlight_row,
    axis=1
)

st.dataframe(
    styled_table,
    width="stretch",
    hide_index=True
)


st.caption(
    "Columns are years, rows show counts and year-over-year percentage "
    "changes per crime category. 2023 is shown without a percentage "
    "change because the dataset starts on January 1, 2023. 2026 is "
    "shown as year-to-date data and is therefore not used for "
    "year-over-year percentage comparisons."
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


arrest_data = con.cursor().execute(
    arrest_query,
    params
).df()


fig = px.pie(
    arrest_data,
    names="Arrest",
    values="Count",
    title="Crimes resulting in an arrest",
    color_discrete_sequence=["#D7263D", "#FF6F91"]
)

fig.update_traces(
    hovertemplate="%{label}<br>%{value:,} crimes (%{percent})<extra></extra>"
)

st.plotly_chart(
    fig,
    width="stretch"
)




# ============================================================
# CRIME INTENSITY: DAY VS HOUR
# ============================================================

st.divider()

st.subheader("Crime Intensity: Day vs Hour")

st.caption(
    "A heatmap of when crimes are reported — darker cells mean more "
    "reported crimes for that day/hour combination, based on the "
    "current filters."
)

intensity_query = f"""
SELECT
    EXTRACT(dow FROM TRY_CAST("Date" AS TIMESTAMP)) AS DayOfWeek,
    EXTRACT(hour FROM TRY_CAST("Date" AS TIMESTAMP)) AS Hour,
    COUNT(*) AS Count
FROM crimes
WHERE {where_clause}
  AND TRY_CAST("Date" AS TIMESTAMP) IS NOT NULL
GROUP BY DayOfWeek, Hour
"""

intensity_data = con.cursor().execute(
    intensity_query,
    params
).df()

if not intensity_data.empty:

    heatmap_day_names = [
        "Sunday", "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday"
    ]

    intensity_pivot = (
        intensity_data
        .pivot(index="DayOfWeek", columns="Hour", values="Count")
        .reindex(index=range(7), columns=range(24), fill_value=0)
    )
    intensity_pivot.index = heatmap_day_names

    fig = px.imshow(
        intensity_pivot,
        labels=dict(x="Hour of day", y="", color="Crimes"),
        aspect="auto",
        title="When do crimes happen most?"
    )

    fig.update_layout(
        coloraxis_colorbar=dict(tickformat=",")
    )

    fig.update_traces(
        hovertemplate="%{y}, %{x}:00<br>%{z:,} crimes<extra></extra>"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:

    st.info(
        "No date data available to compute crime intensity for the "
        "selected filters."
    )


# ============================================================
# TIME PATTERNS
# ============================================================

st.divider()

st.subheader("Time Patterns")

time_query = f"""
SELECT
    EXTRACT(dow FROM TRY_CAST("Date" AS TIMESTAMP)) AS DayOfWeek,
    EXTRACT(hour FROM TRY_CAST("Date" AS TIMESTAMP)) AS Hour,
    COUNT(*) AS Count
FROM crimes
WHERE {where_clause}
  AND TRY_CAST("Date" AS TIMESTAMP) IS NOT NULL
GROUP BY DayOfWeek, Hour
"""

time_data = con.cursor().execute(
    time_query,
    params
).df()

if not time_data.empty:

    day_names = [
        "Sunday", "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday"
    ]

    col1, col2 = st.columns(2)

    with col1:

        by_day = (
            time_data
            .groupby("DayOfWeek")["Count"]
            .sum()
            .reindex(range(7), fill_value=0)
        )
        by_day.index = day_names

        fig = px.bar(
            x=by_day.index,
            y=by_day.values,
            title="Crimes by day of week"
        )

        fig.update_layout(
            xaxis_title="",
            yaxis_title="Number of crimes",
            yaxis_tickformat=","
        )

        fig.update_traces(
            hovertemplate="%{x}<br>%{y:,} crimes<extra></extra>"
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

    with col2:

        by_hour = (
            time_data
            .groupby("Hour")["Count"]
            .sum()
            .reindex(range(24), fill_value=0)
        )

        fig = px.bar(
            x=by_hour.index,
            y=by_hour.values,
            title="Crimes by hour of day"
        )

        fig.update_layout(
            xaxis_title="Hour of day",
            yaxis_title="Number of crimes",
            yaxis_tickformat=","
        )

        fig.update_traces(
            hovertemplate="Hour %{x}<br>%{y:,} crimes<extra></extra>"
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

    domestic_query = f"""
    SELECT
        CASE
            WHEN LOWER(CAST(Domestic AS VARCHAR)) = 'true'
            THEN 'Domestic'
            ELSE 'Non-domestic'
        END AS Domestic,
        COUNT(*) AS Count
    FROM crimes
    WHERE {where_clause}
    GROUP BY Domestic
    """

    domestic_data = con.cursor().execute(
        domestic_query,
        params
    ).df()

    fig = px.pie(
        domestic_data,
        names="Domestic",
        values="Count",
        title="Domestic vs. non-domestic incidents",
        color_discrete_sequence=["#D7263D", "#FF6F91"]
    )

    fig.update_traces(
        hovertemplate="%{label}<br>%{value:,} crimes (%{percent})<extra></extra>"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:

    st.info(
        "No date data available to compute time patterns for the "
        "selected filters."
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


map_df = con.cursor().execute(
    map_query,
    params
).df()


def generate_distinct_map_colors(count):
    """Generate `count` visually distinct, high-contrast hex colors
    (evenly spaced hues, strong saturation) so map points never repeat
    the same color, and still stand out against a light basemap."""

    import colorsys

    colors = []

    for i in range(count):
        hue = i / count
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.85, 0.80)

        colors.append(
            "#{:02X}{:02X}{:02X}".format(
                int(red * 255),
                int(green * 255),
                int(blue * 255)
            )
        )

    return colors


if not map_df.empty:

    sample_size = len(map_df)
    sample_pct = (
        sample_size / total_crimes * 100
        if total_crimes > 0
        else 0
    )

    map_crime_types = map_df["Primary Type"].nunique()
    map_color_sequence = generate_distinct_map_colors(map_crime_types)

    fig = px.scatter_mapbox(
        map_df,
        lat="Latitude",
        lon="Longitude",
        color="Primary Type",
        color_discrete_sequence=map_color_sequence,
        hover_name="Primary Type",
        zoom=9,
        height=600,
        opacity=0.85
    )

    fig.update_traces(
        marker=dict(size=12)
    )

    fig.update_layout(
        mapbox_style="open-street-map",
        margin=dict(l=0, r=0, t=0, b=0),
        legend_title_text="Crime type"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

    st.caption(
        f"The map shows a random sample of {sample_size:,} reported crime "
        f"locations out of {total_crimes:,} matching the current filters "
        f"({sample_pct:.1f}%). Points are colored by crime type — "
        "hover over a point to see its type."
    )

else:

    st.info(
        "No geographic data available for the selected filters."
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


district_data = con.cursor().execute(
    district_query,
    params
).df()

if not district_data.empty:

    district_data["District"] = district_data["District"].astype(str)

    fig = px.treemap(
        district_data,
        path=["District"],
        values="Count",
        color="Count",
        color_continuous_scale=COLOR_CONTINUOUS_SCALE,
        title="Reported crimes by police district"
    )

    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Crimes",
            tickformat=","
        ),
        margin=dict(t=50, l=10, r=10, b=10)
    )

    fig.update_traces(
        hovertemplate="District %{label}<br>%{value:,} crimes<extra></extra>",
        texttemplate="District %{label}<br>%{value:,}"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:

    st.info(
        "No district data available for the selected filters."
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


display_df = con.cursor().execute(
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

    download_df = con.cursor().execute(
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