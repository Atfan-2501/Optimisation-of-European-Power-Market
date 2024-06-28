from gurobipy import Model, GRB

# Create the model
model = Model("SwapBodyOptimization")

# Parameters (Example Values)
N = 5  # Total number of service centers
K = 10  # Total number of swap bodies
L = 3  # Total number of trucks
S = 100  # Sorting capacity at PZE per hour

# Ensure the cost matrix c has the correct dimensions [N][N][K]
c = [[[0 for k in range(K)] for j in range(N)] for i in range(N)]
q = [1 for k in range(K)]  # Sorting quantity per hour

# Initialize c with example values for testing
for i in range(N):
    for j in range(N):
        for k in range(K):
            c[i][j][k] = 1  # Example cost value

# Decision Variables
x = model.addVars(N, N, K, vtype=GRB.BINARY, name="x")
y = model.addVars(L, K, vtype=GRB.BINARY, name="y")
z = model.addVars(K, vtype=GRB.BINARY, name="z")

# Objective Functions
# Minimization of Transportation Cost
model.setObjective(sum(c[i][j][k] * x[i, j, k] for i in range(N) for j in range(N) for k in range(K)), GRB.MINIMIZE)

# Maximize the sorted quantity by the PZE cutoff
model.setObjective(sum(q[k] * z[k] for k in range(K)), GRB.MAXIMIZE)

# Constraints
# Each truck can’t take more than 2 swap bodies
for l in range(L):
    model.addConstr(sum(y[l, k] for k in range(K)) <= 2, name=f"truck_capacity_{l}")

# Max. Sorting capacity per hour at PZE
model.addConstr(sum(q[k] for k in range(K)) <= S, name="sorting_capacity")

# Choose to select route or not
for i in range(N):
    for j in range(N):
        for k in range(K):
            model.addConstr(x[i, j, k] <= 1, name=f"route_selection_{i}_{j}_{k}")

# Optimize the model
model.optimize()

# Print results
if model.status == GRB.OPTIMAL:
    for v in model.getVars():
        print(f'{v.varName}: {v.x}')
    print(f'Obj: {model.objVal}')
else:
    print("No optimal solution found.")