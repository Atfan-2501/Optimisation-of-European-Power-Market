import pandas as pd
import streamlit as st

# Function to check and map columns
def check_and_map_columns(df, required_columns, column_mapping):
    # Check for empty first column and first row
    if df.iloc[0].isnull().all() and df.iloc[:, 0].isnull().all():
        df = df.iloc[1:, 1:]
        
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing columns: {', '.join(missing_columns)}. Using default file.")
        return None, False
    else:
        df = df.rename(columns=column_mapping)
        return df, True

def preprocess_destination_file(file_path):
    df = pd.read_excel(file_path, header=1, usecols=lambda x: 'Unnamed' not in x).dropna(axis='rows')
    required_columns = [
        'PZA_GNR', 'PZ_Sortierstandort', 'PZ_Name', 'Schichtbeginn',
        'Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)', 'Sortierleistung [Sdg je h]', 
        'PZ_Latitude', 'PZ_Longitude'
    ]
    column_mapping = {
        'PZA_GNR': 'Destination_ID',
        'PZ_Sortierstandort': 'PZ_Sorting_location',
        'PZ_Name': 'PZ_Name',
        'Schichtbeginn': 'Start of shift',
        'Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)': 'End of lay-on',
        'Sortierleistung [Sdg je h]': 'Sorting capacity',
        'PZ_Latitude': 'PZ_Latitude',
        'PZ_Longitude': 'PZ_Longitude'
    }
    return check_and_map_columns(df, required_columns, column_mapping)

def preprocess_source_file(file_path):
    df = pd.read_excel(file_path)
    required_columns = [
        'quelle_agnr', 'senke_agnr', 'geplantes_beladeende',
        'Sendungsmenge', 'id'
    ]
    column_mapping = {
        'quelle_agnr': 'Origin_ID',
        'senke_agnr': 'Destination_ID',
        'geplantes_beladeende': 'planned_end_of_loading',
        'Sendungsmenge': 'Consignment quantity',
        'id': 'id'
    }
    return check_and_map_columns(df, required_columns, column_mapping)

def preprocess_trucking_file(file_path):
    df = pd.read_excel(file_path)
    required_columns = [
        'Nr', 'Origin_ID', 'Destination_ID',
        'OSRM_distance [m]', 'OSRM_time [sek]'
    ]
    column_mapping = {
        'Nr': 'Nr',
        'Origin_ID': 'Origin_ID',
        'Destination_ID': 'Destination_ID',
        'OSRM_distance [m]': 'OSRM_distance [m]',
        'OSRM_time [sek]': 'OSRM_time [sek]'
    }
    return check_and_map_columns(df, required_columns, column_mapping)