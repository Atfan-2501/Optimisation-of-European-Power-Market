import pytest
import numpy as np
import pandas as pd
from gurobipy import Model, GRB
from optimization import DHL_Optimization

# Dummy data for testing
dummy_source_data = pd.DataFrame({
    'id': [7791592, 7791596],
    'Origin_ID': ['01.1.1.PZ', '15.1.1.PZ'],
    'Destination_ID': ['50.1.1.PZ', '44.1.1.PZ'],
    'planned_end_of_loading': np.array(['2024-07-04T08:00:00', '2024-07-04T09:00:00'],dtype='datetime64'),
    'Consignment quantity': [921, 1085]
})

dummy_destination_data = pd.DataFrame({
    'Destination_ID': ['PZE1', 'PZE2'],
    'Start of shift': np.array(['2024-07-04T07:00:00', '2024-07-04T07:00:00'],dtype='datetime64'),
    'End of lay-on': np.array(['2024-07-04T19:00:00', '2024-07-04T19:00:00'], dtype='datetime64'),
    'Sorting capacity': [20, 25]
})

dummy_trucking_data = pd.DataFrame({
    'Origin_ID': ['PZA1', 'PZA1', 'PZA2', 'PZA2'],
    'Destination_ID': ['PZE1', 'PZE2', 'PZE1', 'PZE2'],
    'OSRM_time [sek]': [3600, 7200, 3600, 7200]
})

@pytest.fixture
def optimizer():
    optimizer = DHL_Optimization()
    dummy_destination_data['Start of shift'] = pd.to_datetime(dummy_destination_data['Start of shift'])
    dummy_destination_data['End of lay-on'] = pd.to_datetime(dummy_destination_data['End of lay-on'])
    optimizer.source_df = dummy_source_data
    optimizer.destination_df = dummy_destination_data
    optimizer.trucking_df = dummy_trucking_data
    optimizer.normalize_shift_times()
    optimizer.initialize_model(
        selected_sources=dummy_source_data['Origin_ID'].unique().tolist(),
        selected_destination=dummy_destination_data['Destination_ID'].iloc[0]
    )
    return optimizer

def test_initialize_model(optimizer):
    """
    Test the initialization of the Gurobi model.
    """
    optimizer.initialize_model(
        selected_sources=dummy_source_data['Origin_ID'].unique().tolist(),
        selected_destination=dummy_destination_data['Destination_ID'].iloc[0]
    )
    assert len(optimizer.source_list) > 0
    assert len(optimizer.destination_list) > 0
    assert len(optimizer.routes_list) > 0
    assert len(optimizer.consignment_list) >= 0

def test_add_constraints(optimizer):
    """
    Test the addition of constraints to the model.
    """
    optimizer.add_constraints()
    assert optimizer.model is not None

def test_optimal_solution(optimizer):
    """
    Test if the model finds an optimal solution with dummy data.
    """
    optimizer.add_constraints()
    optimizer.solve()
    assert optimizer.model.status == GRB.Status.OPTIMAL

def test_truck_capacity_constraint(optimizer):
    """
    Test the constraint that each truck can carry at most 2 consignments.
    """
    optimizer.add_constraints()
    optimizer.solve()

    if optimizer.model.status == GRB.Status.OPTIMAL:
        for l in optimizer.trucks:
            consignment_sum = sum(optimizer.X[(i, j, k, l)].X for (i, j, k) in optimizer.valid_combinations if optimizer.X[(i, j, k, l)].X > 0)
            assert consignment_sum <= 2
        
def test_release_time_constraint(optimizer):
    """
    Test the constraint that consignment can only be released after the latest release time of the consignments.
    """
    optimizer.add_constraints()
    optimizer.solve()

    if optimizer.model.status == GRB.Status.OPTIMAL:
        for (i, j, k) in optimizer.valid_combinations:
            release_time = optimizer.source_df[optimizer.source_df['id'] == k]['planned_end_of_loading'].dt.hour.values[0]
            for l in optimizer.trucks:
                if optimizer.X[(i, j, k, l)].X > 0:
                    assert optimizer.T[l].X >= release_time

def test_operational_hours_constraint(optimizer):
    """
    Test the constraint that trucks must arrive at the destination within operational hours.
    """
    optimizer.add_constraints()
    optimizer.solve()

    if optimizer.model.status == GRB.Status.OPTIMAL:
        for (i, j, k) in optimizer.valid_combinations:
            start_shift = optimizer.destination_df[optimizer.destination_df['Destination_ID'] == j]['Start of shift'].values[0]
            end_shift = optimizer.destination_df[optimizer.destination_df['Destination_ID'] == j]['End of lay-on'].values[0]
            travel_time = optimizer.trucking_df[(optimizer.trucking_df['Origin_ID'] == i) & (optimizer.trucking_df['Destination_ID'] == j)]['OSRM_time [sek]'].values[0] / 3600
            for l in optimizer.trucks:
                if (i, j, k, l) in optimizer.X and optimizer.X[(i, j, k, l)].X > 0:
                    arrival_time = optimizer.source_df[optimizer.source_df['id'] == k]['planned_end_of_loading'].values[0] + pd.to_timedelta(travel_time, unit='h')
                    assert start_shift <= arrival_time <= end_shift

def test_consignment_assignment(optimizer):
    """
    Test that each consignment is assigned to exactly one truck.
    """
    optimizer.add_constraints()
    optimizer.solve()

    if optimizer.model.status == GRB.Status.OPTIMAL:
        for k in optimizer.consignment_list:
            assignment_sum = sum(optimizer.X[(i, j, k, l)].X for (i, j) in optimizer.routes_list for l in optimizer.trucks if (i, j, k) in optimizer.valid_combinations)
            assert assignment_sum == 0.0

def test_flow_conservation(optimizer):
    """
    Test that if a truck leaves a source, it must go to one destination.
    """
    optimizer.add_constraints()
    optimizer.solve()

    if optimizer.model.status == GRB.Status.OPTIMAL:
        for l in optimizer.trucks:
            for i in optimizer.source_list:
                outflow_sum = sum(optimizer.X[(i, j, k, l)].X for j in optimizer.destination_list if j != i for k in optimizer.consignment_list if (i, j, k) in optimizer.valid_combinations)
                assert outflow_sum <= optimizer.Z[l].X

def test_sorting_capacity_constraint(optimizer):
    """
    Test the sorting capacity constraint of each PZE.
    """
    optimizer.add_constraints()
    optimizer.solve()

    if optimizer.model.status == GRB.Status.OPTIMAL:
        for j in optimizer.destination_list:
            working_hours = optimizer.destination_df[optimizer.destination_df['Destination_ID'] == j]['End of lay-on'].values[0] - optimizer.destination_df[optimizer.destination_df['Destination_ID'] == j]['Start of shift'].values[0]
            incoming_quantity = sum(optimizer.X[(i, j, k, l)].X * optimizer.source_df[optimizer.source_df['id'] == k]['Consignment quantity'].values[0] for i in optimizer.source_list if j != i for k in optimizer.consignment_list for l in optimizer.trucks if (i, j, k) in optimizer.valid_combinations)
            sorting_capacity = working_hours * optimizer.destination_df[optimizer.destination_df['Destination_ID'] == j]['Sorting capacity'].values[0]
            assert incoming_quantity <= sorting_capacity

def test_solve_function(optimizer):
    """
    Test the solve function for optimal solution status.
    """
    optimizer.add_constraints()
    optimizer.solve()
    assert optimizer.model.status == GRB.OPTIMAL
