### DHL Optimization
This project implements an optimization solution for the DHL logistics problem using Gurobi. The goal is to optimize the assignment of consignments to trucks, considering various constraints such as truck capacities, consignment release times, operational hours, and sorting capacities at destination facilities.

### Table of Contents

- *Installation*
- *Usage*
- *Project Structure*
- *Methods*

### Installation

**Install the required packages:**
pip install -r requirements.txt

**Install Gurobi:**
Follow the instructions on the Gurobi website to install Gurobi and obtain a license.

### Usage

**Ensure you have the required datasets in the Dataset directory:**
- 2024-04-25_OR Praktikum_RWTH Aachen_WBeh_Aufträge.xlsx
- 2024-04-25_OR Praktikum_RWTH Aachen_Inputs.xlsx
- 2024-04-25_OSRM_Truck_Distanzen+Fahrtzeiten_PZ_x_PZ.xlsx

**Run the main script:**
python dhl_optimization.py

**The output will be saved in the output directory as output.csv.**

### Project Structure

DHL_Optimization/
├── Dataset/
│   ├── 2024-04-25_OR Praktikum_RWTH Aachen_WBeh_Aufträge.xlsx
│   ├── 2024-04-25_OR Praktikum_RWTH Aachen_Inputs.xlsx
│   └── 2024-04-25_OSRM_Truck_Distanzen+Fahrtzeiten_PZ_x_PZ.xlsx
├── output/
│   └── output.csv
├── requirements.txt
├── Optimization_gurobi.py
└── readme.md

### Methods

**DHL_Optimization**
A class to represent the DHL Optimization problem.

**Attributes:**
- *source_df (pd.DataFrame)*: DataFrame containing source facility information.
- *destination_df (pd.DataFrame)*: DataFrame containing destination facility information.
- *trucking_df (pd.DataFrame)*: DataFrame containing trucking information.
- *model (gurobipy.Model)*: Gurobi optimization model.
- *source_list (list)*: List of unique source facility IDs.
- *destination_list (list)*: List of unique destination facility IDs.
- *routes_list (list)*: List of possible routes between source and destination facilities.
- *consignment_list (list)*: List of consignment IDs.
- *valid_combinations (list)*: List of valid combinations of routes and consignments.
- *trucks (range)*: Range of truck indices.
- *X (dict)*: Decision variables for consignment assignment to trucks.
- *Z (dict)*: Decision variables for truck usage.
- *T (dict)*: Decision variables for truck release times.
- *ArrivalDay (dict)*: Decision variables for truck arrival days.
- *ArrivalTime (dict)*: Decision variables for truck arrival times.

**Methods:**
- *__init__(self)*: Initializes the DHL_Optimization class with default values.
- *read_data(self, source_path, destination_path, trucking_path)*: Reads data from Excel sheets into pandas DataFrames.
- *normalize_shift_times(self)*: Normalizes the shift times in the destination DataFrame to ensure end times after midnight are handled correctly.
- *initialize_model(self)*: Initializes the Gurobi model with decision variables and the objective function.
- *add_constraints(self)*: Adds constraints to the Gurobi model to ensure the solution is feasible.
- *solve(self)*: Solves the optimization model and prints the solution.

**Main Function**
- *main()*: Creates an instance of DHL_Optimization, reads data, normalizes shift times, initializes the model, adds constraints, and solves the optimization problem.