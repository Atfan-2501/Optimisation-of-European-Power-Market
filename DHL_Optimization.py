import pandas as pd
import pulp as lp
from pulp import *
# Reading the data from the excel sheets.
source_df = pd.read_excel("Source_facility_info.xlsx", sheet_name= "PZA")
destination_df = pd.read_excel("Destination_facility_info.xlsx", sheet_name= "PZE")
trucking_df = pd.read_excel("Trucking_info.xlsx", sheet_name= "Truck")

# Convert relevant columns to datetime# Convert start_shift and end_shift to numerical hours and normalize end_shift to handle the next day
def normalize_shift_times(row):
    start_hour = row['Start of shift'].hour + row['Start of shift'].minute / 60
    end_hour = row['End of lay-on'].hour + row['End of lay-on'].minute / 60
    if end_hour < start_hour:
        end_hour += 24  # normalize end_hour for the next day
    return pd.Series([start_hour, end_hour])

destination_df[['Start of shift', 'End of lay-on']] = destination_df.apply(normalize_shift_times, axis=1)
source_df['planned_end_of_loading'] = pd.to_datetime(source_df['planned_end_of_loading'])
# Initialize the model
model = lp.LpProblem("DHL_Optimization", lp.LpMaximize)

# Defining variables
source_list = list(trucking_df['Origin_ID'].unique()[:3])  # Index of PZA
destination_list = list(trucking_df['Destination_ID'].unique()[:3])  # Index of PZE
routes_list = [(i, j) for i in source_list for j in destination_list if i != j]
trucks = range(300)

# Decision Variables
# X - Whether a truck goes from I to J
X = lp.LpVariable.dicts("X", [(i, j, l) for (i, j) in routes_list for l in trucks], cat='Binary')
# Y - Consignment K being carried by K or not
Y = lp.LpVariable.dicts("Y", [(k, l) for k in source_df['id'].unique() for l in trucks], cat='Binary')
# Z - From a pool of Trucks, whether a truck is used or not
Z = lp.LpVariable.dicts("Z", trucks, cat='Binary')

# T - Time of departure of a given truck
T = lp.LpVariable.dicts("T", trucks, lowBound=0, cat='Integer')

ArrivalDay = lp.LpVariable.dicts("ArrivalDay", trucks, lowBound=0, cat='Integer')  # 0 for same day, 1 for next day, etc.
# Combining the objective function: Maximizing the (E+1)th day output and minimizing the distance
model += lp.lpSum(Z[l] for l in trucks) - 0.01 * lp.lpSum([
    (trucking_df[(trucking_df['Origin_ID'] == i) & (trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] /3600) * X[(i, j, l)]
    for (i, j) in routes_list for l in trucks
])
# Constraints
# 1. Each truck can carry at most 2 consignments
for l in trucks:
    model += lp.lpSum([Y[(k, l)] for k in source_df['id']]) <= 2 * Z[l]
# 2. Consignment can only be released after the latest release time of the consignments
for k in source_df['id']:
    release_time = source_df[source_df['id'] == k]['planned_end_of_loading'].dt.hour  # Convert to hours
    for l in trucks:
        model += T[l] >= release_time * Y[(k, l)]
# 3. Truck must arrive at the destination within the operational hours

for (i, j) in routes_list:
    start_shift = destination_df[destination_df['Destination_ID'] == j]['Start of shift'].values[0]
    end_shift = destination_df[destination_df['Destination_ID'] == j]['End of lay-on'].values[0]
    travel_time = trucking_df[(trucking_df['Origin_ID'] == i) & (trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600  # Convert to hours
    for l in trucks:
        model += T[l] + travel_time * X[(i, j, l)]  >= start_shift # Account for day shift
        model += T[l] + travel_time * X[(i, j, l)]  <= end_shift  # Account for end of shift
# 4. Each consignment must be assigned to exactly one truck
for k in source_df['id']:
    model += lp.lpSum([Y[(k, l)] for l in trucks]) == 1
# 5. Flow conservation: If a truck leaves a source, it must go to one destination
for l in trucks:
    for i in source_list:
        model += lp.lpSum([X[(i, j, l)] for j in destination_list if j not in source_list]) == Z[l]
# Solve the model
model.solve()
pulp.LpStatus
