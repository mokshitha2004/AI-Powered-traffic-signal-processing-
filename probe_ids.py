import traci
SUMO_BINARY = "sumo-gui"
SUMO_CONFIG = "simulation.sumocfg"

# start SUMO (GUI) and connect
traci.start([SUMO_BINARY, "-c", SUMO_CONFIG, "--start"])
print("SUMO started")

# print lists
print("Traffic light IDs:", traci.trafficlight.getIDList())
print("Edge IDs (first 10):", traci.edge.getIDList()[:10])
print("Lane IDs (first 12):", traci.lane.getIDList()[:12])

traci.close()
print("Done.")
