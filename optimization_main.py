import streamlit as st
from optimization import DHL_Optimization
from optimization_preprocess import preprocess_destination_file, preprocess_source_file, preprocess_trucking_file
import pandas as pd

def main():
    st.title("Dashboard: Optimizing Package Center Deliveries")
    st.header("Select Nodes")

    # File upload for datasets
    default_source_path = "Data Preprocessing/Source_facility_info.xlsx"
    default_destination_path = "Data Preprocessing/Destination_facility_info.xlsx"
    default_trucking_path = "Data Preprocessing/Trucking_info.xlsx"

    source_file = st.file_uploader("Upload source data", type="xlsx")
    destination_file = st.file_uploader("Upload destination data", type="xlsx")
    trucking_file = st.file_uploader("Upload trucking data", type="xlsx")

    if source_file and source_file.name == "2024-04-25_OR Praktikum_RWTH Aachen_WBeh_Aufträge.xlsx":
        source_df, source_success = preprocess_source_file(source_file)
        if not source_success:
            source_df = pd.read_excel(default_source_path)
    else:
        source_df = pd.read_excel(default_source_path)

    if destination_file and destination_file.name == "2024-04-25_OR Praktikum_RWTH Aachen_Inputs.xlsx":
        destination_df, destination_success = preprocess_destination_file(destination_file)
        if not destination_success:
            destination_df = pd.read_excel(default_destination_path)
    else:
        destination_df = pd.read_excel(default_destination_path)

    if trucking_file and trucking_file.name == "2024-04-25_OSRM_Truck_Distanzen+Fahrtzeiten_PZ_x_PZ.xlsx":
        trucking_df, trucking_success = preprocess_trucking_file(trucking_file)
        if not trucking_success:
            trucking_df = pd.read_excel(default_trucking_path)
    else:
        trucking_df = pd.read_excel(default_trucking_path)
        try:
            trucking_df.drop(['Unnamed: 12','Note: OSRM time = pure driving time without breaks, …'], axis=1, inplace=True)
        except Exception:
            pass

    # Initialize the Class
    optimizer = DHL_Optimization()
    
    # Assign the preprocessed dataframes
    optimizer.destination_df = destination_df
    optimizer.source_df = source_df
    optimizer.trucking_df = trucking_df

    optimizer.normalize_shift_times()

    source_nodes = list(optimizer.trucking_df['Origin_ID'].unique())
    destination_nodes = list(optimizer.trucking_df['Destination_ID'].unique())

    selected_sources = st.multiselect("Select up to 8 source nodes", source_nodes, max_selections=8)
    selected_destination = st.selectbox("Select one destination node", destination_nodes, index=None)

    if selected_destination in selected_sources and selected_destination is not None:
        st.warning(f"The selected destination node '{selected_destination}' is already included in the selected source nodes. Please select a different destination.")
    elif selected_destination is None:
        st.warning("Please select a destination node.")
    else:
        st.success(f"The selected destination node '{selected_destination}' is not in the selected source nodes. You can proceed.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Show Destination Info") and selected_destination:
            st.dataframe(optimizer.destination_df[optimizer.destination_df['Destination_ID'].isin([selected_destination])])

    with col2:
        if st.button("Show Source to Destination Routes") and selected_sources:
            st.dataframe(optimizer.trucking_df[optimizer.trucking_df['Origin_ID'].isin(selected_sources) & optimizer.trucking_df['Destination_ID'].isin([selected_destination])])

    if st.button("Show Map") and selected_sources and selected_destination:
        optimizer.show_map(selected_sources, selected_destination)

    if st.button("Run Optimization") and selected_sources and selected_destination:
        st.write("Optimizing ...")
        optimizer.initialize_model(selected_sources, selected_destination)
        optimizer.add_constraints()
        optimizer.solve()
        st.success("Optimization completed. Check the output folder for results.")

if __name__ == "__main__":
    main()
