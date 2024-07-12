import streamlit as st
import pandas as pd
from gurobipy import *
import time
import folium
import streamlit as st
from streamlit_folium import st_folium
import io
import sys

# Assume ColorProfiles is already defined or imported from colors.py
# from colors import ColorProfiles as clr

class DHL_Optimization:
    def __init__(self):
        self.source_df = None
        self.destination_df = None
        self.trucking_df = None
        self.model = Model("DHL_Optimization")
        self.source_list = None
        self.destination_list = None
        self.routes_list = None
        self.consignment_list = None
        self.valid_combinations = None
        self.trucks = range(300)
        self.X = {}
        self.Z = {}
        self.T = {}
        self.ArrivalDay = {}
        self.ArrivalTime = {}
        self.ArrivalDayBinary = {}

    def read_data(self, source_path, destination_path, trucking_path):
        self.source_df = pd.read_excel(source_path, sheet_name="PZA")
        self.destination_df = pd.read_excel(destination_path, sheet_name="PZE")
        self.trucking_df = pd.read_excel(trucking_path, sheet_name="Truck")

    def normalize(self,row):
            start_hour = row['Start of shift'].hour + row['Start of shift'].minute / 60
            end_hour = row['End of lay-on'].hour + row['End of lay-on'].minute / 60
            if end_hour < start_hour:
                end_hour += 24  # normalize end_hour for the next day
            return pd.Series([start_hour, end_hour])

    def normalize_shift_times(self):        
        self.destination_df[['Start of shift', 'End of lay-on']] = self.destination_df.apply(self.normalize, axis=1)
        self.source_df['planned_end_of_loading'] = pd.to_datetime(self.source_df['planned_end_of_loading'])

    def initialize_model(self, selected_sources, selected_destination):
        self.source_list = selected_sources
        self.destination_list = [selected_destination]
        self.routes_list = [(i, j) for i in self.source_list for j in self.destination_list if i != j]
        self.consignment_list = [
            x for (i, j) in self.routes_list
            for x in self.source_df[(self.source_df['Origin_ID'] == i) & (self.source_df['Destination_ID'] == j)]['id'].values
        ]
        
        self.valid_combinations = [
            (i, j, k) for (i, j) in self.routes_list 
            for k in self.consignment_list if k in self.source_df[(self.source_df['Origin_ID'] == i) & (self.source_df['Destination_ID'] == j)]['id'].values
        ]

        self.trucks = range(300)

        for (i, j, k, l) in [(i, j, k, l) for (i, j, k) in self.valid_combinations for l in self.trucks]:
            self.X[(i, j, k, l)] = self.model.addVar(vtype=GRB.BINARY, name=f"X_{i}_{j}_{k}_{l}")

        for l in self.trucks:
            self.Z[l] = self.model.addVar(vtype=GRB.BINARY, name=f"Z_{l}")
            self.T[l] = self.model.addVar(lb=0, vtype=GRB.CONTINUOUS, name=f"T_{l}")
            self.ArrivalTime[l] = self.model.addVar(lb=0, ub=24, vtype=GRB.CONTINUOUS, name=f"ArrivalTime_{l}")
            for d in range(1, 7):  # Maximum number of days to consider
                self.ArrivalDayBinary[(l, d)] = self.model.addVar(vtype=GRB.BINARY, name=f"ArrivalDayBinary_{l}_{d}")
        
        self.model.setObjective(quicksum(self.Z[l]* quicksum(d * self.ArrivalDayBinary[(l, d)] for d in range(1, 7)) for l in self.trucks), GRB.MINIMIZE)

    def add_constraints(self):
        print("Adding constraints to the model...")
        st.write("Adding constraints to the model...")
        time_saved = time.time()

        # 1. Each truck can carry at most 2 consignments
        for l in self.trucks:
            self.model.addConstr(quicksum(self.X[(i, j, k, l)] for (i, j, k) in self.valid_combinations) <= 2 * self.Z[l])
        
        print(f"1st Constraint Model took {time.time() - time_saved} seconds.")
        st.write(f"1st Constraint took {time.time() - time_saved:.2f} seconds.")
        time_saved = time.time()


        # 2. Consignment can only be released after the latest release time of the consignments
        for (i, j, k) in self.valid_combinations:
            release_time = self.source_df[self.source_df['id'] == k]['planned_end_of_loading'].dt.hour.values[0]
            for l in self.trucks:
                self.model.addConstr(self.T[l] >= release_time * self.X[(i, j, k, l)])
        
        print(f"2nd Constraint Model took {time.time() - time_saved} seconds.")
        st.write(f"2nd Constraint took {time.time() - time_saved:.2f} seconds.")
        time_saved = time.time()
        
        # Constraint 3: Truck must arrive at the destination within the operational hours
        for (i, j, k) in self.valid_combinations:
            start_shift = self.destination_df[self.destination_df['Destination_ID'] == j]['Start of shift'].values[0]
            end_shift = self.destination_df[self.destination_df['Destination_ID'] == j]['End of lay-on'].values[0]
            travel_time = self.trucking_df[(self.trucking_df['Origin_ID'] == i) & (self.trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600
            for l in self.trucks:
                self.ArrivalTime[(l)] = (self.T[l] + travel_time * self.X[(i, j, k, l)] + 24 * quicksum((d-1)*self.ArrivalDayBinary[(l, d)] for d in range(1, 7))) - 24 * self.model.addVar(vtype=GRB.INTEGER, name=f"multiplier_{i}_{j}_{k}_{l}")
                self.model.addConstr(self.ArrivalTime[(l)] >= start_shift)
                self.model.addConstr(self.ArrivalTime[(l)] <= end_shift)
        
        print(f"3rd Constraint Model took {time.time() - time_saved} seconds.")
        st.write(f"3rd Constraint took {time.time() - time_saved:.2f} seconds.")
        time_saved = time.time()
        
        # 4. Each consignment must be assigned to exactly one truck
        for (i, j, k) in self.valid_combinations:
            self.model.addConstr(quicksum(self.X[(i, j, k, l)]*self.Z[(l)] for l in self.trucks if (i, j, k) in self.valid_combinations) == 1)
        
        print(f"4th Constraint Model took {time.time() - time_saved} seconds.")
        st.write(f"4th Constraint Model took {time.time() - time_saved:.2f} seconds.")
        time_saved = time.time()
        
        #5.1. Sorting capacity constraint for each truck arriving at a package center
        for j in self.destination_list:
            working_hours = self.destination_df[self.destination_df['Destination_ID'] == j]['End of lay-on'].values[0] - self.destination_df[self.destination_df['Destination_ID'] == j]['Start of shift'].values[0]
            sorting_capacity_per_day =  working_hours/2*self.destination_df[self.destination_df['Destination_ID'] == j]['Sorting capacity'].values[0]
            for d in range(1, 7):
                self.model.addConstr(
                    quicksum(self.X[(i, j, k, l)] * self.source_df[self.source_df['id'] == k]['Consignment quantity'].values[0] * self.ArrivalDayBinary[(l, d)]
                            for i in self.source_list if j != i
                            for k in self.consignment_list
                            for l in self.trucks
                            if (i, j, k) in self.valid_combinations) <= sorting_capacity_per_day,
                    name=f"SortingCapacity_{j}_{d}"
                )

        #5.2. Assigning arrival day to each used truck            
        for l in self.trucks:
            self.model.addConstr(
                quicksum(self.ArrivalDayBinary[(l, d)] * self.Z[l] for d in range(1, 7)) == 1,
                name = f'Assigning Arrival Day to each used truck'
                )
            
        print(f"5th and 6th Constraint Model took {time.time() - time_saved} seconds.")
        st.write(f"5th and 6th Constraint took {time.time() - time_saved:.2f} seconds.")
                
    def solve(self):
        print("Solving the optimization problem...")
        start_time = time.time()
        
        self.model.setParam('TimeLimit', 5*60)

        # Capture the output of model.optimize()
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout

        try:
            self.model.optimize()
            output = new_stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        # Display the captured output in Streamlit
        # def generate_output():
        #     st.write("Optimization Output:")
        #     for line in output.splitlines():
        #         yield line
        #         time.sleep(0.1)  # simulate a delay to mimic real-time output

        # st.write_stream(generate_output)      
        st.write("Optimization Output:")  
        st.text(output)
        # self.model.optimize()
        
        if self.model.status in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL]:
            data = []
            k_set = set()
            for (i, j, k, l) in self.X.keys():
                if (self.Z[l].X == 1 ) and (self.X[i,j,k,l].X == 1):
                    start_shift = self.destination_df[self.destination_df['Destination_ID'] == j]['Start of shift'].values[0]
                    end_shift = self.destination_df[self.destination_df['Destination_ID'] == j]['End of lay-on'].values[0]
                    travel_time = self.trucking_df[(self.trucking_df['Origin_ID'] == i) & (self.trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600
                    arrival = quicksum(d*self.ArrivalDayBinary[(l, d)].X for d in range(1, 7))
                    data.append({
                        'Origin(PZA)': i,
                        'Destination (PZE)': j,
                        'Consignment ID': k,
                        'Truck Id': l,
                        'Departure time': self.T[l].X,
                        'Arrival Day': arrival,
                        "Destination Start Shift": start_shift,
                        "Destination End Shift": end_shift,
                        "Travel Time": travel_time
                    })
            df_out = pd.DataFrame(data)
            df_out.to_csv("output/output.csv")

        else:
            print("No optimal solution found.")
        
        print(f"Optimization completed in {time.time() - start_time} seconds.")
        st.dataframe(df_out) 

    def show_map(self,selected_sources,selected_destination):
        start_loc = (
        self.destination_df[self.destination_df['Destination_ID'] == selected_sources[0]]['PZ_Latitude'].values[0],
        self.destination_df[self.destination_df['Destination_ID'] == selected_sources[0]]['PZ_Longitude'].values[0]
        )
        map_pze = folium.Map(location=start_loc, zoom_start=13)

        routes_list = [(i, selected_destination) for i in selected_sources if i != selected_destination]

        for start, end in routes_list:
            # Marker for the start location
            start_marker = folium.Marker(
                location=(
                    self.destination_df[self.destination_df['Destination_ID'] == start]['PZ_Latitude'].values[0],
                    self.destination_df[self.destination_df['Destination_ID'] == start]['PZ_Longitude'].values[0]
                ),
                tooltip=self.destination_df[self.destination_df['Destination_ID'] == start]['PZ_Sorting_location'].values[0]
            )

            # Marker for the end location
            end_marker = folium.Marker(
                location=(
                    self.destination_df[self.destination_df['Destination_ID'] == end]['PZ_Latitude'].values[0],
                    self.destination_df[self.destination_df['Destination_ID'] == end]['PZ_Longitude'].values[0]
                ),
                tooltip=self.destination_df[self.destination_df['Destination_ID'] == end]['PZ_Sorting_location'].values[0]
            )

            # Get the distance between the start and end locations
            distance = self.trucking_df[(self.trucking_df['Origin_ID'] == start) & (self.trucking_df['Destination_ID'] == end)]['OSRM_distance [m]'].values[0]

            # Line for the route segment connecting start to end
            line = folium.PolyLine(
                locations=[
                    (
                        self.destination_df[self.destination_df['Destination_ID'] == start]['PZ_Latitude'].values[0],
                        self.destination_df[self.destination_df['Destination_ID'] == start]['PZ_Longitude'].values[0]
                    ),
                    (
                        self.destination_df[self.destination_df['Destination_ID'] == end]['PZ_Latitude'].values[0],
                        self.destination_df[self.destination_df['Destination_ID'] == end]['PZ_Longitude'].values[0]
                    )
                ],
                tooltip=f"<b>From</b>: {self.destination_df[self.destination_df['Destination_ID'] == start]['PZ_Sorting_location'].values[0]}<br>"
                        f"<b>To</b>: {self.destination_df[self.destination_df['Destination_ID'] == end]['PZ_Sorting_location'].values[0]}<br>"
                        f"<b>Distance</b>: {distance} m"
            )

            # Add markers and line to the map
            start_marker.add_to(map_pze)
            end_marker.add_to(map_pze)
            line.add_to(map_pze)

        # call to render Folium map in Streamlit    
        st_data = st_folium(map_pze, width=725,returned_objects=[])

def main():
    st.title("Dashboard: Optimizing Package Center Deliveries")
    st.header("Select Nodes")

    # File upload for datasets
    default_source_path = "Source_facility_info.xlsx"
    default_destination_path = "Destination_facility_info.xlsx"
    default_trucking_path = "Trucking_info.xlsx"

    source_file = st.file_uploader("Upload source data", type="xlsx")
    destination_file = st.file_uploader("Upload destination data", type="xlsx")
    trucking_file = st.file_uploader("Upload trucking data", type="xlsx")

    # Read the uploaded files if they exist
    source_path = source_file if source_file is not None else default_source_path
    destination_path = destination_file if destination_file is not None else default_destination_path
    trucking_path = trucking_file if trucking_file is not None else default_trucking_path

    if source_path and destination_path and trucking_path:
        # Initialize the Class
        optimizer = DHL_Optimization()
        
        # Read the datasets
        optimizer.read_data(source_path, destination_path,trucking_path)
        # Normalize shift times
        optimizer.normalize_shift_times()

        source_nodes = list(optimizer.trucking_df['Origin_ID'].unique())
        destination_nodes = list(optimizer.trucking_df['Destination_ID'].unique())

        selected_sources = st.multiselect("Select up to 8 source nodes", source_nodes, max_selections=8)

        selected_destination = st.selectbox("Select one destination node", destination_nodes, index = None)

        # Check if the selected destination is already in the selected sources
        if selected_destination in selected_sources and selected_destination is not None:
             st.warning(f"The selected destination node '{selected_destination}' is already included in the selected source nodes. Please select a different destination.")
        elif selected_destination is None:
            st.warning("Please select a destination node.")
        else:
            st.success(f"The selected destination node '{selected_destination}' is not in the selected source nodes. You can proceed.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Show Destination Info") and selected_destination:
                # Display Destination Dataframe
                st.dataframe(optimizer.destination_df[optimizer.destination_df['Destination_ID'].isin([selected_destination]) ])

        with col2:
            if st.button("Show Source to Destination Routes") and selected_sources:
                # Display routes to Destination Dataframe
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