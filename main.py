import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import geopandas as gpd
from shapely.geometry import Point
from geopy.distance import geodesic
import plotly.express as px
import plotly.graph_objects as go
import re

# Set page config
st.set_page_config(
    page_title="Meteorite Landings Explorer",
    page_icon="☄️",
    layout="wide",
    initial_sidebar_state="expanded"
)
def extract_year(val):
    """
    Tente d'extraire une année (4 chiffres) d'un champ hétérogène.
    Retourne np.nan si rien trouvé.
    """
    if pd.isna(val):
        return np.nan
    # Si déjà un int ou float correct (ex: 1998 ou 1998.0)
    if isinstance(val, (int, np.integer)):
        return val
    if isinstance(val, float):
        return int(val) if not np.isnan(val) else np.nan
    # Sinon, chercher 4 chiffres consécutifs
    m = re.search(r"(\d{4})", str(val))
    return int(m.group(1)) if m else np.nan
# Cache data loading
@st.cache_data
def load_data():
    df = pd.read_csv("meteorite-landings.csv")

    # ── Nettoyage coords ─────────────────────────────
    df = df.dropna(subset=["reclat", "reclong"])

    # ── Conversion année → int ───────────────────────
    
    
    



    df["year"] = df["year"].apply(extract_year).astype("Int64")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)

    # ── Nettoyage masse ─────────────────────────────
    df["mass"] = pd.to_numeric(df["mass"], errors="coerce")
    df = df.dropna(subset=["mass"])
    
    # Add size categories and colors for visualization
    def assign_size_and_color(mass):
        if mass < 100:
            return 'Tiny', [255, 255, 0, 160]  # Yellow
        elif mass < 1000:
            return 'Small', [255, 165, 0, 160]  # Orange
        elif mass < 10000:
            return 'Medium', [255, 0, 0, 160]  # Red
        elif mass < 100000:
            return 'Large', [128, 0, 128, 160]  # Purple
        else:
            return 'Huge', [0, 0, 255, 160]  # Blue
    
    # Apply size and color assignment
    size_color_data = df['mass'].apply(assign_size_and_color)
    df['size_category'] = [item[0] for item in size_color_data]
    df['color'] = [item[1] for item in size_color_data]
    
    return df

@st.cache_data
def load_world_boundaries():
    """Load world boundaries for country filtering"""
    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    world = gpd.read_file(url)
    return world

# Your existing filter functions
def filter_by_year_range(df, minimal, maximal):
    return df[(df['year'] >= minimal) & (df['year'] <= maximal)]

def filter_by_country(df, country_name, world):
    country = world.loc[world["NAME"] == country_name]
    if country.empty:
        return df  # Return original df if country not found
    
    country_geom = country.geometry.iloc[0]
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["reclong"], df["reclat"]),
        crs="EPSG:4326"
    )
    filtered = gdf[gdf.geometry.within(country_geom)]
    return filtered.drop(columns="geometry")

def filter_by_class(df, classi):
    return df[df['recclass'] == classi]

def filter_by_mass_range(df, minimal, maximal):
    return df[(df['mass'] >= minimal) & (df['mass'] <= maximal)]

def find_meteorites_in_radius(df, lat, lon, radius_km):
    """Find meteorites within radius of clicked point"""
    meteorites_in_radius = []
    click_point = (lat, lon)
    
    for idx, row in df.iterrows():
        meteorite_point = (row['reclat'], row['reclong'])
        distance = geodesic(click_point, meteorite_point).kilometers
        if distance <= radius_km:
            meteorites_in_radius.append({
                'distance': distance,
                **row.to_dict()
            })
    
    return pd.DataFrame(meteorites_in_radius).sort_values('distance') if meteorites_in_radius else pd.DataFrame()

def main():
    st.title("☄️ Meteorite Landings Explorer")
    st.markdown("Explore meteorite landings around the world with interactive filtering and mapping")
   
    # Load data
    with st.spinner("Loading meteorite data..."):
        df = load_data()
        world = load_world_boundaries()
    
    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    
    # Year filter
    st.sidebar.subheader("Year Range")
    year_min, year_max = int(df['year'].min()), int(df['year'].max())
    
    # Handle case where all years are the same
    if year_min == year_max:
        st.sidebar.info(f"All meteorites are from year: {year_min}")
        year_range = (year_min, year_max)
    else:
        year_range = st.sidebar.slider(
            "Select year range:",
            min_value=year_min,
            max_value=year_max,
            value=(year_min, year_max),
            step=1
        )
    
    # Country filter
    st.sidebar.subheader("Country")
    countries = ['All Countries'] + sorted(world['NAME'].unique().tolist())
    selected_country = st.sidebar.selectbox("Select country:", countries)
    
    # Class filter
    st.sidebar.subheader("Meteorite Class")
    classes = ['All Classes'] + sorted(df['recclass'].dropna().unique().tolist())
    selected_class = st.sidebar.selectbox("Select meteorite class:", classes)
    
    # Mass filter
    st.sidebar.subheader("Mass Range (grams)")
    mass_min, mass_max = float(df['mass'].min()), float(df['mass'].max())
    
    # Handle case where all masses are the same
    if mass_min == mass_max:
        st.sidebar.info(f"All meteorites have mass: {mass_min}g")
        mass_range = (mass_min, mass_max)
    else:
        # Cap max value for better UX
        display_max = min(mass_max, 100000)
        mass_min_int = int(mass_min)
        display_max_int = int(display_max)
        mass_range = st.sidebar.slider(
        "Select mass range:",
        min_value=mass_min_int,
        max_value=display_max_int,
        value=(mass_min_int, min(display_max_int, 10000)),
        step=100
      )
       
    
    # Search radius configuration
    st.sidebar.subheader("Click Search Settings")
    search_radius = st.sidebar.number_input(
        "Search radius (km):",
        min_value=1,
        max_value=500,
        value=50,
        step=5
    )
    
    # Apply filters
    filtered_df = df.copy()
    
    # Apply year filter
    filtered_df = filter_by_year_range(filtered_df, year_range[0], 2005)
    
    # Apply country filter
    if selected_country != 'All Countries':
        filtered_df = filter_by_country(filtered_df, selected_country, world)
    
    # Apply class filter
    if selected_class != 'All Classes':
        filtered_df = filter_by_class(filtered_df, selected_class)
    
    # Apply mass filter
    filtered_df = filter_by_mass_range(filtered_df, mass_range[0], mass_range[1])
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("🗺️ Interactive Meteorite Map")
        st.markdown("Click on the map to find meteorites within your specified radius")
        
        # Create PyDeck map
        if not filtered_df.empty:
            # Calculate size based on mass for visualization
            filtered_df['size'] = np.clip(np.log10(filtered_df['mass'] + 1) * 20, 10, 100)
            
            # PyDeck scatter plot layer
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=filtered_df,
                get_position=["reclong", "reclat"],
                get_color="color",
                get_radius="size",
                pickable=True,
                auto_highlight=True,
                radius_min_pixels=3,
                radius_max_pixels=20,
            )
            
            # Set initial view
            view_state = pdk.ViewState(
                latitude=filtered_df['reclat'].mean(),
                longitude=filtered_df['reclong'].mean(),
                zoom=2,
                pitch=0
            )
            
            # Create deck
            deck = pdk.Deck(
                map_style='mapbox://styles/mapbox/light-v9',
                initial_view_state=view_state,
                layers=[scatter_layer],
                tooltip={
                    "html": "<b>{name}</b><br/>Class: {recclass}<br/>Mass: {mass}g<br/>Year: {year}<br/>Location: ({reclat}, {reclong})",
                    "style": {"backgroundColor": "steelblue", "color": "white"}
                }
            )
            
            # Display map and capture clicks
            map_data = st.pydeck_chart(deck, use_container_width=True)
            
        else:
            st.warning("No meteorites match the current filter criteria.")
    
    with col2:
        st.subheader("📊 Summary Statistics")
        
        if not filtered_df.empty:
            st.metric("Total Meteorites", len(filtered_df))
            st.metric("Average Mass", f"{filtered_df['mass'].mean():.1f}g")
            st.metric("Largest Meteorite", f"{filtered_df['mass'].max():.1f}g")
            st.metric("Year Range", f"{filtered_df['year'].min()} - {filtered_df['year'].max()}")
            
            # Size distribution chart
            st.subheader("Size Distribution")
            size_counts = filtered_df['size_category'].value_counts()
            fig_pie = px.pie(
                values=size_counts.values,
                names=size_counts.index,
                title="Meteorites by Size Category"
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
            
        else:
            st.info("Apply filters to see statistics")
    
    # Click interaction section
    st.subheader("🎯 Click Search Results")
    
    # Manual coordinate input as alternative to clicking
    coord_col1, coord_col2, coord_col3 = st.columns(3)
    with coord_col1:
        search_lat = st.number_input("Latitude:", value=0.0, step=0.1, format="%.6f")
    with coord_col2:
        search_lon = st.number_input("Longitude:", value=0.0, step=0.1, format="%.6f")
    with coord_col3:
        if st.button("Search Location"):
            st.session_state.search_coords = (search_lat, search_lon)
    
    # Display search results
    if hasattr(st.session_state, 'search_coords') and st.session_state.search_coords:
        lat, lon = st.session_state.search_coords
        nearby_meteorites = find_meteorites_in_radius(filtered_df, lat, lon, search_radius)
        
        if not nearby_meteorites.empty:
            st.success(f"Found {len(nearby_meteorites)} meteorites within {search_radius}km of ({lat:.4f}, {lon:.4f})")
            
            # Display results table
            display_cols = ['name', 'recclass', 'mass', 'year', 'fall', 'distance']
            st.dataframe(
                nearby_meteorites[display_cols].round({'distance': 2, 'mass': 1}),
                use_container_width=True
            )
            
            # Detailed view for selected meteorite
            if not nearby_meteorites.empty:
                st.subheader("🔍 Meteorite Details")
                selected_idx = st.selectbox(
                    "Select a meteorite for detailed view:",
                    range(len(nearby_meteorites)),
                    format_func=lambda x: f"{nearby_meteorites.iloc[x]['name']} ({nearby_meteorites.iloc[x]['distance']:.1f}km away)"
                )
                
                selected_meteorite = nearby_meteorites.iloc[selected_idx]
                
                detail_col1, detail_col2 = st.columns(2)
                with detail_col1:
                    st.info(f"**Name:** {selected_meteorite['name']}")
                    st.info(f"**Class:** {selected_meteorite['recclass']}")
                    st.info(f"**Mass:** {selected_meteorite['mass']:.1f} grams")
                    st.info(f"**Year:** {int(selected_meteorite['year'])}")
                
                with detail_col2:
                    st.info(f"**Fall/Found:** {selected_meteorite['fall']}")
                    st.info(f"**Latitude:** {selected_meteorite['reclat']:.6f}")
                    st.info(f"**Longitude:** {selected_meteorite['reclong']:.6f}")
                    st.info(f"**Distance:** {selected_meteorite['distance']:.2f} km")
        
        else:
            st.warning(f"No meteorites found within {search_radius}km of ({lat:.4f}, {lon:.4f})")
    
    # Dataset info
    with st.expander("ℹ️ Dataset Information"):
        st.markdown("""
        **Dataset:** Meteorite Landings from NASA's Open Data Portal
        
        **Columns:**
        - **name**: Meteorite name
        - **recclass**: Meteorite classification
        - **mass**: Mass in grams
        - **fall**: Whether the meteorite was seen falling or found later
        - **year**: Year of fall/discovery
        - **reclat/reclong**: Coordinates where meteorite was recovered
        
        **Size Categories:**
        - 🟡 Tiny: < 100g
        - 🟠 Small: 100g - 1kg  
        - 🔴 Medium: 1kg - 10kg
        - 🟣 Large: 10kg - 100kg
        - 🔵 Huge: > 100kg
        """)

if __name__ == "__main__":
    main()