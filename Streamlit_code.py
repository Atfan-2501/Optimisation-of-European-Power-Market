import streamlit as st
import pandas as pd
from gurobipy import *
import time

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
        self.source_df = pd.read_excel(source_path, sheet_name="ta_auftrage_awb_202404251124")
        self.destination_df = pd.read_excel(destination_path, header=1, usecols=lambda x: 'Unnamed' not in x, sheet_name="PZ").dropna(axis='rows')
        self.trucking_df = pd.read_excel(trucking_path, sheet_name="OSRM_Truck")
        self.source_df['geplantes_beladeende'] = pd.to_datetime(self.source_df['geplantes_beladeende'])

    def normalize_shift_times(self):
        def normalize(row):
            start_hour = row['Schichtbeginn'].hour + row['Schichtbeginn'].minute / 60
            end_hour = row['Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)'].hour + row['Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)'].minute / 60
            if end_hour < start_hour:
                end_hour += 24  # normalize end_hour for the next day
            return pd.Series([start_hour, end_hour])
        
        self.destination_df[['Schichtbeginn', 'Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)']] = self.destination_df.apply(normalize, axis=1)

    def initialize_model(self, selected_sources, selected_destination):
        self.source_list = selected_sources
        self.destination_list = [selected_destination]
        self.routes_list = [(i, j) for i in self.source_list for j in self.destination_list if i != j]
        self.consignment_list = [
            x for (i, j) in self.routes_list
            for x in self.source_df[(self.source_df['quelle_agnr'] == i) & (self.source_df['senke_agnr'] == j)]['id'].values
        ]
        
        self.valid_combinations = [
            (i, j, k) for (i, j) in self.routes_list 
            for k in self.consignment_list if k in self.source_df[(self.source_df['quelle_agnr'] == i) & (self.source_df['senke_agnr'] == j)]['id'].values
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
        time_saved = time.time()
        
        for l in self.trucks:
            self.model.addConstr(quicksum(self.X[(i, j, k, l)] for (i, j, k) in self.valid_combinations) <= 2 * self.Z[l])
        
        print(f"1st Constraint Model took {time.time() - time_saved} seconds.")
        time_saved = time.time()
        
        for (i, j, k) in self.valid_combinations:
            release_time = self.source_df[self.source_df['id'] == k]['geplantes_beladeende'].dt.hour.values[0]
            for l in self.trucks:
                self.model.addConstr(self.T[l] >= release_time * self.X[(i, j, k, l)])
        
        print(f"2nd Constraint Model took {time.time() - time_saved} seconds.")
        time_saved = time.time()
        
        for (i, j, k) in self.valid_combinations:
            start_shift = self.destination_df[self.destination_df['PZA_GNR'] == j]['Schichtbeginn'].values[0]
            end_shift = self.destination_df[self.destination_df['PZA_GNR'] == j]['Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)'].values[0]
            travel_time = self.trucking_df[(self.trucking_df['Origin_ID'] == i) & (self.trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600
            for l in self.trucks:
                self.ArrivalTime[(l)] = (self.T[l] + travel_time * self.X[(i, j, k, l)] + 24 * quicksum((d-1)*self.ArrivalDayBinary[(l, d)] for d in range(1, 7))) - 24 * self.model.addVar(vtype=GRB.INTEGER, name=f"multiplier_{i}_{j}_{k}_{l}")
                self.model.addConstr(self.ArrivalTime[(l)] >= start_shift)
                self.model.addConstr(self.ArrivalTime[(l)] <= end_shift)
        
        print(f"3rd Constraint Model took {time.time() - time_saved} seconds.")
        time_saved = time.time()
        
        for (i, j, k) in self.valid_combinations:
            self.model.addConstr(quicksum(self.X[(i, j, k, l)] for l in self.trucks if (i, j, k) in self.valid_combinations) == 1)
        
        print(f"4th Constraint Model took {time.time() - time_saved} seconds.")
        time_saved = time.time()
        
        for j in self.destination_list:
            working_hours = self.destination_df[self.destination_df['PZA_GNR'] == j]['Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)'].values[0] - self.destination_df[self.destination_df['PZA_GNR'] == j]['Schichtbeginn'].values[0]
            sorting_capacity_per_day =  working_hours/2*self.destination_df[self.destination_df['PZA_GNR'] == j]['Sortierleistung [Sdg je h]'].values[0]
            for d in range(1, 7):
                self.model.addConstr(
                    quicksum(self.X[(i, j, k, l)] * self.source_df[self.source_df['id'] == k]['Sendungsmenge'].values[0] * self.ArrivalDayBinary[(l, d)]
                            for i in self.source_list if j != i
                            for k in self.consignment_list
                            for l in self.trucks
                            if (i, j, k) in self.valid_combinations) <= sorting_capacity_per_day,
                    name=f"SortingCapacity_{j}_{d}"
                )
                    
        for l in self.trucks:
            self.model.addConstr(
                quicksum(self.ArrivalDayBinary[(l, d)] * self.Z[l] for d in range(1, 7)) == 1,
                name = f'Assigning Arrival Day to each used truck'
                )
            
        print(f"5th Constraint Model took {time.time() - time_saved} seconds.")
                
    def solve(self):
        print("Solving the optimization problem...")
        start_time = time.time()
        
        self.model.setParam('TimeLimit', 5*60)
        self.model.optimize()
        
        if self.model.status in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL]:
            data = []
            k_set = set()
            for (i, j, k, l) in self.X.keys():
                if (self.Z[l].X == 1 ) and (self.X[i,j,k,l].X == 1):
                    start_shift = self.destination_df[self.destination_df['PZA_GNR'] == j]['Schichtbeginn'].values[0]
                    end_shift = self.destination_df[self.destination_df['PZA_GNR'] == j]['Auflegeende (=Sortierschluss/ PZE Sorter Cutoff)'].values[0]
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
            pd.DataFrame(data).to_csv("output/output.csv")
        else:
            print("No optimal solution found.")
        
        print(f"Optimization completed in {time.time() - start_time} seconds.")

def main():
    st.title("Welcome to Optimizing Package Center Operations Insight")
    st.header("Select Nodes")

    # File upload for datasets
    source_file = st.file_uploader("Upload source data", type="xlsx")
    destination_file = st.file_uploader("Upload destination data", type="xlsx")
    trucking_file = st.file_uploader("Upload trucking data", type="xlsx")

    if source_file and destination_file and trucking_file:
        optimizer = DHL_Optimization()
        optimizer.read_data(source_file, destination_file, trucking_file)
        optimizer.normalize_shift_times()

        source_nodes = list(optimizer.trucking_df['Origin_ID'].unique())
        destination_nodes = list(optimizer.trucking_df['Destination_ID'].unique())

        selected_sources = st.multiselect("Select up to 8 source nodes", source_nodes, max_selections=8)
        selected_destination = st.selectbox("Select one destination node", destination_nodes)

        if st.button("Run Optimization") and selected_sources and selected_destination:
            optimizer.initialize_model(selected_sources, selected_destination)
            optimizer.add_constraints()
            optimizer.solve()
            st.success("Optimization completed. Check the output folder for results.")

if __name__ == "__main__":
    main()