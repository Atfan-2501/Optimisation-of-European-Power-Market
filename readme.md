### DHL Optimization

### Overview
This project implements an optimization solution for the DHL logistics problem using Gurobi. The goal is to optimize the assignment of consignments to trucks, considering various constraints such as truck capacities, consignment release times, operational hours, and sorting capacities at destination facilities.

### Features
- **Data Normalization:** Adjusts data to fit the required formats and timeframes.
- **Model Initialization:** Sets up the optimization model with defined variables and constraints.
- **Constraints Management:** Ensures that all logistical and operational constraints are satisfied.
- **Optimization and Solving:** Utilizes the Gurobi solver to find the optimal solution.
- **Visualization:** Provides a visual representation of the solution using Streamlit and Folium.

### Project Structure
**1. optimization.py**
This module contains the DHL_Optimization class that manages the entire optimization process:

- *Attributes:*
    - source_df: DataFrame containing consignment source information.
    - destination_df: DataFrame containing destination details.
    - trucking_df: DataFrame containing trucking route details.

- *Methods:*
    - normalize_shift_times(): Converts shift start and end times to the correct format.
    - initialize_model(selected_sources, selected_destination): Sets up the optimization model.
    - add_constraints(): Adds various constraints to the model.
    - solve(): Solves the optimization model.
    - visualize_results(solution_df): Visualizes the optimal solution using Streamlit and Folium.

**2. optimization_main.py**
The main script to run the optimization process:

- Loads input data from Excel files.
- Creates an instance of DHL_Optimization.
- Normalizes data and initializes the model.
- Adds constraints and solves the model.
- Visualizes the results.

**3. test_optimization.py**
Contains unit tests for the optimization process using pytest:

- *Fixtures:*
    - optimizer(): Sets up an optimizer instance with dummy data for testing.

- *Test Cases:*
    - test_initialize_model(): Verifies model initialization.
    - test_add_constraints(): Checks if constraints are correctly added.
    - test_optimal_solution(): Ensures an optimal solution is found with dummy data.
    - test_truck_capacity_constraint(): Validates truck capacity constraints.
    - test_release_time_constraint(): Checks release time constraints.
    - test_operational_hours_constraint(): Ensures trucks arrive within operational hours.
    - test_consignment_assignment(): Confirms consignments are assigned to exactly one truck.
    - test_flow_conservation(): Validates flow conservation constraints.
    - test_sorting_capacity_constraint(): Checks sorting capacity constraints.
    - test_solve_function(): Ensures the solve function finds an optimal solution.

**4. colors.py**
Color class mainly used in this project for highlighting keywords in the output

**5. requirements.txt**
Lists the dependencies required for the project:
    pandas
    openpyxl
    gurobipy
    streamlit
    folium
    streamlit_folium

### How to Run

**1. Install Dependencies:**
    pip install -r requirements.txt

**2. Prepare Data:** Ensure the source, destination, and trucking data are available in the specified format.

**3. Run Optimization:**
    python optimization_main.py

**4. Run Tests:**
    pytest test_optimization.py

### Streamlit Visualization

**Setting Up Streamlit**
Streamlit is used to create an interactive web application to visualize the optimization results. The app displays the optimal routes and consignments using Folium for map visualization.

**Running the Streamlit App**
To run the Streamlit app, use the following command:
    streamlit run main.py

**Interactive Output**
The Streamlit app provides the following interactive outputs:
- *Map Visualization:* Displays the routes of the trucks from origins to destinations using Folium.
- *Summary Statistics:* Shows key statistics about the optimization results, such as total cost, number of consignments assigned, and truck utilization.
- *Filters and Controls:* Allows users to filter results based on specific criteria and adjust visualization settings.

### Usage
- **Normalization:** Adjusts the data to ensure consistency and compatibility with the model.
- **Initialization:** Sets up the optimization model with the required variables and constraints.
- **Constraints:** Adds operational and logistical constraints to ensure feasibility.
- **Solving:** Uses Gurobi to find the optimal solution.
- **Visualization:** Presents the results using Streamlit and Folium for easy interpretation.

### Contributors
**Atfan Deshmukh - @atfan.deshmukh25**
**Harshvardhan Kanthode - @harshvardhankanthode99**
**Praveen Kumar Ojha - @ojha.praveenk**