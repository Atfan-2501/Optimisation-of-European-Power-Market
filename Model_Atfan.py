import pandas as pd
import gurobipy as gp
from gurobipy import GRB

# Reading the data from the excel sheets.
source_df = pd.read_excel("Source_facility_info.xlsx", sheet_name= "PZA")
destination_df = pd.read_excel("Destination_facility_info.xlsx", sheet_name= "PZE")
trucking_df = pd.read_excel("Trucking_info.xlsx", sheet_name= "Truck")

# Convert relevant columns to datetime
def normalize_shift_times(row):
    start_hour = row['Start of shift'].hour + row['Start of shift'].minute / 60
    end_hour = row['End of lay-on'].hour + row['End of lay-on'].minute / 60
    if end_hour < start_hour:
        end_hour += 24  # normalize end_hour for the next day
    return pd.Series([start_hour, end_hour])

destination_df[['Start of shift', 'End of lay-on']] = destination_df.apply(normalize_shift_times, axis=1)
source_df['planned_end_of_loading'] = pd.to_datetime(source_df['planned_end_of_loading'])

# Initialize the model
model = gp.Model("DHL_Optimization")

# Defining variables
source_list = list(trucking_df['Origin_ID'].unique()[:3])  # Index of PZA
destination_list = list(trucking_df['Destination_ID'].unique()[:3])  # Index of PZE
routes_list = [(i, j) for i in source_list for j in destination_list if i != j]
trucks = range(300)

# Decision Variables
X = model.addVars([(i, j, l) for (i, j) in routes_list for l in trucks], vtype=GRB.BINARY, name="X")
Y = model.addVars([(k, l) for k in source_df['id'].unique() for l in trucks], vtype=GRB.BINARY, name="Y")
Z = model.addVars(trucks, vtype=GRB.BINARY, name="Z")
T = model.addVars(trucks, lb=0, vtype=GRB.CONTINUOUS, name="T")
ArrivalDay = model.addVars(trucks, lb=0, vtype=GRB.INTEGER, name="ArrivalDay")

# Objective function: Maximize the (E+1)th day output and minimize the distance
model.setObjective(gp.quicksum(Z[l] for l in trucks) - 0.01 * gp.quicksum(
    (trucking_df[(trucking_df['Origin_ID'] == i) & (trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600) * X[(i, j, l)]
    for (i, j) in routes_list for l in trucks), GRB.MAXIMIZE)

# Constraints
# 1. Each truck can carry at most 2 consignments
model.addConstrs((gp.quicksum(Y[(k, l)] for k in source_df['id']) <= 2 * Z[l] for l in trucks), "TruckCapacity")

# 2. Consignment can only be released after the latest release time of the consignments
for k in source_df['id']:
    release_time = source_df[source_df['id'] == k]['planned_end_of_loading'].dt.hour.values[0]
    model.addConstrs((T[l] >= release_time * Y[(k, l)] for l in trucks), "ReleaseTime")

# 3. Truck must arrive at the destination within the operational hours
for (i, j) in routes_list:
    start_shift = destination_df[destination_df['Destination_ID'] == j]['Start of shift'].values[0]
    end_shift = destination_df[destination_df['Destination_ID'] == j]['End of lay-on'].values[0]
    travel_time = trucking_df[(trucking_df['Origin_ID'] == i) & (trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600
    model.addConstrs((T[l] + travel_time * X[(i, j, l)] >= start_shift for l in trucks), "StartShift")
    model.addConstrs((T[l] + travel_time * X[(i, j, l)] <= end_shift for l in trucks), "EndShift")

# 4. Each consignment must be assigned to exactly one truck
model.addConstrs((gp.quicksum(Y[(k, l)] for l in trucks) == 1 for k in source_df['id']), "ConsignmentAssignment")

# 5. Flow conservation: If a truck leaves a source, it must go to one destination
for l in trucks:
    for i in source_list:
        model.addConstr(gp.quicksum(X[(i, j, l)] for j in destination_list if j not in source_list) == Z[l], name=f"FlowConservation_{i}_{l}")

# Solve the model
model.optimize()

# Print the status of the solution
print('Optimization Status:', model.Status)