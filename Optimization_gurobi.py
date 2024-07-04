import pandas as pd
from gurobipy import *

class DHL_Optimization:
    """
    A class to represent the DHL Optimization problem.

    Attributes:
        source_df (pd.DataFrame): DataFrame containing source facility information.
        destination_df (pd.DataFrame): DataFrame containing destination facility information.
        trucking_df (pd.DataFrame): DataFrame containing trucking information.
        model (gurobipy.Model): Gurobi optimization model.
        source_list (list): List of unique source facility IDs.
        destination_list (list): List of unique destination facility IDs.
        routes_list (list): List of possible routes between source and destination facilities.
        consignment_list (list): List of consignment IDs.
        valid_combinations (list): List of valid combinations of routes and consignments.
        trucks (range): Range of truck indices.
        X (dict): Decision variables for consignment assignment to trucks.
        Z (dict): Decision variables for truck usage.
        T (dict): Decision variables for truck release times.
        ArrivalDay (dict): Decision variables for truck arrival days.
        ArrivalTime (dict): Decision variables for truck arrival times.
    """

    def __init__(self):
        """
        Initializes the DHL_Optimization class with default values.
        """
        self.source_df = None
        self.destination_df = None
        self.trucking_df = None
        self.model = Model("DHL_Optimization")
        self.source_list = None
        self.destination_list = None
        self.routes_list = None
        self.consignment_list = None
        self.valid_combinations = None
        self.trucks = range(100)
        self.X = {}
        self.Z = {}
        self.T = {}
        self.ArrivalDay = {}
        self.ArrivalTime = {}

    def read_data(self, source_path="Source_facility_info.xlsx", destination_path="Destination_facility_info.xlsx", trucking_path="Trucking_info.xlsx"):
        """
        Reads data from Excel sheets into pandas DataFrames.

        Args:
            source_path (str): Path to the source facility information Excel file.
            destination_path (str): Path to the destination facility information Excel file.
            trucking_path (str): Path to the trucking information Excel file.
        """
        self.source_df = pd.read_excel(source_path, sheet_name="PZA")
        self.destination_df = pd.read_excel(destination_path, sheet_name="PZE")
        self.trucking_df = pd.read_excel(trucking_path, sheet_name="Truck")
        self.source_df['planned_end_of_loading'] = pd.to_datetime(self.source_df['planned_end_of_loading'])

    def normalize_shift_times(self):
        """
        Normalizes the shift times in the destination DataFrame to ensure that end times after midnight are handled correctly.
        """
        def normalize(row):
            start_hour = row['Start of shift'].hour + row['Start of shift'].minute / 60
            end_hour = row['End of lay-on'].hour + row['End of lay-on'].minute / 60
            if end_hour < start_hour:
                end_hour += 24  # normalize end_hour for the next day
            return pd.Series([start_hour, end_hour])
        
        self.destination_df[['Start of shift', 'End of lay-on']] = self.destination_df.apply(normalize, axis=1)

    def initialize_model(self):
        """
        Initializes the Gurobi model with decision variables and objective function.
        """
        self.source_list = list(self.trucking_df['Origin_ID'].unique()[:2])  # Index of PZA
        self.destination_list = list(self.trucking_df['Destination_ID'].unique()[:2])  # Index of PZE
        self.routes_list = [(i, j) for i in self.source_list for j in self.destination_list if i != j]
        self.consignment_list = [
            x for (i, j) in self.routes_list
            for x in self.source_df[(self.source_df['Origin_ID'] == i) & (self.source_df['Destination_ID'] == j)]['id'].values
        ]
        self.valid_combinations = [
            (i, j, k) for (i, j) in self.routes_list
            for k in self.consignment_list if k in self.source_df[(self.source_df['Origin_ID'] == i) & (self.source_df['Destination_ID'] == j)]['id'].values
        ]

        for (i, j, k, l) in [(i, j, k, l) for (i, j, k) in self.valid_combinations for l in self.trucks]:
            self.X[(i, j, k, l)] = self.model.addVar(vtype=GRB.BINARY, name=f"X_{i}_{j}_{k}_{l}")
            self.ArrivalTime[(i, j, k, l)] = self.model.addVar(lb=0, ub=24, vtype=GRB.CONTINUOUS, name=f"ArrivalTime_{i}_{j}_{k}_{l}")

        for l in self.trucks:
            self.Z[l] = self.model.addVar(vtype=GRB.BINARY, name=f"Z_{l}")
            self.T[l] = self.model.addVar(lb=0, vtype=GRB.CONTINUOUS, name=f"T_{l}")
            self.ArrivalDay[l] = self.model.addVar(vtype=GRB.INTEGER, name=f"ArrivalDay_{l}")

        self.model.setObjective(quicksum(self.ArrivalDay[l] for l in self.trucks), GRB.MINIMIZE)

    def add_constraints(self):
        """
        Adds constraints to the Gurobi model to ensure the solution is feasible.
        """
        # Constraint 1: Each truck can carry at most 2 consignments
        for l in self.trucks:
            self.model.addConstr(quicksum(self.X[(i, j, k, l)] for (i, j, k) in self.valid_combinations) <= 2 * self.Z[l])
        
        # Constraint 2: Consignment can only be released after the latest release time of the consignments
        for (i, j, k) in self.valid_combinations:
            release_time = self.source_df[self.source_df['id'] == k]['planned_end_of_loading'].dt.hour.values[0]  # Convert to hours
            for l in self.trucks:
                self.model.addConstr(self.T[l] >= release_time * self.X[(i, j, k, l)])
        
        # Constraint 3: Truck must arrive at the destination within the operational hours
        for (i, j, k) in self.valid_combinations:
            start_shift = self.destination_df[self.destination_df['Destination_ID'] == j]['Start of shift'].values[0]
            end_shift = self.destination_df[self.destination_df['Destination_ID'] == j]['End of lay-on'].values[0]
            travel_time = self.trucking_df[(self.trucking_df['Origin_ID'] == i) & (self.trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600  # Convert to hours
            for l in self.trucks:
                arrival_time_var = self.ArrivalTime[(i, j, k, l)]
                self.model.addConstr(arrival_time_var == (self.T[l] + travel_time * self.X[(i, j, k, l)] + 24 * self.ArrivalDay[l]) - 24 * self.model.addVar(vtype=GRB.INTEGER, name=f"multiplier_{i}_{j}_{k}_{l}"))
                self.model.addConstr(arrival_time_var >= start_shift)
                self.model.addConstr(arrival_time_var <= end_shift)
        
        # Constraint 4: Each consignment must be assigned to exactly one truck
        for k in self.consignment_list:
            self.model.addConstr(quicksum(self.X[(i, j, k, l)] for (i, j) in self.routes_list for l in self.trucks if (i, j, k) in self.valid_combinations) == 1)
        
        # Constraint 5: Flow conservation - If a truck leaves a source, it must go to one destination
        for l in self.trucks:
            for i in self.source_list:
                self.model.addConstr(quicksum(self.X[(i, j, k, l)] for j in self.destination_list if j != i for k in self.consignment_list if (i, j, k) in self.valid_combinations) >= self.Z[l])
        
        # Constraint 6: Sorting Capacity - Each PZE should have enough capacity to accommodate all the incoming trucks
        for j in self.destination_list:
            working_hours = self.destination_df[self.destination_df['Destination_ID'] == j]['End of lay-on'].values[0] - self.destination_df[self.destination_df['Destination_ID'] == j]['Start of shift'].values[0]
            self.model.addConstr(quicksum(self.X[(i, j, k, l)] * self.source_df[self.source_df['id'] == k]['Consignment quantity'].values[0]
                            for i in self.source_list if j != i for k in self.consignment_list for l in self.trucks if (i, j, k) in self.valid_combinations) <= working_hours * self.destination_df[self.destination_df['Destination_ID'] == j]['Sorting capacity'].values[0])

    def solve(self):
        """
        Solves the optimization model and prints the solution.
        """
        self.model.optimize()
        if self.model.status == GRB.OPTIMAL:
            print("Optimal solution found.")
            print(f"Objective value: {self.model.objVal}")
            solution = {}
            for v in self.model.getVars():
                if v.x > 0:
                    solution[v.varName] = v.x
            print("Solution:", solution)
        else:
            print("No optimal solution found.")

def main():
    """
    The main function to create an instance of DHL_Optimization, read data, normalize shift times,
    initialize the model, add constraints, and solve the optimization problem.
    """
    optimizer = DHL_Optimization()
    optimizer.read_data()
    optimizer.normalize_shift_times()
    optimizer.initialize_model()
    optimizer.add_constraints()
    optimizer.solve()

if __name__ == "__main__":
    main()