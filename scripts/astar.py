import matplotlib.pyplot as plt

class Astar():
	def __init__(self, graph, start, goal):
		"""	Initialize maze search
				graph: generated from maze.py 
				start: tuple starting coordinate
				goal: tuple goal coordinate
		"""
		self.graph = graph 
		self.start = start 
		self.goal = goal 
		self.frontier = [] #priority queue
		self.came_from = {} #contains previous node
		self.a_star_search()
		# self.path = self.getPath()

	def heuristic(self, node):
		""" return calculated manhattan distance from node to goal
				node: node to start from 
		"""
		return abs(node[0]-self.goal[0]) + abs(node[1]-self.goal[1])
	
	def a_star_search(self):
		""" traverse the maze and check nodes by priority
		"""
		#set up starting node
		self.addToQueue(self.start, 0) #starting node with 0 priority
		cost_so_far = {}
		self.came_from[self.start] = None #starting node has no previous node
		cost_so_far[self.start] = 0 #no cost so far

		while len(self.frontier): #while there are nodes to check
			current = self.frontier.pop()[0] #coordinate with highest priority

			if current == self.goal: #if we found goal
				print "goal!!"
				print "cost", cost_so_far[current]
				return #done

			x, y = current
			for neighbor in self.graph[x][y].neighbors: #for each neighbor around current node
				newCost = cost_so_far[current] + self.calcWeights(current, neighbor) #calculate new cost

				#if found new node or found a lower cost route to old node
				if neighbor not in cost_so_far or newCost < cost_so_far[neighbor]: 
					cost_so_far[neighbor] = newCost #add/update cost
					priority = -(newCost + self.heuristic(neighbor)) #set priority
					self.came_from[neighbor] = current #add/update previous node
					self.addToQueue(neighbor, priority) #add to Queue

	def calcWeights(self, node1, node2):
		"""	return calculated weight moving from node1 to node2
				introduces penalty for turns
				node1: tuple coordinate of first node
				node2: tuple coordinate of second node
		"""
		node3 = self.came_from[node1] #where we came from
		if not node3: #if starting node
			return 1 
		elif node1[0] == node2[0] == node3[0]: #if vertical line
			return 1
		elif node1[1] == node2[1] == node3[1]: #if horizontal line
			return 1 
		else: #turn required
			return 2 #introduce penalty 2 

	def addToQueue(self, node, priority):
		"""	Update Queue with new node and its priority
				output list of nodes sorted by priority
				format [((x, y), z)] where x, y are node coordinates, z is priority
				node: tuple coordinate of node
				priority: integer node priority
		"""
		self.frontier.append((node, priority)) #add to list
		self.frontier.sort(key= lambda prior: prior[1]) #sort by priority

	# def getPath(self):
	# 	path = []

	# 	node = self.goal #work backwards
	# 	last = self.came_from[node] #node we came from
		
	# 	while last: #not at starting node
	# 		path.append(node)
	# 		node = last #update current node
	# 		last = self.came_from[last]
	# 	path.append(node) #add the last node
	# 	return list(reversed(path))





 