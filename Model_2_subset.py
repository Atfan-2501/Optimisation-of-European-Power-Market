import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import os
from datetime import datetime, timedelta
from itertools import islice

# Get the current working directory
cwd = os.getcwd()

# Load the Excel files
excel_1_path = os.path.join("Dataset", 'Inputs.xlsx')
excel_2_path = os.path.join("Dataset", 'Consignment.xlsx')
excel_3_path = os.path.join("Dataset", 'Distance.xlsx')

# Read the Excel files
df1 = pd.read_excel(excel_1_path)
df2 = pd.read_excel(excel_2_path)
df3 = pd.read_excel(excel_3_path)

# Extract the parameters
PZA = df3['Origin_ID'].tolist()[:10]  # Limiting the size
PZE = df3['Destination_ID'].tolist()[:10]  # Limiting the size
d = {(row['Origin_ID'], row['Destination_ID']): row['OSRM_distance [m]'] for idx, row in df3.iterrows() if row['Origin_ID'] in PZA and row['Destination_ID'] in PZE}
T = {(row['Origin_ID'], row['Destination_ID']): row['OSRM_time [sek]'] for idx, row in df3.iterrows() if row['Origin_ID'] in PZA and row['Destination_ID'] in PZE}
SC = {row['PZ_AGNR']: row['Sortierleistung [Sdg je h]'] for idx, row in df1.iterrows() if row['PZ_AGNR'] in PZA}
DG = {row['PZ_AGNR']: row['Anzahl Entladebänder (Tore)'] for idx, row in df1.iterrows() if row['PZ_AGNR'] in PZE}
UC = {row['PZ_AGNR']: row['Entladeleistung je Entladeband (Tor) je Stunde'] for idx, row in df1.iterrows() if row['PZ_AGNR'] in PZE}
Q = {row['id']: row['Sendungsmenge'] for idx, row in islice(df2.iterrows(), 5)}  # Limiting the size
SD = {row['id']: pd.to_datetime(row['geplantes_beladeende']) for idx, row in islice(df2.iterrows(), 5)}  # Limiting the size

# Assign a random big number for Deadline, making it start date + 1 day
Deadline = {row['id']: pd.to_datetime(row['geplantes_beladeende']) + timedelta(days=1) for idx, row in islice(df2.iterrows(), 10)}  # Limiting the size

LT = 10 * 60  # Loading/Unloading time (seconds)
ET = 10 * 60  # Entry/Exit time (seconds)
ST = 5 * 60  # Swapping time (seconds)
UDT = 30 * 60  # Unloading time delay (seconds)
Shift_Hours = 11 * 3600  # Duration of the shift in seconds

# Create the model
model = gp.Model("ParcelCenterOptimization")

# Ensure unique pairs of (PZA, PZE)
unique_pairs = set(zip(PZA, PZE))

# Define the decision variables
x = model.addVars(unique_pairs, vtype=GRB.BINARY, name="x")
y = model.addVars(unique_pairs, vtype=GRB.INTEGER, name="y")

# Define the constraints

# Sorting Capacity
for i in PZA:
    if i in SC:
        model.addConstr(gp.quicksum(y[i, j] for j in PZE if (i, j) in unique_pairs) <= SC.get(i, 0) * Shift_Hours, name=f"SortingCapacity_{i}")
    else:
        print(f"Warning: SC does not contain key {i}")

# Unloading Capacity
for j in PZE:
    if j in UC and j in DG:
        model.addConstr(gp.quicksum(y[i, j] for i in PZA if (i, j) in unique_pairs) <= UC.get(j, 0) * DG.get(j, 0) * Shift_Hours, name=f"UnloadingCapacity_{j}")
    else:
        print(f"Warning: UC or DG does not contain key {j}")

# Truck Capacity
for i, j in unique_pairs:
    model.addConstr(y[i, j] <= 2 * x[i, j], name=f"TruckCapacity_{i}_{j}")

# Time Constraints
for i, j in unique_pairs:
    for id_ in Q:
        if i in SC:
            model.addConstr(T[i, j] + (y[i, j] / SC.get(i, 1)) + LT <= (Deadline[id_] - SD[id_]).total_seconds(), name=f"TimeConstraint_{i}_{j}")

# Flow Conservation
for j in PZE:
    model.addConstr(gp.quicksum(y[i, j] for i in PZA if (i, j) in unique_pairs) == Q.get(j, 0), name=f"FlowConservationOut_{j}")

for i in PZA:
    model.addConstr(gp.quicksum(y[i, j] for j in PZE if (i, j) in unique_pairs) == Q.get(i, 0), name=f"FlowConservationIn_{i}")

# Example of adding an objective function
model.setObjective(gp.quicksum(x[i, j] * T[i, j] for i, j in unique_pairs), GRB.MINIMIZE)

# Optimize the model
model.optimize()

# Print the results
if model.status == GRB.OPTIMAL:
    print("Optimal solution found")
    for i in PZA:
        for j in PZE:
            if x[i,j].x > 0.5:
                print(f"Route from {i} to {j} with {y[i,j].x} swap bodies")
else:
    print("No optimal solution found")