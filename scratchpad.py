# Setup
BResetSimRequest = False

# VM Running
SimulationAlive = True
NSimRequest = 6

# VM Stops
SimulationAlive = False
NSimRequest = 6

while True:
    if SimulationAlive:
        BResetSimRequest = False
    else:
        if not BResetSimRequest:
            NSimRequest = 0
            BResetSimRequest = True


